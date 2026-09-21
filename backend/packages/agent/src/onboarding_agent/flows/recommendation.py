"""Stage 3, policy recommendation: code checks eligibility, ranks and prices; the LLM explains; the customer
accepts, declines or changes their answers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import interrupt

from onboarding_agent.flows.base import DomainModule, Flow, HandoffKind, as_uuid, jsonable, step_of, thread_of
from onboarding_agent.flows.profiling import restart_profiling, resume_profiling
from onboarding_agent.ids import node_uuid
from onboarding_agent.llm.schemas import RecommendationRationale
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import human, locale_of, price_label, say, t
from onboarding_core.catalog.eligibility import RuleSpec, evaluate_product, rank_order, target_market_score
from onboarding_core.catalog.models import Product
from onboarding_core.needs.models import InsurableObject
from onboarding_core.needs.rules import needs_view, object_view
from onboarding_core.party.rules import party_view
from onboarding_core.ports import UnitOfWork
from onboarding_core.quoting.models import Quote
from onboarding_core.quoting.pricing import RatingError, compute_premium, compute_term, quote_valid_until
from onboarding_core.recommendation.models import Recommendation


async def session_recommendations(uow: UnitOfWork, state: dict[str, Any]) -> list[Recommendation]:
    """The recommendations of the current round, best rank first."""
    ids = [as_uuid(i) for i in state.get("recommendation_ids") or []]
    if not ids:
        return []
    return sorted(await uow.recommendations.list(ids), key=lambda r: (r.rank or 0, r.product_code))


def price_quote(product: Product, obj: InsurableObject, now: datetime) -> Quote:
    """A fresh quote for insuring `obj` with `product` at today's rules (no id yet)."""
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
        rating_inputs=jsonable(premium.rating_inputs),
        status="ISSUED",
        valid_until=quote_valid_until(now, start),
        created_at=now,
    )


class RecommendationFlow(Flow):
    async def check_eligibility(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        m, today, step = state["market"], self.now().date(), step_of(config)
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            na = await uow.needs.get(as_uuid(state["needs_assessment_id"]))
            objects = [
                object_view(o)
                for o in await uow.objects.list(as_uuid(i) for i in state.get("insurable_object_ids") or [])
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
                rec_id = node_uuid(thread_of(config), "check_eligibility", step, product.product_code)
                await uow.recommendations.save(
                    Recommendation(
                        recommendation_id=rec_id,
                        session_id=as_uuid(state["session_id"]),
                        party_id=party.party_id,
                        needs_assessment_id=na.needs_assessment_id,
                        product_code=product.product_code,
                        insurable_object_id=as_uuid(chosen["insurable_object_id"]) if chosen else None,
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
            na = await uow.needs.get(as_uuid(state["needs_assessment_id"]))
            recs = await session_recommendations(uow, state)
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
        now, step = self.now(), step_of(config)
        quote_ids: dict[str, str] = {}
        async with self.d.uow() as uow:
            eligible = 0
            for rec in await session_recommendations(uow, state):
                if rec.eligibility_result != "ELIGIBLE":
                    continue
                product = await uow.catalog.product(rec.product_code)
                obj = await uow.objects.get(rec.insurable_object_id)
                try:
                    quote = price_quote(product, obj, now)
                except RatingError as exc:
                    rec.eligibility_result = "INELIGIBLE"
                    rec.failed_reasons = [*rec.failed_reasons, f"RATING_ERROR: {exc}"]
                    continue
                quote.quote_id = node_uuid(thread_of(config), "quote_premium", step, str(rec.recommendation_id))
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

    async def explain_recommendation(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            na = await uow.needs.get(as_uuid(state["needs_assessment_id"]))
            recs = [r for r in await session_recommendations(uow, state) if r.eligibility_result == "ELIGIBLE"]
            products = {r.product_code: await uow.catalog.product(r.product_code) for r in recs}
            quotes = {
                str(r.recommendation_id): await uow.quotes.get(as_uuid(state["quote_ids"][str(r.recommendation_id)]))
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
            recs = await session_recommendations(uow, state)
            eligible = [r for r in recs if r.eligibility_result == "ELIGIBLE" and r.status == "PROPOSED"]
            quotes = {k: await uow.quotes.get(as_uuid(v)) for k, v in (state.get("quote_ids") or {}).items()}
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


def after_check_eligibility(state: dict[str, Any]) -> str:
    if has_error(state) or state.get("eligible_count", 0) == 0:
        return HANDOFF
    return "rank_products"


def after_rank_products(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "quote_premium"


def after_quote_premium(state: dict[str, Any]) -> str:
    if has_error(state) or state.get("eligible_count", 0) == 0:
        return HANDOFF
    return "explain_recommendation"


def after_explain_recommendation(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "await_decision"


def after_await_decision(state: dict[str, Any]) -> str:
    if has_error(state):
        return HANDOFF
    decision = state.get("decision")
    if decision == "ACCEPT":
        return "open_application"
    if decision == "CHANGE":
        return "assess_needs"
    return END


MODULE = DomainModule(
    name="recommendation",
    flow=RecommendationFlow,
    edges={
        "check_eligibility": after_check_eligibility,
        "rank_products": after_rank_products,
        "quote_premium": after_quote_premium,
        "explain_recommendation": after_explain_recommendation,
        "await_decision": after_await_decision,
    },
    retrying=frozenset({"explain_recommendation"}),
    # No product fits what the customer said: an agent helps them change it.
    handoffs={"NO_ELIGIBLE_PRODUCT": HandoffKind(resume_profiling, restart_profiling)},
)
