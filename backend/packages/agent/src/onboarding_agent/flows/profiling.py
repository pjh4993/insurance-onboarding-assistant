"""Stage 2, customer profiling: partner purchases (with consent), then the needs assessment the LLM extracts
and code checks for completeness."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

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
from onboarding_agent.ids import node_uuid
from onboarding_agent.llm.schemas import NeedsExtraction
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import locale_of, say
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

        if state.get("last_input") != "NEEDS":
            # Nothing new to assess yet: ask (first visit, after a CHANGE without text, after handoff).
            if current is not None and current.completed_at is None and current.missing_fields:
                text = self.text(
                    lang, "profiling.ask_missing", fields=self.d.bundle.field_list(lang, current.missing_fields)
                )
            elif current is not None and current.completed_at is not None:
                text = self.text(lang, "profiling.ask_change")
            else:
                text = self.text(lang, "profiling.ask_needs")
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
        instructions = self.prompt(
            "assess_needs",
            "instructions",
            known_devices=json.dumps(known_devices, ensure_ascii=False),
            values=json.dumps(base, ensure_ascii=False, default=str),
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

        if not missing:
            for obj_id in ids:
                await self._touch(state, "insurable_object", obj_id)
            text = self.text(lang, "profiling.needs_complete")
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
            text = self.text(lang, "profiling.needs_handoff")
            return {
                "needs_assessment_id": na_id,
                "needs_complete": False,
                "needs_rounds": rounds,
                "last_input": None,
                "handoff_reason": "NEEDS_INCOMPLETE",
                "messages": [say(text, now)],
            }
        text = self.text(lang, "profiling.ask_more", fields=self.d.bundle.field_list(lang, missing))
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


TEXTS = TextSpec(
    copy={
        "purchases_found": frozenset({"purchases"}),
        "ask_missing": frozenset({"fields"}),
        "ask_change": frozenset(),
        "ask_needs": frozenset(),
        "needs_complete": frozenset(),
        "needs_handoff": frozenset(),
        "ask_more": frozenset({"fields"}),
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
    inputs={"NEEDS": InputKind("assess_needs")},
    handoffs={"NEEDS_INCOMPLETE": HandoffKind(resume_profiling, restart_profiling)},
)
