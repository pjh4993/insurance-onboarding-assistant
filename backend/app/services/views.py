"""API view models (CONTRACTS.md §3 types) built from the domain DB and the agent's state. Chat
messages come ready-made from `onboarding_agent.chat_message`."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Application,
    ApplicationParty,
    InsurableObject,
    NeedsAssessment,
    OnboardingSession,
    Party,
    Product,
    Quote,
    Recommendation,
)
from onboarding_core.util import iso


def display_name(session: OnboardingSession, party: Party | None) -> str:
    if party is not None and party.verification_status == "VERIFIED" and party.full_name:
        return party.full_name
    return f"Unverified #{session.session_id.hex[:4]}"


def summary_view(session: OnboardingSession, party: Party | None) -> dict[str, Any]:
    return {
        "session_id": str(session.session_id),
        "display_name": display_name(session, party),
        "market": session.market,
        "locale": session.locale,
        "origin": session.origin,
        "status": session.status,
        "stage": session.last_stage,
        "waiting_for": session.waiting_for,
        "mode": session.mode,
        "assigned_agent_id": session.assigned_agent_id,
        "last_activity_at": iso(session.last_activity_at),
    }


def quote_view(q: Quote | None) -> dict[str, Any] | None:
    if q is None:
        return None
    return {
        "quote_id": str(q.quote_id),
        "premium_minor": q.premium_minor,
        "currency": q.currency,
        "billing_period": q.billing_period,
        "term_start_date": iso(q.term_start_date),
        "term_end_date": iso(q.term_end_date),
        "valid_until": iso(q.valid_until),
    }


async def recommendation_cards(
    s: AsyncSession, recs: list[Recommendation], quote_ids: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    cards = []
    for r in recs:
        product = await s.get(Product, r.product_code)
        quote = None
        qid = (quote_ids or {}).get(str(r.recommendation_id))
        if qid:
            quote = await s.get(Quote, uuid.UUID(qid))
        if quote is None:
            quote = await s.scalar(
                select(Quote)
                .where(Quote.recommendation_id == r.recommendation_id)
                .order_by(Quote.created_at.desc())
                .limit(1)
            )
        cards.append(
            {
                "recommendation_id": str(r.recommendation_id),
                "product_code": r.product_code,
                "marketing_name": product.marketing_name if product else r.product_code,
                "product_type": product.product_type if product else "",
                "rank": r.rank,
                "eligibility_result": r.eligibility_result,
                "failed_reasons": list(r.failed_reasons or []),
                "rationale": r.rationale,
                "status": r.status,
                "quote": quote_view(quote),
            }
        )
    return cards


def party_detail(p: Party | None) -> dict[str, Any] | None:
    """PII-masked party: the document number is never returned."""
    if p is None:
        return None
    return {
        "party_id": str(p.party_id),
        "party_type": p.party_type,
        "full_name": p.full_name,
        "email": p.email,
        "phone": p.phone,
        "date_of_birth": iso(p.date_of_birth),
        "id_document_type": p.id_document_type,
        "third_party_consent_at": iso(p.third_party_consent_at),
        "partner_customer_ref": p.partner_customer_ref,
        "verification_status": p.verification_status,
        "verification_method": p.verification_method,
        "verification_attempts": p.verification_attempts,
        "verified_at": iso(p.verified_at),
    }


def needs_detail(na: NeedsAssessment | None) -> dict[str, Any] | None:
    if na is None:
        return None
    return {
        "needs_assessment_id": str(na.needs_assessment_id),
        "version": na.version,
        "age_range": na.age_range,
        "occupation": na.occupation,
        "residence_country": na.residence_country,
        "existing_coverage": na.existing_coverage,
        "objectives": na.objectives,
        "device": na.device,
        "trip": na.trip,
        "captured_by": na.captured_by,
        "missing_fields": na.missing_fields,
        "completed_at": iso(na.completed_at),
        "created_at": iso(na.created_at),
    }


def object_detail(o: InsurableObject) -> dict[str, Any]:
    return {
        "insurable_object_id": str(o.insurable_object_id),
        "object_type": o.object_type,
        "source": o.source,
        "attributes": o.attributes,
    }


def application_detail(a: Application | None) -> dict[str, Any] | None:
    if a is None:
        return None
    return {
        "application_id": str(a.application_id),
        "status": a.status,
        "product_code": a.product_code,
        "answers": a.answers or {},
        "missing_fields": a.missing_fields or [],
        "summary": a.summary,
        "submission_ref": a.submission_ref,
    }


async def application_parties(s: AsyncSession, application_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        await s.execute(
            select(ApplicationParty, Party)
            .join(Party, Party.party_id == ApplicationParty.party_id)
            .where(ApplicationParty.application_id == application_id)
            .order_by(ApplicationParty.role)
        )
    ).all()
    return [{"role": ap.role, "full_name": p.full_name} for ap, p in rows]
