"""Stage 2, customer profiling: partner purchases (with consent), then the needs assessment the LLM extracts
and code checks for completeness."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from onboarding_agent.flows.base import (
    DomainModule,
    Flow,
    HandoffKind,
    InputKind,
    as_uuid,
    jsonable,
    latest_texts,
    step_of,
    thread_of,
)
from onboarding_agent.ids import node_uuid
from onboarding_agent.llm.schemas import NeedsExtraction
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import field_list, locale_of, say, t
from onboarding_core.needs.models import InsurableObject, NeedsAssessment
from onboarding_core.needs.rules import compute_needs_missing, described_objects, merge_needs, needs_view

# NEEDS answers that leave fields missing before an agent takes over.
MAX_NEEDS_ROUNDS = 3


async def restart_profiling(
    flow: Flow, state: dict[str, Any], resolution: str | None, now: datetime
) -> tuple[list[BaseMessage], dict[str, Any]]:
    """Back to the needs assessment with a fresh round count, after an agent helped out."""
    return [], {"stage": "PROFILING", "needs_complete": False, "needs_rounds": 0}


def resume_profiling(state: dict[str, Any]) -> str:
    return "assess_needs"


class ProfilingFlow(Flow):
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
                    obj_id = node_uuid(thread_of(config), "fetch_purchases", 0, str(p.get("order_id")))
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
                await uow.needs.get(as_uuid(state["needs_assessment_id"])) if state.get("needs_assessment_id") else None
            )
            objects = await uow.objects.list(as_uuid(i) for i in state.get("insurable_object_ids") or [])
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
        values = merge_needs(base, ext.model_dump(), m)
        partner_types = {o.object_type for o in partner_objects}
        missing = compute_needs_missing(values, market=m, partner_object_types=partner_types)
        step = step_of(config)

        async with self.d.uow() as uow:
            if current is not None and current.completed_at is None:
                na = await uow.needs.get(current.needs_assessment_id)
            else:
                na_id = node_uuid(thread_of(config), "assess_needs", step)
                na = await uow.needs.get(na_id)
                if na is None:
                    version = await uow.needs.latest_version(party.party_id) + 1
                    na = NeedsAssessment(
                        needs_assessment_id=na_id,
                        party_id=party.party_id,
                        session_id=as_uuid(state["session_id"]),
                        version=version,
                        created_at=now,
                    )
                    await uow.needs.add(na)
            na.age_range = values.get("age_range")
            na.occupation = values.get("occupation")
            na.residence_country = values.get("residence_country")
            na.existing_coverage = jsonable(values.get("existing_coverage") or [])
            na.objectives = list(values.get("objectives") or [])
            na.device = jsonable(values.get("device"))
            na.trip = jsonable(values.get("trip"))
            na.captured_by = actor
            na.missing_fields = missing
            ids = [str(o.insurable_object_id) for o in partner_objects]
            if not missing:
                na.completed_at = now
                for key, object_type, attrs in described_objects(
                    values, partner_object_types=partner_types, today=now.date()
                ):
                    obj_id = node_uuid(thread_of(config), "assess_needs", step, key)
                    await uow.objects.save(
                        InsurableObject(
                            insurable_object_id=obj_id,
                            owner_party_id=party.party_id,
                            object_type=object_type,
                            source=actor,
                            attributes=jsonable(attrs),
                        )
                    )
                    ids.append(str(obj_id))
            na_id = str(na.needs_assessment_id)
        await self._touch(state, "needs_assessment", na_id)

        if not missing:
            for obj_id in ids:
                await self._touch(state, "insurable_object", obj_id)
            text = t(
                lang,
                "감사합니다. 가입할 수 있는 상품을 확인해 볼게요.",
                "Thanks — let me check which products fit you.",
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


def after_fetch_purchases(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "assess_needs"


def after_assess_needs(state: dict[str, Any]) -> str:
    if has_error(state) or state.get("handoff_reason") == "NEEDS_INCOMPLETE":
        return HANDOFF
    return "check_eligibility" if state.get("needs_complete") else "ask_customer"


MODULE = DomainModule(
    name="profiling",
    flow=ProfilingFlow,
    edges={
        "fetch_purchases": after_fetch_purchases,
        "assess_needs": after_assess_needs,
    },
    retrying=frozenset({"assess_needs", "fetch_purchases"}),
    inputs={"NEEDS": InputKind("assess_needs")},
    handoffs={"NEEDS_INCOMPLETE": HandoffKind(resume_profiling, restart_profiling)},
)
