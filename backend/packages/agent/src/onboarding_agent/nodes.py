"""Graph nodes (wiki/lifecycle.md §3).

- code nodes decide and compute: verify_identity, check_otp, check_document, fetch_purchases,
  check_eligibility, rank_products, quote_premium, open_application, submit_application
- LLM nodes extract or write: assess_needs, explain_recommendation, collect_parties,
  collect_answers, summarize_application
- wait nodes stop on `interrupt()`: ask_customer, await_decision, confirm_summary, await_agent

A node that needs customer input sets `waiting_for` and appends the question, then routes to
`ask_customer`, which interrupts and records the answer. Nodes reach the domain DB only through the
`UnitOfWork` port. Every write is idempotent: new rows get `uuid5(thread_id, node, step)` ids and are
upserted with `save`."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from onboarding_agent.deps import AgentDeps
from onboarding_agent.ids import node_uuid
from onboarding_agent.llm.schemas import (
    AnswersExtraction,
    ApplicationSummary,
    NeedsExtraction,
    PartiesExtraction,
    RecommendationRationale,
)
from onboarding_agent.texts import field_list, human, locale_of, mask_phone, note, price_label, say, t
from onboarding_core.application.models import Application
from onboarding_core.catalog.eligibility import (
    RuleSpec,
    age_on,
    evaluate_product,
    rank_order,
    target_market_score,
)
from onboarding_core.catalog.models import Product
from onboarding_core.crypto import decrypt_field, encrypt_field, hmac_hex
from onboarding_core.needs.models import InsurableObject, NeedsAssessment
from onboarding_core.party.models import Party
from onboarding_core.ports import UnitOfWork
from onboarding_core.quoting.models import Quote
from onboarding_core.quoting.pricing import RatingError, compute_premium, compute_term, quote_valid_until
from onboarding_core.recommendation.models import Recommendation
from onboarding_core.util import iso, parse_date

MAX_NEEDS_ROUNDS = 3
MAX_ANSWERS_ROUNDS = 3
DEVICE_OBJECTIVES = {"PROTECT_DEVICE", "EXTEND_WARRANTY"}

DEVICE_CATEGORY_ALIASES = {
    "LAPTOP": "NOTEBOOK",
    "NOTEBOOK_COMPUTER": "NOTEBOOK",
    "COMPUTER": "NOTEBOOK",
    "PHONE": "SMARTPHONE",
    "MOBILE": "SMARTPHONE",
    "MOBILE_PHONE": "SMARTPHONE",
    "CELLPHONE": "SMARTPHONE",
    "CELL_PHONE": "SMARTPHONE",
    "HANDSET": "SMARTPHONE",
    "TELEVISION": "TV",
    "IPAD": "TABLET",
    "PAD": "TABLET",
    "WATCH": "WEARABLE",
    "SMARTWATCH": "WEARABLE",
    "SMART_WATCH": "WEARABLE",
}

# LLM answer keys that mean a required application field (the first matching alias fills it).
ANSWER_ALIASES = {
    "destination": ("destination_countries", "destinations", "destination_country"),
    "trip_cost": ("trip_cost_minor",),
    "purchase_price": ("purchase_price_minor", "price_minor", "price"),
    "device_model": ("model",),
    "msrp": ("msrp_minor",),
    "order_number": ("order_id", "order_no"),
    "traveler_gender": ("gender",),
    "traveler_date_of_birth": ("date_of_birth", "birth_date"),
    "traveler_name": ("full_name", "name"),
    "departure_date": ("departure_datetime",),
    "return_date": ("return_datetime",),
    "imei": ("serial_number",),
}


def normalize_device_category(value: Any) -> str | None:
    if not value:
        return None
    key = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    return DEVICE_CATEGORY_ALIASES.get(key, key)


def apply_answer_aliases(required: list[str], answers: dict[str, Any]) -> dict[str, Any]:
    out = dict(answers)
    for field_name in required:
        if out.get(field_name) not in (None, "", []):
            continue
        for alias in ANSWER_ALIASES.get(field_name, ()):
            value = out.get(alias)
            if value not in (None, "", []):
                out[field_name] = ", ".join(map(str, value)) if isinstance(value, list) else value
                break
    return out


def _thread(config: RunnableConfig) -> str:
    return config["configurable"]["thread_id"]


def _step(config: RunnableConfig) -> int:
    return int(config.get("metadata", {}).get("langgraph_step", 0))


def _uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def party_view(p: Party) -> dict[str, Any]:
    return {"party_type": p.party_type, "date_of_birth": iso(p.date_of_birth)}


def needs_view(na: NeedsAssessment | None) -> dict[str, Any]:
    if na is None:
        return {}
    return {
        "age_range": na.age_range,
        "occupation": na.occupation,
        "residence_country": na.residence_country,
        "existing_coverage": na.existing_coverage or [],
        "objectives": na.objectives or [],
        "device": na.device,
        "trip": na.trip,
    }


def object_view(o: InsurableObject) -> dict[str, Any]:
    return {
        "insurable_object_id": str(o.insurable_object_id),
        "object_type": o.object_type,
        "source": o.source,
        "attributes": o.attributes,
    }


def compute_needs_missing(values: dict[str, Any], *, market: str, has_partner_device: bool) -> list[str]:
    """Deterministic profiling completeness; the LLM's own `missing_fields` is advisory only."""
    missing = [f for f in ("age_range", "residence_country") if not values.get(f)]
    objectives = set(values.get("objectives") or [])
    if not objectives:
        missing.append("objectives")
    device, trip = values.get("device") or {}, values.get("trip") or {}
    if (objectives & DEVICE_OBJECTIVES or device) and not has_partner_device:
        # purchase_date is not required here: when unknown, eligibility assumes "bought today" and
        # the application step asks for the real date (see device_attributes / prefill_answers).
        for key in ("device_category", "purchase_price_minor"):
            if device.get(key) in (None, ""):
                missing.append(f"device.{key}")
    if "TRAVEL_COVER" in objectives or trip:
        keys = ["departure_date", "return_date", "destination_countries"]
        if market == "US":
            keys.append("trip_cost_minor")
        for key in keys:
            if trip.get(key) in (None, "", []):
                missing.append(f"trip.{key}")
    return missing


def merge_needs(base: dict[str, Any], ext: NeedsExtraction, market: str) -> dict[str, Any]:
    merged = dict(base)
    for key in ("age_range", "occupation", "residence_country"):
        value = getattr(ext, key)
        if value:
            merged[key] = value
    if ext.existing_coverage:
        merged["existing_coverage"] = ext.existing_coverage
    if ext.objectives:
        merged["objectives"] = list(dict.fromkeys(ext.objectives))
    for key in ("device", "trip"):
        value = getattr(ext, key)
        if value:
            merged[key] = {**(merged.get(key) or {}), **{k: v for k, v in value.items() if v is not None}}
    if merged.get("device") and merged["device"].get("device_category"):
        merged["device"]["device_category"] = normalize_device_category(merged["device"]["device_category"])
    if merged.get("residence_country"):
        merged["residence_country"] = str(merged["residence_country"]).upper()[:2]
    else:
        # Assumption: a customer onboarding in a market lives there unless they say otherwise.
        merged["residence_country"] = market
    return merged


def device_attributes(device: dict[str, Any], today: Any) -> dict[str, Any]:
    attrs = {k: v for k, v in device.items() if v is not None}
    if attrs.get("device_category"):
        attrs["device_category"] = normalize_device_category(attrs["device_category"])
    # Assumptions, recorded in `assumed_fields` so they are never copied into the application:
    # a device the customer is insuring now is new, undamaged and was bought today unless stated.
    assumed = []
    for key, default in (("condition", "NEW"), ("has_existing_damage", False), ("purchase_date", today.isoformat())):
        if key not in attrs:
            attrs[key] = default
            assumed.append(key)
    if assumed:
        attrs["assumed_fields"] = assumed
    return attrs


def trip_attributes(trip: dict[str, Any], residence_country: str | None) -> dict[str, Any]:
    attrs = {k: v for k, v in trip.items() if v is not None}
    if isinstance(attrs.get("destination_countries"), str):
        attrs["destination_countries"] = [attrs["destination_countries"]]
    attrs.setdefault("departure_country", residence_country)
    return attrs


def prefill_answers(
    required: list[str], obj: dict[str, Any] | None, insured: Party | None, today: Any
) -> dict[str, Any]:
    """Answers the application can take from data already verified or collected."""
    attrs = (obj or {}).get("attributes", {})
    assumed = set(attrs.get("assumed_fields") or [])
    a = {k: v for k, v in attrs.items() if k not in assumed}
    dob = insured.date_of_birth if insured else None
    candidates: dict[str, Any] = {
        "imei": a.get("imei"),
        "device_model": " ".join(x for x in (a.get("manufacturer"), a.get("model")) if x) or None,
        "msrp": a.get("msrp_minor") or a.get("purchase_price_minor"),
        "activation_date": a.get("activation_date"),
        "serial_number": a.get("serial_number"),
        "purchase_date": a.get("purchase_date"),
        "purchase_price": a.get("purchase_price_minor"),
        "order_number": a.get("order_id"),
        "proof_of_purchase": f"partner order {a['order_id']}" if a.get("order_id") else None,
        "departure_date": a.get("departure_date"),
        "return_date": a.get("return_date"),
        "destination": ", ".join(a["destination_countries"]) if a.get("destination_countries") else None,
        "trip_cost": a.get("trip_cost_minor"),
        "traveler_name": insured.full_name if insured else None,
        "traveler_date_of_birth": iso(dob) if dob else None,
        "traveler_age": age_on(dob, today) if dob else None,
    }
    return {k: candidates[k] for k in required if candidates.get(k) not in (None, "")}


def missing_answers(required: list[str], answers: dict[str, Any]) -> list[str]:
    return [f for f in required if answers.get(f) in (None, "", [])]


def latest_texts(messages: list[BaseMessage], input_types: tuple[str, ...]) -> list[str]:
    return [
        str(m.content)
        for m in messages
        if isinstance(m, HumanMessage) and m.additional_kwargs.get("input_type") in input_types
    ]


class Nodes:
    def __init__(self, deps: AgentDeps) -> None:
        self.d = deps

    # ----------------------------------------------------------------------------------- helpers

    def now(self) -> datetime:
        return self.d.clock()

    async def _touch(self, state: dict[str, Any], entity_type: str, entity_id: Any) -> None:
        await self.d.on_entity(state["session_id"], entity_type, str(entity_id))

    async def _party(self, uow: UnitOfWork, state: dict[str, Any]) -> Party:
        party = await uow.parties.get(_uuid(state["party_id"]))
        if party is None:
            raise LookupError("session party not found")
        return party

    def _system(self, state: dict[str, Any], party: Party, instructions: str) -> SystemMessage:
        market = state["market"]
        language = "Korean" if locale_of(state) == "ko" else "English"
        return SystemMessage(
            content=(
                "You are the onboarding assistant of an insurance company.\n"
                f"Customer: {party.full_name or 'unknown'}\n"
                f"Market: {market}. Reply in {language}. Today is {self.now().date().isoformat()}.\n"
                "Money is in integer minor units (KRW won, USD cents).\n\n"
                f"{instructions}"
            )
        )

    # ------------------------------------------------------------------------------------ nodes

    async def greet(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        text = t(
            lang,
            "안녕하세요! 보험 가입을 도와드릴게요. 먼저 본인 확인을 위해 이름, 이메일, 휴대폰 번호, "
            "신분증 종류와 번호를 알려 주세요. 파트너사 구매 기록 조회(제3자 제공)에 동의하시면 "
            "확인이 더 빨라집니다.",
            "Hi! I'll help you find the right cover. First, to verify your identity, please share your "
            "full name, email, phone number and an ID document. If you consent to us checking your "
            "purchase history with our partner, verification is faster.",
        )
        return {
            "stage": "IDENTITY",
            "waiting_for": "IDENTITY_INFO",
            "last_input": None,
            "identity_result": None,
            "messages": [say(text, self.now())],
        }

    async def ask_customer(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        kind = state.get("waiting_for")
        value = interrupt({"waiting_for": kind})
        actor = state.get("actor") or "CUSTOMER"
        lang, now = locale_of(state), self.now()
        out: dict[str, Any] = {"waiting_for": None, "last_input": kind}

        if kind == "IDENTITY_INFO":
            async with self.d.uow() as uow:
                party = await self._party(uow, state)
                party.full_name = str(value.get("full_name") or "").strip() or None
                party.email = str(value.get("email") or "").strip() or None
                party.phone = str(value.get("phone") or "").strip() or None
                party.id_document_type = value.get("id_document_type")
                number = str(value.get("id_document_number") or "").strip()
                if number:
                    party.id_document_number_enc = encrypt_field(self.d.config.aes_key, number)
                    party.id_document_hmac = hmac_hex(self.d.config.hmac_key, number)
                if value.get("date_of_birth"):
                    party.date_of_birth = parse_date(value["date_of_birth"])
                party.third_party_consent_at = now if value.get("third_party_consent") else None
                party.verification_status = "PENDING"
            await self._touch(state, "party", state["party_id"])
            consent = t(
                lang,
                "동의" if value.get("third_party_consent") else "동의 안 함",
                "yes" if value.get("third_party_consent") else "no",
            )
            text = t(
                lang,
                f"본인 정보를 입력했습니다 — {party.full_name} (파트너 조회 {consent})",
                f"Identity details submitted — {party.full_name} (partner lookup consent: {consent})",
            )
            out["identity_result"] = None
        elif kind == "OTP_CODE":
            # Wrapped in a dict so it lands in an encrypted blob: the saver stores primitive
            # channel values inline in the plaintext `checkpoints.checkpoint` JSONB.
            out["otp_code"] = {"code": str(value.get("code", "")).strip()}
            text = t(lang, "인증번호를 입력했습니다.", "Entered the verification code.")
        else:
            text = str(value.get("text") or "").strip() or "-"
        out["messages"] = [human(text, now, actor=actor, input_type=kind or "")]
        return out

    async def verify_identity(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            if party.third_party_consent_at is not None:
                res = await self.d.partner.match_customer(
                    full_name=party.full_name or "",
                    email=party.email or "",
                    phone=party.phone or "",
                    consent_at=party.third_party_consent_at,
                )
                if res.get("matched"):
                    party.partner_customer_ref = res.get("partner_customer_ref")
                    if res.get("date_of_birth"):
                        party.date_of_birth = parse_date(res["date_of_birth"])
                    party.verification_status = "VERIFIED"
                    party.verification_method = "PARTNER_MATCH"
                    party.verified_at = self.now()
                    text = t(
                        lang,
                        "파트너사 고객 정보로 본인 확인이 끝났습니다.",
                        "You're verified through your partner account.",
                    )
                    await self._touch(state, "party", party.party_id)
                    return {"identity_result": "MATCHED", "messages": [say(text, self.now())]}
            otp = await self.d.identity.send_otp(party.phone or "")
            party.verification_status = "PENDING"
        await self._touch(state, "party", state["party_id"])
        text = t(
            lang,
            f"{mask_phone(party.phone)} 번호로 인증번호를 보냈습니다. 받은 6자리 번호를 입력해 주세요.",
            f"We sent a verification code to {mask_phone(party.phone)}. Please enter the 6-digit code.",
        )
        return {
            "identity_result": "NOT_MATCHED",
            "otp_request_id": otp.get("otp_request_id"),
            "waiting_for": "OTP_CODE",
            "messages": [say(text, self.now())],
        }

    async def check_otp(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        verified = False
        code = (state.get("otp_code") or {}).get("code")
        if state.get("otp_request_id") and code:
            res = await self.d.identity.verify_otp(state["otp_request_id"], code)
            verified = bool(res.get("verified"))
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            if verified:
                party.verification_status = "VERIFIED"
                party.verification_method = "OTP"
                party.verified_at = self.now()
            else:
                # OTP is always the first counted failure, so `max` keeps a re-run idempotent.
                party.verification_attempts = max(party.verification_attempts or 0, 1)
        await self._touch(state, "party", state["party_id"])
        if verified:
            text = t(lang, "인증번호가 확인됐습니다.", "Code verified — thank you.")
            return {"identity_result": "OTP_OK", "otp_code": None, "messages": [say(text, self.now())]}
        text = t(
            lang,
            "인증번호가 맞지 않아 입력하신 신분증으로 확인해 볼게요.",
            "That code didn't work, so I'll verify the ID document you gave instead.",
        )
        return {"identity_result": "OTP_FAILED", "otp_code": None, "messages": [say(text, self.now())]}

    async def check_document(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
        verified = False
        if party.id_document_number_enc and party.id_document_type:
            number = decrypt_field(self.d.config.aes_key, party.id_document_number_enc)
            res = await self.d.identity.verify_document(
                document_type=party.id_document_type,
                document_number=number,
                full_name=party.full_name or "",
                date_of_birth=iso(party.date_of_birth),
            )
            verified = bool(res.get("verified"))
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            if verified:
                party.verification_status = "VERIFIED"
                party.verification_method = "DOCUMENT"
                party.verified_at = self.now()
            else:
                party.verification_attempts = 2
                party.verification_status = "FAILED"
        await self._touch(state, "party", state["party_id"])
        if verified:
            text = t(lang, "신분증으로 본인 확인이 끝났습니다.", "Your ID document is verified.")
            return {"identity_result": "DOC_OK", "messages": [say(text, self.now())]}
        text = t(
            lang,
            "본인 확인을 마치지 못했습니다. 상담원을 연결해 드릴게요.",
            "I couldn't verify your identity, so I'm connecting you with an agent.",
        )
        return {
            "identity_result": "DOC_FAILED",
            "handoff_reason": "IDENTITY_FAILED",
            "messages": [say(text, self.now())],
        }

    async def fetch_purchases(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        """Loads partner purchases as InsurableObjects. Without consent it does nothing — consent is a
        precondition of the node, not a branch (state-model.md §3)."""
        lang, ids = locale_of(state), list(state.get("insurable_object_ids") or [])
        found: list[str] = []
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
        if party.third_party_consent_at and party.partner_customer_ref:
            purchases = await self.d.partner.purchases(
                party.partner_customer_ref, consent_at=party.third_party_consent_at
            )
            async with self.d.uow() as uow:
                for p in purchases:
                    item = p.get("item") or {}
                    obj_id = node_uuid(_thread(config), "fetch_purchases", 0, str(p.get("order_id")))
                    attrs = {
                        "device_category": item.get("category"),
                        "manufacturer": item.get("manufacturer"),
                        "model": item.get("model"),
                        "imei": item.get("imei"),
                        "release_date": item.get("release_date"),
                        "activation_date": item.get("activation_date"),
                        "purchase_date": (p.get("purchased_at") or "")[:10] or None,
                        "purchase_price_minor": item.get("price_minor"),
                        "currency": item.get("currency"),
                        "order_id": p.get("order_id"),
                        # A partner sale is a new, undamaged device.
                        "condition": "NEW",
                        "has_existing_damage": False,
                    }
                    await uow.objects.save(
                        InsurableObject(
                            insurable_object_id=obj_id,
                            owner_party_id=party.party_id,
                            object_type="DEVICE",
                            source="PARTNER",
                            attributes={k: v for k, v in attrs.items() if v is not None},
                        )
                    )
                    if str(obj_id) not in ids:
                        ids.append(str(obj_id))
                    found.append(" ".join(x for x in (item.get("manufacturer"), item.get("model")) if x))
            for obj_id in ids:
                await self._touch(state, "insurable_object", obj_id)
        out: dict[str, Any] = {
            "stage": "PROFILING",
            "insurable_object_ids": ids,
            "needs_complete": False,
            "needs_rounds": 0,
            "last_input": None,
            "handoff_reason": None,
        }
        if found:
            text = t(
                lang,
                f"파트너사 구매 기록에서 {', '.join(found)} 구매를 찾았습니다.",
                f"I found your recent purchase: {', '.join(found)}.",
            )
            out["messages"] = [say(text, self.now())]
        return out

    async def assess_needs(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        m, now, actor = state["market"], self.now(), state.get("actor") or "CUSTOMER"
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            current = (
                await uow.needs.get(_uuid(state["needs_assessment_id"])) if state.get("needs_assessment_id") else None
            )
            objects = await uow.objects.list(_uuid(i) for i in state.get("insurable_object_ids") or [])
        partner_objects = [o for o in objects if o.source == "PARTNER"]

        if state.get("last_input") != "NEEDS":
            # Nothing new to assess yet: ask (first visit, after a CHANGE without text, after handoff).
            if current is not None and current.completed_at is None and current.missing_fields:
                text = t(
                    lang,
                    f"추천을 위해 {field_list(lang, current.missing_fields)}을(를) 알려 주세요.",
                    f"To recommend cover, please tell me {field_list(lang, current.missing_fields)}.",
                )
            elif current is not None and current.completed_at is not None:
                text = t(
                    lang,
                    "어떤 점을 바꾸고 싶으신가요? 달라진 내용을 알려 주세요.",
                    "What would you like to change? Tell me what's different.",
                )
            else:
                text = t(
                    lang,
                    "이제 맞는 보험을 찾아볼게요. 나이, 직업, 거주 국가와 무엇을 보장받고 싶은지(기기, 여행 등) "
                    "알려 주세요. 기존에 가입한 보험이 있다면 함께 알려 주세요.",
                    "Now let's find the right cover. Tell me your age, occupation, where you live, and "
                    "what you'd like to protect (a device, a trip, ...). Mention any insurance you "
                    "already have.",
                )
            return {
                "needs_complete": False,
                "handoff_reason": None,
                "waiting_for": "NEEDS",
                "messages": [say(text, now)],
            }

        rounds = int(state.get("needs_rounds") or 0) + 1
        known_devices = [
            {k: o.attributes.get(k) for k in ("device_category", "manufacturer", "model", "purchase_date")}
            for o in partner_objects
        ]
        base = needs_view(current)
        instructions = (
            "Extract the customer's profile and insurance needs from their messages into the "
            "NeedsExtraction tool. Use null for anything the customer has not said; do not guess.\n"
            f"Devices already known from partner purchase records: {json.dumps(known_devices, ensure_ascii=False)}\n"
            f"Values captured so far: {json.dumps(base, ensure_ascii=False, default=str)}"
        )
        texts = latest_texts(state.get("messages") or [], ("NEEDS",))
        ext = await self.d.llm.extract(
            "assess_needs",
            NeedsExtraction,
            [self._system(state, party, instructions), HumanMessage("\n\n".join(texts) or "-")],
        )
        values = merge_needs(base, ext, m)
        missing = compute_needs_missing(values, market=m, has_partner_device=bool(partner_objects))
        step = _step(config)

        async with self.d.uow() as uow:
            if current is not None and current.completed_at is None:
                na = await uow.needs.get(current.needs_assessment_id)
            else:
                na_id = node_uuid(_thread(config), "assess_needs", step)
                na = await uow.needs.get(na_id)
                if na is None:
                    version = await uow.needs.latest_version(party.party_id) + 1
                    na = NeedsAssessment(
                        needs_assessment_id=na_id,
                        party_id=party.party_id,
                        session_id=_uuid(state["session_id"]),
                        version=version,
                        created_at=now,
                    )
                    await uow.needs.add(na)
            na.age_range = values.get("age_range")
            na.occupation = values.get("occupation")
            na.residence_country = values.get("residence_country")
            na.existing_coverage = _jsonable(values.get("existing_coverage") or [])
            na.objectives = list(values.get("objectives") or [])
            na.device = _jsonable(values.get("device"))
            na.trip = _jsonable(values.get("trip"))
            na.captured_by = actor
            na.missing_fields = missing
            ids = [str(o.insurable_object_id) for o in partner_objects]
            if not missing:
                na.completed_at = now
                if values.get("device") and not partner_objects:
                    obj_id = node_uuid(_thread(config), "assess_needs", step, "device")
                    await uow.objects.save(
                        InsurableObject(
                            insurable_object_id=obj_id,
                            owner_party_id=party.party_id,
                            object_type="DEVICE",
                            source=actor,
                            attributes=_jsonable(device_attributes(values["device"], now.date())),
                        )
                    )
                    ids.append(str(obj_id))
                if values.get("trip"):
                    obj_id = node_uuid(_thread(config), "assess_needs", step, "trip")
                    await uow.objects.save(
                        InsurableObject(
                            insurable_object_id=obj_id,
                            owner_party_id=party.party_id,
                            object_type="TRIP",
                            source=actor,
                            attributes=_jsonable(trip_attributes(values["trip"], values.get("residence_country"))),
                        )
                    )
                    ids.append(str(obj_id))
            na_id = str(na.needs_assessment_id)
        await self._touch(state, "needs_assessment", na_id)

        if not missing:
            for obj_id in ids:
                await self._touch(state, "insurable_object", obj_id)
            text = t(
                m, "감사합니다. 가입할 수 있는 상품을 확인해 볼게요.", "Thanks — let me check which products fit you."
            )
            return {
                "needs_assessment_id": na_id,
                "needs_complete": True,
                "needs_rounds": 0,
                "last_input": None,
                "handoff_reason": None,
                "insurable_object_ids": ids,
                "messages": [say(text, now)],
            }
        if rounds >= MAX_NEEDS_ROUNDS:
            text = t(
                lang,
                "필요한 정보를 다 받지 못해 상담원을 연결해 드릴게요.",
                "I still don't have everything I need, so I'm bringing in an agent to help.",
            )
            return {
                "needs_assessment_id": na_id,
                "needs_complete": False,
                "needs_rounds": rounds,
                "last_input": None,
                "handoff_reason": "NEEDS_INCOMPLETE",
                "messages": [say(text, now)],
            }
        text = t(
            lang,
            f"추천을 위해 {field_list(lang, missing)}을(를) 더 알려 주세요.",
            f"Thanks! To recommend cover I also need {field_list(lang, missing)}.",
        )
        return {
            "needs_assessment_id": na_id,
            "needs_complete": False,
            "needs_rounds": rounds,
            "last_input": None,
            "handoff_reason": None,
            "waiting_for": "NEEDS",
            "messages": [say(text, now)],
        }

    async def check_eligibility(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        m, today, step = state["market"], self.now().date(), _step(config)
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            na = await uow.needs.get(_uuid(state["needs_assessment_id"]))
            objects = [
                object_view(o)
                for o in await uow.objects.list(_uuid(i) for i in state.get("insurable_object_ids") or [])
            ]
            products = await uow.catalog.active_products(m)
            rules_by_product: dict[str, list[RuleSpec]] = {}
            for r in await uow.catalog.rules():
                rules_by_product.setdefault(r.product_code, []).append(
                    RuleSpec(
                        str(r.rule_id),
                        r.subject,
                        r.attribute,
                        r.operator,
                        r.value,
                        r.failure_reason_code,
                        r.description,
                    )
                )
            rec_ids, eligible, reasons = [], 0, []
            needs = needs_view(na)
            for product in products:
                if product.sale_effective_date > today or (
                    product.sale_expiration_date and product.sale_expiration_date < today
                ):
                    continue
                candidates = [o for o in objects if o["object_type"] == product.insurable_object_type]
                chosen, outcome = None, None
                for obj in candidates:
                    res = evaluate_product(
                        rules_by_product.get(product.product_code, []),
                        party=party_view(party),
                        needs=needs,
                        obj=obj,
                        today=today,
                    )
                    if chosen is None or res.eligible:
                        chosen, outcome = obj, res
                    if res.eligible:
                        break
                if outcome is None:
                    result, failed_ids = "INELIGIBLE", []
                    failed = [f"NO_INSURABLE_OBJECT: no {product.insurable_object_type.lower()} to insure"]
                else:
                    result = "ELIGIBLE" if outcome.eligible else "INELIGIBLE"
                    failed_ids, failed = outcome.failed_rule_ids, outcome.failed_reasons
                rec_id = node_uuid(_thread(config), "check_eligibility", step, product.product_code)
                await uow.recommendations.save(
                    Recommendation(
                        recommendation_id=rec_id,
                        session_id=_uuid(state["session_id"]),
                        party_id=party.party_id,
                        needs_assessment_id=na.needs_assessment_id,
                        product_code=product.product_code,
                        insurable_object_id=_uuid(chosen["insurable_object_id"]) if chosen else None,
                        rank=0,
                        score=0.0,
                        eligibility_result=result,
                        failed_rule_ids=failed_ids,
                        failed_reasons=failed,
                        status="PROPOSED",
                        created_at=self.now(),
                    )
                )
                rec_ids.append(str(rec_id))
                if result == "ELIGIBLE":
                    eligible += 1
                else:
                    reasons.append(f"{product.marketing_name}: {failed[0].split(': ', 1)[-1]}")
        for rec_id in rec_ids:
            await self._touch(state, "recommendation", rec_id)
        out: dict[str, Any] = {
            "stage": "RECOMMENDATION",
            "recommendation_ids": rec_ids,
            "quote_ids": {},
            "eligible_count": eligible,
            "decision": None,
        }
        if eligible == 0:
            text = t(
                lang,
                "지금 알려 주신 내용으로는 가입할 수 있는 상품이 없습니다. 상담원이 이어서 도와드릴게요.\n",
                "Based on what you told me, none of our products fit right now. An agent will follow up with you.\n",
            ) + "\n".join(f"- {r}" for r in reasons)
            out["handoff_reason"] = "NO_ELIGIBLE_PRODUCT"
            out["messages"] = [say(text, self.now())]
        return out

    async def rank_products(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        async with self.d.uow() as uow:
            na = await uow.needs.get(_uuid(state["needs_assessment_id"]))
            recs = await self._recs(uow, state)
            tms: dict[str, list[dict]] = {}
            for tm in await uow.catalog.target_markets():
                tms.setdefault(tm.product_code, []).append(
                    {"attribute": tm.attribute, "values": tm.values, "weight": tm.weight, "rationale": tm.rationale}
                )
            needs = needs_view(na)
            items = []
            for r in recs:
                score, _ = target_market_score(tms.get(r.product_code, []), needs)
                items.append(
                    {
                        "rec": r,
                        "score": score,
                        "eligibility_result": r.eligibility_result,
                        "product_code": r.product_code,
                    }
                )
            for rank, item in enumerate(rank_order(items), start=1):
                item["rec"].rank = rank
                item["rec"].score = item["score"]
        return {}

    async def quote_premium(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        now, step = self.now(), _step(config)
        quote_ids: dict[str, str] = {}
        async with self.d.uow() as uow:
            eligible = 0
            for rec in await self._recs(uow, state):
                if rec.eligibility_result != "ELIGIBLE":
                    continue
                product = await uow.catalog.product(rec.product_code)
                obj = await uow.objects.get(rec.insurable_object_id)
                try:
                    quote = self._price(product, obj, now)
                except RatingError as exc:
                    rec.eligibility_result = "INELIGIBLE"
                    rec.failed_reasons = [*rec.failed_reasons, f"RATING_ERROR: {exc}"]
                    continue
                quote.quote_id = node_uuid(_thread(config), "quote_premium", step, str(rec.recommendation_id))
                quote.recommendation_id = rec.recommendation_id
                await uow.quotes.save(quote)
                quote_ids[str(rec.recommendation_id)] = str(quote.quote_id)
                eligible += 1
        for q in quote_ids.values():
            await self._touch(state, "quote", q)
        out: dict[str, Any] = {"quote_ids": quote_ids, "eligible_count": eligible}
        if eligible == 0:
            out["handoff_reason"] = "NO_ELIGIBLE_PRODUCT"
        return out

    def _price(self, product: Product, obj: InsurableObject, now: datetime) -> Quote:
        attrs = obj.attributes or {}
        premium = compute_premium(product.rating, attrs)
        start, end = compute_term(product.term_rule, attrs, now.date())
        return Quote(
            product_code=product.product_code,
            insurable_object_id=obj.insurable_object_id,
            coverages=[
                {"code": c["code"], "limit_minor": c.get("limit_minor"), "deductible_minor": c.get("deductible_minor")}
                for c in product.coverages
            ],
            term_start_date=start,
            term_end_date=end,
            premium_minor=premium.premium_minor,
            billing_period=product.billing_period,
            currency=product.currency,
            rating_inputs=_jsonable(premium.rating_inputs),
            status="ISSUED",
            valid_until=quote_valid_until(now, start),
            created_at=now,
        )

    async def _recs(self, uow: UnitOfWork, state: dict[str, Any]) -> list[Recommendation]:
        ids = [_uuid(i) for i in state.get("recommendation_ids") or []]
        if not ids:
            return []
        return sorted(await uow.recommendations.list(ids), key=lambda r: (r.rank or 0, r.product_code))

    async def explain_recommendation(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            na = await uow.needs.get(_uuid(state["needs_assessment_id"]))
            recs = [r for r in await self._recs(uow, state) if r.eligibility_result == "ELIGIBLE"]
            products = {r.product_code: await uow.catalog.product(r.product_code) for r in recs}
            quotes = {
                str(r.recommendation_id): await uow.quotes.get(_uuid(state["quote_ids"][str(r.recommendation_id)]))
                for r in recs
            }
            tms: dict[str, list[dict]] = {}
            for tm in await uow.catalog.target_markets():
                tms.setdefault(tm.product_code, []).append(
                    {"attribute": tm.attribute, "values": tm.values, "weight": tm.weight, "rationale": tm.rationale}
                )
        needs = needs_view(na)
        lines, fallback = [], {}
        for r in recs:
            p, q = products[r.product_code], quotes[str(r.recommendation_id)]
            _, grounds = target_market_score(tms.get(r.product_code, []), needs)
            fallback[str(r.recommendation_id)] = " ".join(grounds) or p.marketing_name
            lines.append(
                f"- recommendation_id: {r.recommendation_id}\n"
                f"  product: {p.marketing_name} ({p.product_type}), rank {r.rank}\n"
                f"  price: {price_label(lang, q.premium_minor, q.currency, q.billing_period)}, "
                f"cover {q.term_start_date} to {q.term_end_date}\n"
                f"  grounds: {json.dumps(grounds, ensure_ascii=False)}"
            )
        instructions = (
            "Write one short, customer-facing reason (1-2 sentences) for each recommended product, "
            "using only the listed grounds and the customer's needs. Do not invent coverage or prices. "
            "Return every recommendation_id exactly as given.\n"
            f"Customer needs: {json.dumps(needs, ensure_ascii=False, default=str)}\n"
            "Recommendations:\n" + "\n".join(lines)
        )
        ext = await self.d.llm.extract(
            "explain_recommendation",
            RecommendationRationale,
            [self._system(state, party, instructions), HumanMessage("Explain these recommendations.")],
        )
        by_id = {str(i.get("recommendation_id")): str(i.get("rationale") or "") for i in ext.items}
        async with self.d.uow() as uow:
            out_lines = []
            for r in recs:
                rec = await uow.recommendations.get(r.recommendation_id)
                rec.rationale = by_id.get(str(r.recommendation_id)) or fallback[str(r.recommendation_id)]
                q = quotes[str(r.recommendation_id)]
                out_lines.append(
                    f"{rec.rank}. {products[r.product_code].marketing_name} — "
                    f"{price_label(lang, q.premium_minor, q.currency, q.billing_period)}\n   {rec.rationale}"
                )
        for r in recs:
            await self._touch(state, "recommendation", r.recommendation_id)
        text = (
            t(lang, "추천 상품입니다:\n", "Here's what I recommend:\n")
            + "\n".join(out_lines)
            + t(
                lang,
                "\n\n가입할 상품을 고르시거나, 답을 바꾸거나, 가입하지 않을 수 있어요.",
                "\n\nChoose one to apply, change your answers, or decline.",
            )
        )
        return {"waiting_for": "DECISION", "messages": [say(text, self.now())]}

    async def await_decision(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        value = interrupt({"waiting_for": "DECISION"})
        lang, now, actor = locale_of(state), self.now(), state.get("actor") or "CUSTOMER"
        decision = value.get("decision")
        chosen_id = value.get("recommendation_id")
        extra_text = str(value.get("text") or "").strip()
        async with self.d.uow() as uow:
            recs = await self._recs(uow, state)
            eligible = [r for r in recs if r.eligibility_result == "ELIGIBLE" and r.status == "PROPOSED"]
            quotes = {k: await uow.quotes.get(_uuid(v)) for k, v in (state.get("quote_ids") or {}).items()}
            if decision == "ACCEPT":
                rec = next((r for r in eligible if str(r.recommendation_id) == str(chosen_id)), None)
                rec = rec or (eligible[0] if eligible else None)
                if rec is None:
                    raise LookupError("no proposed recommendation to accept")
                rec.status, rec.decided_by, rec.decided_at = "ACCEPTED", actor, now
                quote = quotes.get(str(rec.recommendation_id))
                if quote is not None:
                    quote.status = "ACCEPTED"
                product = await uow.catalog.product(rec.product_code)
                text = t(lang, f"{product.marketing_name}에 가입할게요.", f"I'd like {product.marketing_name}.")
                touched = [("recommendation", rec.recommendation_id)]
            elif decision == "DECLINE":
                for r in eligible:
                    r.status, r.decided_by, r.decided_at = "DECLINED", actor, now
                text = t(lang, "가입하지 않을게요.", "No thanks, I'll pass.")
                touched = [("recommendation", r.recommendation_id) for r in eligible]
            else:  # CHANGE
                for r in recs:
                    if r.status in ("PROPOSED", "ACCEPTED"):
                        r.status = "EXPIRED"
                for q in quotes.values():
                    if q is not None:
                        q.status = "EXPIRED"
                text = extra_text or t(lang, "답을 바꾸고 싶어요.", "I'd like to change my answers.")
                touched = [("recommendation", r.recommendation_id) for r in recs]
        for entity_type, entity_id in touched:
            await self._touch(state, entity_type, entity_id)

        input_type = "NEEDS" if decision == "CHANGE" and extra_text else "DECISION"
        out: dict[str, Any] = {
            "decision": decision,
            "waiting_for": None,
            "messages": [
                human(
                    text if decision == "CHANGE" or not extra_text else f"{text} {extra_text}",
                    now,
                    actor=actor,
                    input_type=input_type,
                )
            ],
        }
        if decision == "DECLINE":
            out["stage"] = "DECLINED"
            out["messages"].append(
                say(t(lang, "알겠습니다. 언제든 다시 찾아 주세요.", "Understood. You're welcome back any time."), now)
            )
        elif decision == "CHANGE":
            out.update(
                stage="PROFILING",
                needs_complete=False,
                needs_rounds=0,
                recommendation_ids=[],
                quote_ids={},
                eligible_count=0,
                last_input="NEEDS" if extra_text else None,
            )
        return out

    async def open_application(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang, now, step, actor = locale_of(state), self.now(), _step(config), state.get("actor") or "CUSTOMER"
        app_id = node_uuid(_thread(config), "open_application", step)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            rec = next((r for r in await self._recs(uow, state) if r.status == "ACCEPTED"), None)
            if rec is None:
                raise LookupError("no accepted recommendation")
            product = await uow.catalog.product(rec.product_code)
            obj = await uow.objects.get(rec.insurable_object_id)
            quote = await uow.quotes.get(_uuid(state["quote_ids"][str(rec.recommendation_id)]))
            if quote.valid_until < now:
                # The accepted price lapsed while the customer was away: re-price at today's rules.
                fresh = self._price(product, obj, now)
                fresh.quote_id = node_uuid(_thread(config), "open_application", step, "requote")
                fresh.recommendation_id = rec.recommendation_id
                fresh.status = "ACCEPTED"
                quote.status = "EXPIRED"
                quote = await uow.quotes.save(fresh)
            answers = prefill_answers(product.required_application_fields, object_view(obj), party, now.date())
            await uow.applications.save(
                Application(
                    application_id=app_id,
                    session_id=_uuid(state["session_id"]),
                    recommendation_id=rec.recommendation_id,
                    quote_id=quote.quote_id,
                    product_code=product.product_code,
                    insurable_object_id=obj.insurable_object_id,
                    status="DRAFT",
                    answers=_jsonable(answers),
                    missing_fields=missing_answers(product.required_application_fields, answers),
                    captured_by=actor,
                )
            )
            quote_ids = {**state["quote_ids"], str(rec.recommendation_id): str(quote.quote_id)}
            name = product.marketing_name
        await self._touch(state, "application", app_id)
        text = t(lang, f"{name} 청약서를 작성할게요.", f"Great choice. Let's complete your {name} application.")
        return {
            "stage": "APPLICATION",
            "application_id": str(app_id),
            "quote_ids": quote_ids,
            "parties_complete": False,
            "answers_complete": False,
            "confirmed": None,
            "last_input": None,
            "messages": [say(text, now)],
        }

    async def collect_parties(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang, now, step = locale_of(state), self.now(), _step(config)
        if state.get("last_input") != "PARTIES":
            text = t(
                lang,
                "피보험자(보장받는 분)와 보험료를 내는 분이 모두 본인인가요? 다른 분이 있다면 그분의 역할"
                "(피보험자/납입자), 이름, 생년월일을 알려 주세요.",
                "Are you both the insured person and the payer? If someone else is, tell me their role "
                "(insured or payer), full name and date of birth.",
            )
            return {"parties_complete": False, "waiting_for": "PARTIES", "messages": [say(text, now)]}

        async with self.d.uow() as uow:
            party = await self._party(uow, state)
        instructions = (
            "Decide whether the applicant is also the insured person and the payer. If not, list the "
            "other people with their role (INSURED or PAYER), full_name and date_of_birth (ISO 8601)."
        )
        texts = latest_texts(state.get("messages") or [], ("PARTIES",))
        ext = await self.d.llm.extract(
            "collect_parties",
            PartiesExtraction,
            [self._system(state, party, instructions), HumanMessage(texts[-1] if texts else "-")],
        )
        others = [] if ext.all_self else [p for p in ext.parties if p.get("role") in ("INSURED", "PAYER")]
        if any(not str(p.get("full_name") or "").strip() for p in others):
            text = t(
                lang,
                "다른 분의 이름과 생년월일을 알려 주세요.",
                "Please tell me the other person's full name and date of birth.",
            )
            return {
                "parties_complete": False,
                "last_input": None,
                "waiting_for": "PARTIES",
                "messages": [say(text, now)],
            }

        app_id = _uuid(state["application_id"])
        async with self.d.uow() as uow:
            roles: dict[str, uuid.UUID] = {"POLICYHOLDER": party.party_id}
            names = []
            for i, p in enumerate(others):
                pid = node_uuid(_thread(config), "collect_parties", step, f"{p['role']}:{i}")
                await uow.parties.save(
                    Party(
                        party_id=pid,
                        party_type="PERSON",
                        full_name=str(p["full_name"]).strip(),
                        date_of_birth=parse_date(p.get("date_of_birth")),
                        verification_status="UNVERIFIED",
                        verification_attempts=0,
                    )
                )
                roles.setdefault(p["role"], pid)
                names.append(f"{p['role']}: {p['full_name']}")
            roles.setdefault("INSURED", party.party_id)
            roles.setdefault("PAYER", party.party_id)
            await uow.applications.set_parties(app_id, roles)
            # Traveller fields follow the insured person.
            application = await uow.applications.get(app_id)
            product = await uow.catalog.product(application.product_code)
            insured = await uow.parties.get(roles["INSURED"])
            obj = await uow.objects.get(application.insurable_object_id)
            prefill = prefill_answers(product.required_application_fields, object_view(obj), insured, now.date())
            answers = dict(application.answers or {})
            for key in ("traveler_name", "traveler_date_of_birth", "traveler_age"):
                if key in prefill:
                    answers[key] = prefill[key]
                elif key in answers and roles["INSURED"] != party.party_id:
                    answers.pop(key)
            application.answers = _jsonable(answers)
            application.missing_fields = missing_answers(product.required_application_fields, answers)
        await self._touch(state, "application", app_id)
        text = t(
            lang,
            "당사자 정보를 확인했습니다" + (f" ({', '.join(names)})." if names else " — 모두 본인입니다."),
            "Got it" + (f" ({', '.join(names)})." if names else " — you're the insured and the payer."),
        )
        return {"parties_complete": True, "last_input": None, "messages": [say(text, now)]}

    async def collect_answers(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang, now, actor = locale_of(state), self.now(), state.get("actor") or "CUSTOMER"
        app_id = _uuid(state["application_id"])
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            application = await uow.applications.get(app_id)
            product = await uow.catalog.product(application.product_code)
        required = list(product.required_application_fields)
        answers = dict(application.answers or {})
        got_input = state.get("last_input") == "ANSWERS"

        if got_input:
            missing_now = missing_answers(required, answers)
            instructions = (
                "Extract application answers from the customer's latest message into AnswersExtraction. "
                f"Use exactly these field names: {json.dumps(required)}. Dates ISO 8601, money in minor units.\n"
                f"Answers so far: {json.dumps(answers, ensure_ascii=False, default=str)}\n"
                f"Still missing: {json.dumps(missing_now)}"
            )
            texts = latest_texts(state.get("messages") or [], ("ANSWERS",))
            ext = await self.d.llm.extract(
                "collect_answers",
                AnswersExtraction,
                [self._system(state, party, instructions), HumanMessage(texts[-1] if texts else "-")],
            )
            answers.update({k: v for k, v in (ext.answers or {}).items() if v not in (None, "")})
            answers = apply_answer_aliases(required, answers)

        missing = missing_answers(required, answers)
        rounds = int(state.get("answers_rounds") or 0) + (1 if got_input else 0)
        async with self.d.uow() as uow:
            application = await uow.applications.get(app_id)
            application.answers = _jsonable(answers)
            application.missing_fields = missing
            application.status = "INCOMPLETE" if missing else "COMPLETE"
            application.captured_by = actor
        await self._touch(state, "application", app_id)

        base = {
            "last_input": None,
            "handoff_reason": None,
            "answers_rounds": rounds,
            "confirmed": None if got_input else state.get("confirmed"),
        }
        if missing and rounds >= MAX_ANSWERS_ROUNDS:
            text = t(
                lang,
                "청약에 필요한 정보를 다 받지 못해 상담원을 연결해 드릴게요.",
                "I still can't complete the application, so I'm bringing in an agent to help.",
            )
            return {
                **base,
                "answers_complete": False,
                "handoff_reason": "ANSWERS_INCOMPLETE",
                "messages": [say(text, now)],
            }
        if missing:
            text = t(
                lang,
                f"청약을 위해 {field_list(lang, missing)}을(를) 알려 주세요.",
                f"To complete the application, please provide {field_list(lang, missing)}.",
            )
            return {**base, "answers_complete": False, "waiting_for": "ANSWERS", "messages": [say(text, now)]}
        if state.get("confirmed") is False and not got_input:
            text = t(lang, "어떤 내용을 고칠까요?", "What would you like to change?")
            return {**base, "answers_complete": False, "waiting_for": "ANSWERS", "messages": [say(text, now)]}
        return {**base, "answers_complete": True, "answers_rounds": 0}

    async def summarize_application(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang, now = locale_of(state), self.now()
        app_id = _uuid(state["application_id"])
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            application = await uow.applications.get(app_id)
            product = await uow.catalog.product(application.product_code)
            quote = await uow.quotes.get(application.quote_id)
            parties = await self._application_parties(uow, app_id)
        facts = {
            "product": product.marketing_name,
            "price": price_label(lang, quote.premium_minor, quote.currency, quote.billing_period),
            "cover": f"{quote.term_start_date} to {quote.term_end_date}",
            "parties": parties,
            "answers": application.answers,
        }
        instructions = (
            "Write a short plain-language summary of this insurance application for the customer to "
            "confirm before submission. Use only these facts:\n" + json.dumps(facts, ensure_ascii=False, default=str)
        )
        ext = await self.d.llm.extract(
            "summarize_application",
            ApplicationSummary,
            [self._system(state, party, instructions), HumanMessage("Summarize my application.")],
        )
        async with self.d.uow() as uow:
            application = await uow.applications.get(app_id)
            application.summary = ext.summary
            application.status = "COMPLETE"
        await self._touch(state, "application", app_id)
        text = ext.summary + t(lang, "\n\n이대로 제출할까요?", "\n\nShall I submit this application?")
        return {"waiting_for": "CONFIRM", "confirmed": None, "messages": [say(text, now)]}

    async def _application_parties(self, uow: UnitOfWork, app_id: uuid.UUID) -> list[dict[str, Any]]:
        return [
            {"role": role, "full_name": p.full_name, "date_of_birth": iso(p.date_of_birth)}
            for role, p in await uow.applications.parties(app_id)
        ]

    async def confirm_summary(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        value = interrupt({"waiting_for": "CONFIRM"})
        lang, now, actor = locale_of(state), self.now(), state.get("actor") or "CUSTOMER"
        confirmed = bool(value.get("confirmed"))
        extra = str(value.get("text") or "").strip()
        if confirmed:
            msg = human(
                extra or t(lang, "네, 제출해 주세요.", "Yes, please submit."), now, actor=actor, input_type="CONFIRM"
            )
            return {"confirmed": True, "waiting_for": None, "messages": [msg]}
        msg = human(
            extra or t(lang, "고칠 내용이 있어요.", "I need to change something."),
            now,
            actor=actor,
            input_type="ANSWERS" if extra else "CONFIRM",
        )
        return {
            "confirmed": False,
            "answers_complete": False,
            "waiting_for": None,
            "last_input": "ANSWERS" if extra else None,
            "messages": [msg],
        }

    async def submit_application(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang, now = locale_of(state), self.now()
        app_id = _uuid(state["application_id"])
        async with self.d.uow() as uow:
            application = await uow.applications.get(app_id)
            quote = await uow.quotes.get(application.quote_id)
            obj = await uow.objects.get(application.insurable_object_id)
            parties = await self._application_parties(uow, app_id)
        if application.submission_ref:
            ref = application.submission_ref
        else:
            # No ID numbers or contact details: the contract system does not need them.
            payload = {
                "application_id": str(app_id),
                "product_code": application.product_code,
                "quote": {
                    "quote_id": str(quote.quote_id),
                    "premium_minor": quote.premium_minor,
                    "currency": quote.currency,
                    "billing_period": quote.billing_period,
                    "term_start_date": iso(quote.term_start_date),
                    "term_end_date": iso(quote.term_end_date),
                    "coverages": quote.coverages,
                },
                "parties": parties,
                "insurable_object": {"object_type": obj.object_type, "attributes": obj.attributes} if obj else None,
                "answers": application.answers,
                "summary": application.summary,
            }
            res = await self.d.contract.submit_application(str(app_id), _jsonable(payload))
            ref = res["submission_ref"]
            async with self.d.uow() as uow:
                application = await uow.applications.get(app_id)
                application.submission_ref = ref
                application.status = "SUBMITTED"
                application.submitted_at = now
        await self._touch(state, "application", app_id)
        text = t(
            lang,
            f"청약을 제출했습니다. 접수번호는 {ref}입니다. 심사 결과는 따로 안내해 드릴게요.",
            f"Your application is submitted. Your reference number is {ref}. We'll be in touch "
            "with the underwriting decision.",
        )
        return {"stage": "SUBMITTED", "waiting_for": None, "messages": [say(text, now)]}

    async def human_handoff(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        err = state.get("last_error")
        reason = "ERROR" if err else state.get("handoff_reason") or "ERROR"
        out: dict[str, Any] = {
            "stage": "HANDOFF",
            "waiting_for": "AGENT",
            "handoff_reason": reason,
            "handoff_resolution": None,
            "resume_stage": state.get("stage") if state.get("stage") != "HANDOFF" else state.get("resume_stage"),
            "resume_node": err["node"] if err else None,
        }
        if err:
            lang = locale_of(state)
            out["messages"] = [
                note(f"Handoff: {err['node']} failed after {err['attempts']} attempts ({err['kind']}).", self.now()),
                say(
                    t(
                        lang,
                        "처리 중 문제가 생겨 상담원을 연결해 드릴게요. 입력하신 내용은 저장돼 있습니다.",
                        "Something went wrong on our side, so I'm connecting you with an agent. "
                        "Everything you've entered is saved.",
                    ),
                    self.now(),
                ),
            ]
        return out

    async def await_agent(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        value = interrupt({"waiting_for": "AGENT", "reason": state.get("handoff_reason")})
        lang, now = locale_of(state), self.now()
        resolution = value.get("resolution")
        reason = state.get("handoff_reason")
        agent_note = str(value.get("note") or "").strip()
        msgs: list[BaseMessage] = [
            human(agent_note or f"Agent resolution: {resolution}", now, actor="AGENT", input_type="AGENT")
        ]
        out: dict[str, Any] = {
            "handoff_resolution": resolution,
            "waiting_for": None,
            "last_error": None,
        }
        if reason != "ERROR":
            # An ERROR handoff re-runs the failed node with the input it had; others start fresh.
            out["last_input"] = None
        if resolution == "END":
            out["stage"] = "WITHDRAWN"
            msgs.append(say(t(lang, "상담원이 상담을 종료했습니다.", "The agent has closed this session."), now))
        elif reason == "IDENTITY_FAILED":
            async with self.d.uow() as uow:
                party = await self._party(uow, state)
                if resolution == "VERIFIED":
                    party.verification_status = "VERIFIED"
                    party.verification_method = "AGENT"
                    party.verified_at = now
                else:
                    party.verification_status = "UNVERIFIED"
                    party.verification_attempts = 0
            await self._touch(state, "party", state["party_id"])
            if resolution == "VERIFIED":
                msgs.append(
                    say(t(lang, "상담원이 본인 확인을 마쳤습니다.", "An agent has verified your identity."), now)
                )
        elif reason in ("NO_ELIGIBLE_PRODUCT", "NEEDS_INCOMPLETE"):
            out.update(stage="PROFILING", needs_complete=False, needs_rounds=0)
        elif reason == "ANSWERS_INCOMPLETE":
            out.update(stage="APPLICATION", answers_complete=False, answers_rounds=0)
        elif reason == "ERROR":
            out["stage"] = state.get("resume_stage") or "IDENTITY"
        out["messages"] = msgs
        return out
