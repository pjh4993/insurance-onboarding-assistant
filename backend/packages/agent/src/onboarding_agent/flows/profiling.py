"""Stage 2, customer profiling: partner purchases (with consent), then the needs assessment, asked one small
form (topic) at a time. A form's fields merge straight into the assessment; free text goes through the LLM
extraction, together with the customer's first message. Code checks for completeness."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, get_args

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from onboarding_agent.config import TextSpec
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
from onboarding_agent.flows.forms import FormField, form_copy, form_spec, render
from onboarding_agent.ids import node_uuid
from onboarding_agent.llm.schemas import AgeRange, NeedsExtraction, Objective
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import locale_of, money, say
from onboarding_core.catalog.seed import PRODUCTS
from onboarding_core.needs.models import InsurableObject, NeedsAssessment
from onboarding_core.needs.rules import compute_needs_missing, described_objects, merge_needs, needs_view
from onboarding_core.product_lines import LINES, line_for_object_type
from onboarding_core.product_lines.base import BLANK
from onboarding_core.product_lines.device import DEVICE_CATEGORIES

# NEEDS answers that fill none of the missing fields before an agent takes over. Answering form after form
# fills fields every time, so only answers that add nothing count.
MAX_NEEDS_ROUNDS = 3

MARKET_CURRENCY = {j: p["currency"] for p in PRODUCTS for j in p["jurisdictions"]}
MINOR_PER_UNIT = {"KRW": 1, "USD": 100}  # KRW has no subunit


@dataclass(frozen=True)
class NeedsField:
    form: FormField
    path: str  # the needs value it fills, as compute_needs_missing names it: "age_range", "device.model"
    optional: bool = False  # shown even when not required
    money: bool = False  # typed in whole units of the market's currency, stored in minor units


# The needs forms. Each field compute_needs_missing can report belongs to one of them; a product line's topic
# is named after its needs key. Which fields a form shows, and which are required, follow the line's rules.
NEEDS_TOPICS: dict[str, tuple[NeedsField, ...]] = {
    "coverage": (NeedsField(FormField("objectives", "multiselect", get_args(Objective)), "objectives"),),
    "person": (
        NeedsField(FormField("age_range", "select", get_args(AgeRange)), "age_range"),
        NeedsField(FormField("residence_country", "text", placeholder=True), "residence_country"),
        NeedsField(FormField("occupation", "text"), "occupation", optional=True),
    ),
    "device": (
        NeedsField(FormField("device_category", "select", DEVICE_CATEGORIES), "device.device_category"),
        NeedsField(FormField("manufacturer", "text", placeholder=True), "device.manufacturer", optional=True),
        NeedsField(FormField("model", "text", placeholder=True), "device.model", optional=True),
        NeedsField(FormField("purchase_date", "date"), "device.purchase_date", optional=True),
        NeedsField(FormField("purchase_price", "number", placeholder=True), "device.purchase_price_minor", money=True),
    ),
    "trip": (
        NeedsField(FormField("destination_countries", "text", placeholder=True), "trip.destination_countries"),
        NeedsField(FormField("departure_date", "date"), "trip.departure_date"),
        NeedsField(FormField("return_date", "date"), "trip.return_date"),
        NeedsField(FormField("trip_cost", "number", placeholder=True), "trip.trip_cost_minor", money=True),
    ),
}
NEEDS_FIELDS = {f.form.name: f for fields in NEEDS_TOPICS.values() for f in fields}
TOPIC_OF = {f.path: topic for topic, fields in NEEDS_TOPICS.items() for f in fields}


def interest_topic(product_type: str | None) -> str | None:
    """The needs topic of the product line a catalog product type insures."""
    for p in PRODUCTS:
        if p["product_type"] == product_type:
            return line_for_object_type(p["insurable_object_type"]).needs_key
    return None


def interest_objective(product_type: str | None) -> str | None:
    """The objective the catalog's products of a type target most."""
    weighted = [
        (tm["weight"], tm["values"][0])
        for p in PRODUCTS
        if p["product_type"] == product_type
        for tm in p.get("target_markets") or []
        if tm["attribute"] == "objectives" and tm["values"]
    ]
    return max(weighted)[1] if weighted else None


def next_topic(missing: list[str], product_interest: str | None) -> str | None:
    """The form to ask next: what to protect first (it decides which lines apply), then the line the customer
    came for, the person, and any other line."""
    topics = {TOPIC_OF[f] for f in missing if f in TOPIC_OF}
    order = ["coverage", interest_topic(product_interest), "person", *(line.needs_key for line in LINES)]
    return next((t for t in order if t in topics), None)


def required_paths(values: dict[str, Any], market: str) -> set[str]:
    required = {"age_range", "residence_country", "objectives"}
    for line in LINES:
        described = values.get(line.needs_key) or {}
        required |= {f"{line.needs_key}.{key}" for key in line.required_needs(market, described)}
    return required


def value_at(values: dict[str, Any], path: str) -> Any:
    head, _, key = path.partition(".")
    return (values.get(head) or {}).get(key) if key else values.get(head)


def minor_per_unit(market: str) -> int:
    return MINOR_PER_UNIT.get(MARKET_CURRENCY.get(market, "USD"), 100)


def to_minor(value: Any, market: str) -> int | None:
    try:
        return round(float(str(value).replace(",", "")) * minor_per_unit(market))
    except ValueError:
        return None


def structured_needs(fields: dict[str, Any], market: str) -> dict[str, Any]:
    """A form's answers in the shape of a NeedsExtraction, for merge_needs. Unknown names are ignored."""
    out: dict[str, Any] = {}
    for name, value in fields.items():
        spec = NEEDS_FIELDS.get(name)
        if spec is None or value in BLANK:
            continue
        if spec.money:
            value = to_minor(value, market)
        elif name == "destination_countries":
            items = value if isinstance(value, list) else str(value).split(",")
            value = [str(c).strip().upper() for c in items if str(c).strip()]
        elif name == "residence_country":
            value = str(value).strip().upper()
        elif spec.form.kind == "multiselect":
            value = [v for v in (value if isinstance(value, list) else [value]) if v in spec.form.options]
        elif isinstance(value, str):
            value = value.strip()
        if value in BLANK:
            continue
        head, _, key = spec.path.partition(".")
        if key:
            out.setdefault(head, {})[key] = value
        else:
            out[head] = value
    return out


async def record_needs(
    flow: Flow, state: dict[str, Any], value: dict[str, Any], now: datetime
) -> tuple[str, dict[str, Any]]:
    """A needs answer: a form's fields, free text, or both. assess_needs takes it from `needs_input`."""
    lang, market = locale_of(state), state["market"]
    fields = dict(value.get("fields") or {})
    text = str(value.get("text") or "").strip()
    parts = []
    if fields:
        currency = MARKET_CURRENCY.get(market, "USD")
        shown = {
            name: money(minor, currency)
            for name, v in fields.items()
            if name in NEEDS_FIELDS and NEEDS_FIELDS[name].money and (minor := to_minor(v, market)) is not None
        }
        forms = [f.form for f in NEEDS_FIELDS.values()]
        parts.append(render(flow, lang, "profiling", forms, fields, shown))
    if text:
        parts.append(text)
    pending = {"topic": value.get("topic"), "fields": fields, "text": text}
    return "\n".join(p for p in parts if p) or "-", {"needs_input": pending}


async def needs_form(flow: Flow, state: dict[str, Any], lang: str) -> dict[str, Any] | None:
    """The form for the needs topic being asked: the topic's required fields plus its optional ones, pre-filled
    with what the assessment already has (what to protect: from the product the customer came for)."""
    topic, market = state.get("form_topic"), state["market"]
    if topic not in NEEDS_TOPICS:
        return None
    current = None
    if state.get("needs_assessment_id"):
        async with flow.d.uow() as uow:
            current = await uow.needs.get(as_uuid(state["needs_assessment_id"]))
    values = merge_needs(needs_view(current), {}, market)
    required = required_paths(values, market)
    currency = MARKET_CURRENCY.get(market, "USD")
    fields = []
    for f in NEEDS_TOPICS[topic]:
        if f.path not in required and not f.optional:
            continue
        value = value_at(values, f.path)
        if f.path == "objectives" and not value and (objective := interest_objective(state.get("product_interest"))):
            value = [objective]
        if f.money and value not in BLANK:
            major = value / minor_per_unit(market)
            value = int(major) if major == int(major) else major
        elif f.form.name == "destination_countries" and isinstance(value, list):
            value = ", ".join(value)
        fields.append((f.form, f.path in required, value))
    spec = form_spec(flow, lang, "profiling", topic, fields, allow_text=True)
    for item in spec["fields"]:
        if NEEDS_FIELDS[item["name"]].money:
            item["label"] = f"{item['label']} ({currency})"
    return spec


async def restart_profiling(
    flow: Flow, state: dict[str, Any], resolution: str | None, now: datetime
) -> tuple[list[BaseMessage], dict[str, Any]]:
    """Back to the needs assessment with a fresh round count, after an agent helped out."""
    return [], {"stage": "PROFILING", "needs_complete": False, "needs_rounds": 0, "needs_input": None}


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
            text = self.text(lang, "profiling.purchases_found", purchases=", ".join(found))
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
        partner_types = {o.object_type for o in partner_objects}
        interest = state.get("product_interest")
        base = needs_view(current)
        before = compute_needs_missing(merge_needs(base, {}, m), market=m, partner_object_types=partner_types)

        if state.get("last_input") != "NEEDS":
            # Nothing new to assess yet: ask (first visit, after a CHANGE without text, after handoff).
            if current is not None and current.completed_at is not None:
                return self._ask(lang, self.text(lang, "profiling.ask_change"), None)
            topic = next_topic(before, interest)
            lead = self._lead(lang, topic)
            if current is not None:
                return self._ask(lang, self.text(lang, "profiling.ask_missing", lead=lead), topic)
            return self._ask(lang, self.text(lang, "profiling.ask_needs", lead=lead), topic)

        # The answer: a form's fields and/or free text (`needs_input`); a CHANGE decision's text has no input.
        pending = state.get("needs_input") or {}
        fields = pending.get("fields") or {}
        values = merge_needs(base, {}, m)
        if pending.get("text") or not pending:
            known_devices = [
                {k: o.attributes.get(k) for k in ("device_category", "manufacturer", "model", "purchase_date")}
                for o in partner_objects
            ]
            instructions = self.prompt(
                "assess_needs",
                "instructions",
                known_devices=json.dumps(known_devices, ensure_ascii=False),
                values=json.dumps(base, ensure_ascii=False, default=str),
            )
            # The first message the customer wrote (the intake) is part of what they told us.
            intake = str((state.get("intake") or {}).get("text") or "").strip()
            texts = ([intake] if intake else []) + latest_texts(state.get("messages") or [], ("NEEDS",))
            ext = await self.d.llm.extract(
                "assess_needs",
                NeedsExtraction,
                [self._system(state, party, instructions), HumanMessage("\n\n".join(texts) or "-")],
            )
            values = merge_needs(values, ext.model_dump(), m)
        if fields:
            # What the customer typed into a form wins over what the LLM read from their text.
            values = merge_needs(values, structured_needs(fields, m), m)
        missing = compute_needs_missing(values, market=m, partner_object_types=partner_types)
        # A round is an answer that fills none of the fields missing before it.
        rounds = int(state.get("needs_rounds") or 0) + (0 if set(before) - set(missing) else 1)
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
                    values, partner_object_types=partner_types, today=self.today(state)
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

        done = {"needs_assessment_id": na_id, "needs_input": None, "last_input": None, "form_topic": None}
        if not missing:
            for obj_id in ids:
                await self._touch(state, "insurable_object", obj_id)
            text = self.text(lang, "profiling.needs_complete")
            return {
                **done,
                "needs_complete": True,
                "needs_rounds": 0,
                "handoff_reason": None,
                "insurable_object_ids": ids,
                "messages": [say(text, now)],
            }
        if rounds >= MAX_NEEDS_ROUNDS:
            text = self.text(lang, "profiling.needs_handoff")
            return {
                **done,
                "needs_complete": False,
                "needs_rounds": rounds,
                "handoff_reason": "NEEDS_INCOMPLETE",
                "messages": [say(text, now)],
            }
        topic = next_topic(missing, interest)
        return {
            **done,
            **self._ask(lang, self.text(lang, "profiling.ask_more", lead=self._lead(lang, topic)), topic),
            "needs_rounds": rounds,
        }

    def _lead(self, lang: str, topic: str | None) -> str:
        return self.text(lang, f"profiling.form.{topic}.lead") if topic else ""

    def _ask(self, lang: str, text: str, topic: str | None) -> dict[str, Any]:
        return {
            "needs_complete": False,
            "handoff_reason": None,
            "waiting_for": "NEEDS",
            "form_topic": topic,
            "messages": [say(text.strip(), self.now())],
        }


def after_fetch_purchases(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "assess_needs"


def after_assess_needs(state: dict[str, Any]) -> str:
    if has_error(state) or state.get("handoff_reason") == "NEEDS_INCOMPLETE":
        return HANDOFF
    return "check_eligibility" if state.get("needs_complete") else "ask_customer"


TEXTS = TextSpec(
    copy={
        "purchases_found": frozenset({"purchases"}),
        "ask_missing": frozenset({"lead"}),
        "ask_change": frozenset(),
        "ask_needs": frozenset({"lead"}),
        "needs_complete": frozenset(),
        "needs_handoff": frozenset(),
        "ask_more": frozenset({"lead"}),
        **form_copy({topic: [f.form for f in fields] for topic, fields in NEEDS_TOPICS.items()}),
    },
    llm={
        "assess_needs": {
            "instructions": frozenset({"known_devices", "values"}),
        },
    },
)


MODULE = DomainModule(
    name="profiling",
    texts=TEXTS,
    flow=ProfilingFlow,
    edges={
        "fetch_purchases": after_fetch_purchases,
        "assess_needs": after_assess_needs,
    },
    retrying=frozenset({"assess_needs", "fetch_purchases"}),
    inputs={"NEEDS": InputKind("assess_needs", record_needs, needs_form)},
    handoffs={"NEEDS_INCOMPLETE": HandoffKind(resume_profiling, restart_profiling)},
)
