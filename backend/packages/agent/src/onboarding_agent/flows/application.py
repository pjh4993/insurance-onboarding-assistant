"""Stage 4, policy application: open it with pre-filled answers, collect parties and the missing answers,
summarize, confirm, submit."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import interrupt

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
from onboarding_agent.flows.recommendation import price_quote, session_recommendations
from onboarding_agent.ids import node_uuid
from onboarding_agent.llm.schemas import (
    AnswersExtraction,
    ApplicationSummary,
    PartiesExtraction,
)
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import human, locale_of, price_label, say
from onboarding_core.application.models import Application
from onboarding_core.application.rules import apply_answer_aliases, missing_answers, prefill_answers
from onboarding_core.needs.rules import object_view
from onboarding_core.party.models import Party
from onboarding_core.ports import UnitOfWork
from onboarding_core.util import iso, parse_date

# ANSWERS replies that leave fields missing before an agent takes over.
MAX_ANSWERS_ROUNDS = 3


async def restart_answers(
    flow: Flow, state: dict[str, Any], resolution: str | None, now: datetime
) -> tuple[list[BaseMessage], dict[str, Any]]:
    """Back to the application questions with a fresh round count, after an agent helped out."""
    return [], {"stage": "APPLICATION", "answers_complete": False, "answers_rounds": 0}


def resume_answers(state: dict[str, Any]) -> str:
    return "collect_answers"


class ApplicationFlow(Flow):
    async def open_application(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang, now, step, actor = locale_of(state), self.now(), step_of(config), state.get("actor") or "CUSTOMER"
        app_id = node_uuid(thread_of(config), "open_application", step)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            rec = next((r for r in await session_recommendations(uow, state) if r.status == "ACCEPTED"), None)
            if rec is None:
                raise LookupError("no accepted recommendation")
            product = await uow.catalog.product(rec.product_code)
            obj = await uow.objects.get(rec.insurable_object_id)
            quote = await uow.quotes.get(as_uuid(state["quote_ids"][str(rec.recommendation_id)]))
            if quote.valid_until < now:
                # The accepted price lapsed while the customer was away: re-price at today's rules.
                fresh = price_quote(product, obj, now)
                fresh.quote_id = node_uuid(thread_of(config), "open_application", step, "requote")
                fresh.recommendation_id = rec.recommendation_id
                fresh.status = "ACCEPTED"
                quote.status = "EXPIRED"
                quote = await uow.quotes.save(fresh)
            answers = prefill_answers(product.required_application_fields, object_view(obj), party, now.date())
            await uow.applications.save(
                Application(
                    application_id=app_id,
                    session_id=as_uuid(state["session_id"]),
                    recommendation_id=rec.recommendation_id,
                    quote_id=quote.quote_id,
                    product_code=product.product_code,
                    insurable_object_id=obj.insurable_object_id,
                    status="DRAFT",
                    answers=jsonable(answers),
                    missing_fields=missing_answers(product.required_application_fields, answers),
                    captured_by=actor,
                )
            )
            quote_ids = {**state["quote_ids"], str(rec.recommendation_id): str(quote.quote_id)}
            name = product.marketing_name
        await self._touch(state, "application", app_id)
        text = self.text(lang, "application.opened", product=name)
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
        lang, now, step = locale_of(state), self.now(), step_of(config)
        if state.get("last_input") != "PARTIES":
            text = self.text(lang, "application.ask_parties")
            return {"parties_complete": False, "waiting_for": "PARTIES", "messages": [say(text, now)]}

        async with self.d.uow() as uow:
            party = await self._party(uow, state)
        instructions = self.prompt("collect_parties", "instructions")
        texts = latest_texts(state.get("messages") or [], ("PARTIES",))
        ext = await self.d.llm.extract(
            "collect_parties",
            PartiesExtraction,
            [self._system(state, party, instructions), HumanMessage(texts[-1] if texts else "-")],
        )
        others = [] if ext.all_self else [p for p in ext.parties if p.get("role") in ("INSURED", "PAYER")]
        if any(not str(p.get("full_name") or "").strip() for p in others):
            text = self.text(lang, "application.ask_party_details")
            return {
                "parties_complete": False,
                "last_input": None,
                "waiting_for": "PARTIES",
                "messages": [say(text, now)],
            }

        app_id = as_uuid(state["application_id"])
        async with self.d.uow() as uow:
            roles: dict[str, uuid.UUID] = {"POLICYHOLDER": party.party_id}
            names = []
            for i, p in enumerate(others):
                pid = node_uuid(thread_of(config), "collect_parties", step, f"{p['role']}:{i}")
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
            application.answers = jsonable(answers)
            application.missing_fields = missing_answers(product.required_application_fields, answers)
        await self._touch(state, "application", app_id)
        others = ", ".join(names)
        text = (
            self.text(lang, "application.parties_named", names=others)
            if names
            else self.text(lang, "application.parties_self")
        )
        return {"parties_complete": True, "last_input": None, "messages": [say(text, now)]}

    async def collect_answers(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang, now, actor = locale_of(state), self.now(), state.get("actor") or "CUSTOMER"
        app_id = as_uuid(state["application_id"])
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            application = await uow.applications.get(app_id)
            product = await uow.catalog.product(application.product_code)
        required = list(product.required_application_fields)
        answers = dict(application.answers or {})
        got_input = state.get("last_input") == "ANSWERS"

        if got_input:
            missing_now = missing_answers(required, answers)
            instructions = self.prompt(
                "collect_answers",
                "instructions",
                fields=json.dumps(required),
                answers=json.dumps(answers, ensure_ascii=False, default=str),
                missing=json.dumps(missing_now),
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
            application.answers = jsonable(answers)
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
            text = self.text(lang, "application.answers_handoff")
            return {
                **base,
                "answers_complete": False,
                "handoff_reason": "ANSWERS_INCOMPLETE",
                "messages": [say(text, now)],
            }
        if missing:
            text = self.text(lang, "application.ask_answers", fields=self.d.bundle.field_list(lang, missing))
            return {**base, "answers_complete": False, "waiting_for": "ANSWERS", "messages": [say(text, now)]}
        if state.get("confirmed") is False and not got_input:
            text = self.text(lang, "application.ask_correction")
            return {**base, "answers_complete": False, "waiting_for": "ANSWERS", "messages": [say(text, now)]}
        return {**base, "answers_complete": True, "answers_rounds": 0}

    async def summarize_application(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang, now = locale_of(state), self.now()
        app_id = as_uuid(state["application_id"])
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            application = await uow.applications.get(app_id)
            product = await uow.catalog.product(application.product_code)
            quote = await uow.quotes.get(application.quote_id)
            parties = await self._application_parties(uow, app_id)
        facts = {
            "product": product.marketing_name,
            "price": price_label(self.d.bundle, lang, quote.premium_minor, quote.currency, quote.billing_period),
            "cover": f"{quote.term_start_date} to {quote.term_end_date}",
            "parties": parties,
            "answers": application.answers,
        }
        instructions = self.prompt(
            "summarize_application", "instructions", facts=json.dumps(facts, ensure_ascii=False, default=str)
        )
        ext = await self.d.llm.extract(
            "summarize_application",
            ApplicationSummary,
            [self._system(state, party, instructions), HumanMessage(self.prompt("summarize_application", "user"))],
        )
        async with self.d.uow() as uow:
            application = await uow.applications.get(app_id)
            application.summary = ext.summary
            application.status = "COMPLETE"
        await self._touch(state, "application", app_id)
        text = self.text(lang, "application.confirm_summary", summary=ext.summary)
        return {"waiting_for": "CONFIRM", "confirmed": None, "messages": [say(text, now)]}

    async def confirm_summary(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        value = interrupt({"waiting_for": "CONFIRM"})
        lang, now, actor = locale_of(state), self.now(), state.get("actor") or "CUSTOMER"
        confirmed = bool(value.get("confirmed"))
        extra = str(value.get("text") or "").strip()
        if confirmed:
            msg = human(extra or self.text(lang, "application.confirm_yes"), now, actor=actor, input_type="CONFIRM")
            return {"confirmed": True, "waiting_for": None, "messages": [msg]}
        msg = human(
            extra or self.text(lang, "application.confirm_no"),
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
        app_id = as_uuid(state["application_id"])
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
            res = await self.d.contract.submit_application(str(app_id), jsonable(payload))
            ref = res["submission_ref"]
            async with self.d.uow() as uow:
                application = await uow.applications.get(app_id)
                application.submission_ref = ref
                application.status = "SUBMITTED"
                application.submitted_at = now
        await self._touch(state, "application", app_id)
        text = self.text(lang, "application.submitted", ref=ref)
        return {"stage": "SUBMITTED", "waiting_for": None, "messages": [say(text, now)]}

    async def _application_parties(self, uow: UnitOfWork, app_id: uuid.UUID) -> list[dict[str, Any]]:
        return [
            {"role": role, "full_name": p.full_name, "date_of_birth": iso(p.date_of_birth)}
            for role, p in await uow.applications.parties(app_id)
        ]


def after_open_application(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "collect_parties"


def after_collect_parties(state: dict[str, Any]) -> str:
    if has_error(state):
        return HANDOFF
    return "collect_answers" if state.get("parties_complete") else "ask_customer"


def after_collect_answers(state: dict[str, Any]) -> str:
    if has_error(state) or state.get("handoff_reason") == "ANSWERS_INCOMPLETE":
        return HANDOFF
    return "summarize_application" if state.get("answers_complete") else "ask_customer"


def after_summarize_application(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "confirm_summary"


def after_confirm_summary(state: dict[str, Any]) -> str:
    if has_error(state):
        return HANDOFF
    return "submit_application" if state.get("confirmed") else "collect_answers"


def after_submit_application(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else END


TEXTS = TextSpec(
    copy={
        "opened": frozenset({"product"}),
        "ask_parties": frozenset(),
        "ask_party_details": frozenset(),
        "parties_named": frozenset({"names"}),
        "parties_self": frozenset(),
        "answers_handoff": frozenset(),
        "ask_answers": frozenset({"fields"}),
        "ask_correction": frozenset(),
        "confirm_summary": frozenset({"summary"}),
        "confirm_yes": frozenset(),
        "confirm_no": frozenset(),
        "submitted": frozenset({"ref"}),
    },
    llm={
        "collect_parties": {
            "instructions": frozenset(),
        },
        "collect_answers": {
            "instructions": frozenset({"fields", "answers", "missing"}),
        },
        "summarize_application": {
            "instructions": frozenset({"facts"}),
            "user": frozenset(),
        },
    },
)


MODULE = DomainModule(
    name="application",
    texts=TEXTS,
    flow=ApplicationFlow,
    edges={
        "open_application": after_open_application,
        "collect_parties": after_collect_parties,
        "collect_answers": after_collect_answers,
        "summarize_application": after_summarize_application,
        "confirm_summary": after_confirm_summary,
        "submit_application": after_submit_application,
    },
    retrying=frozenset({"collect_answers", "collect_parties", "submit_application", "summarize_application"}),
    inputs={"PARTIES": InputKind("collect_parties"), "ANSWERS": InputKind("collect_answers")},
    handoffs={"ANSWERS_INCOMPLETE": HandoffKind(resume_answers, restart_answers)},
)
