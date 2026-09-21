"""SQLAlchemy models. Schemas: `catalog` (read-only reference data), `domain` (customer + transaction
records). The `checkpoint` schema belongs to langgraph-checkpoint-postgres.

Field names follow wiki/entity-dictionary.md. Only the entities the flow needs are modelled."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMAS = ("catalog", "domain", "checkpoint")


class Base(DeclarativeBase):
    pass


def _ts(nullable: bool = True, **kw: Any) -> Mapped[Any]:
    return mapped_column(DateTime(timezone=True), nullable=nullable, **kw)


# --------------------------------------------------------------------------------------------- catalog


class Product(Base):
    __tablename__ = "product"
    __table_args__ = {"schema": "catalog"}

    product_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_type: Mapped[str] = mapped_column(String(32))
    marketing_name: Mapped[str] = mapped_column(String(200))
    insurable_object_type: Mapped[str] = mapped_column(String(16))
    coverages: Mapped[list[dict]] = mapped_column(JSONB)
    rating: Mapped[dict] = mapped_column(JSONB)
    billing_period: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3))
    jurisdictions: Mapped[list[str]] = mapped_column(ARRAY(String(2)))
    sale_effective_date: Mapped[date] = mapped_column(Date)
    sale_expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    term_rule: Mapped[dict] = mapped_column(JSONB)
    required_application_fields: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class EligibilityRule(Base):
    __tablename__ = "eligibility_rule"
    __table_args__ = {"schema": "catalog"}

    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("catalog.product.product_code"), index=True)
    subject: Mapped[str] = mapped_column(String(32))
    attribute: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(16))
    value: Mapped[Any] = mapped_column(JSONB)
    failure_reason_code: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)


class TargetMarket(Base):
    __tablename__ = "target_market"
    __table_args__ = {"schema": "catalog"}

    target_market_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("catalog.product.product_code"), index=True)
    attribute: Mapped[str] = mapped_column(String(64))
    values: Mapped[list] = mapped_column(JSONB)
    weight: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)


# --------------------------------------------------------------------------------------------- domain


class Party(Base):
    __tablename__ = "party"
    __table_args__ = {"schema": "domain"}

    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    party_type: Mapped[str] = mapped_column(String(16), default="PERSON")
    full_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    id_document_type: Mapped[str | None] = mapped_column(String(32))
    # The document number is never stored in plaintext: AES-EAX ciphertext + HMAC for lookups.
    id_document_number_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    id_document_hmac: Mapped[str | None] = mapped_column(String(64), index=True)
    third_party_consent_at: Mapped[datetime | None] = _ts()
    partner_customer_ref: Mapped[str | None] = mapped_column(String(64))
    verification_status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")
    verification_method: Mapped[str | None] = mapped_column(String(16))
    verification_attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified_at: Mapped[datetime | None] = _ts()
    merged_into_party_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts(False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(False, server_default=func.now(), onupdate=func.now())


class OnboardingSession(Base):
    __tablename__ = "onboarding_session"
    __table_args__ = {"schema": "domain"}

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True)
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.party.party_id"))
    market: Mapped[str] = mapped_column(String(2))
    token_hmac: Mapped[str] = mapped_column(String(64), unique=True)
    token_expires_at: Mapped[datetime] = _ts(False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    last_stage: Mapped[str] = mapped_column(String(16), default="IDENTITY")
    waiting_for: Mapped[str | None] = mapped_column(String(16))
    current_node: Mapped[str | None] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(8), default="AUTO")
    assigned_agent_id: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = _ts(False)
    last_activity_at: Mapped[datetime] = _ts(False, index=True)
    ended_at: Mapped[datetime | None] = _ts()


class NeedsAssessment(Base):
    __tablename__ = "needs_assessment"
    __table_args__ = {"schema": "domain"}

    needs_assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.party.party_id"), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    version: Mapped[int] = mapped_column(Integer)
    age_range: Mapped[str | None] = mapped_column(String(16))
    occupation: Mapped[str | None] = mapped_column(String(200))
    residence_country: Mapped[str | None] = mapped_column(String(2))
    existing_coverage: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    objectives: Mapped[list[str]] = mapped_column(JSONB, default=list)
    objectives_note: Mapped[str | None] = mapped_column(Text)
    # Device/trip the customer described, kept with the version so a CHANGE re-derives objects.
    device: Mapped[dict | None] = mapped_column(JSONB)
    trip: Mapped[dict | None] = mapped_column(JSONB)
    captured_by: Mapped[str] = mapped_column(String(16), default="CUSTOMER")
    missing_fields: Mapped[list[str]] = mapped_column(JSONB, default=list)
    completed_at: Mapped[datetime | None] = _ts()
    created_at: Mapped[datetime] = _ts(False, server_default=func.now())


class InsurableObject(Base):
    __tablename__ = "insurable_object"
    __table_args__ = {"schema": "domain"}

    insurable_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    owner_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.party.party_id"), index=True)
    object_type: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    attributes: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _ts(False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(False, server_default=func.now(), onupdate=func.now())


class Recommendation(Base):
    __tablename__ = "recommendation"
    __table_args__ = {"schema": "domain"}

    recommendation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.onboarding_session.session_id"), index=True)
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.party.party_id"))
    needs_assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.needs_assessment.needs_assessment_id"))
    product_code: Mapped[str] = mapped_column(ForeignKey("catalog.product.product_code"))
    insurable_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    rank: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    eligibility_result: Mapped[str] = mapped_column(String(16))
    failed_rule_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    failed_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    rationale: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="PROPOSED")
    decided_by: Mapped[str | None] = mapped_column(String(16))
    decided_at: Mapped[datetime | None] = _ts()
    created_at: Mapped[datetime] = _ts(False, server_default=func.now())


class Quote(Base):
    __tablename__ = "quote"
    __table_args__ = {"schema": "domain"}

    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("domain.recommendation.recommendation_id"), index=True
    )
    product_code: Mapped[str] = mapped_column(String(64))
    insurable_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    coverages: Mapped[list[dict]] = mapped_column(JSONB)
    term_start_date: Mapped[date] = mapped_column(Date)
    term_end_date: Mapped[date] = mapped_column(Date)
    premium_minor: Mapped[int] = mapped_column(Integer)
    billing_period: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3))
    rating_inputs: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="ISSUED")
    valid_until: Mapped[datetime] = _ts(False)
    created_at: Mapped[datetime] = _ts(False)


class Application(Base):
    __tablename__ = "application"
    __table_args__ = {"schema": "domain"}

    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.onboarding_session.session_id"), index=True)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.recommendation.recommendation_id"))
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.quote.quote_id"))
    product_code: Mapped[str] = mapped_column(String(64))
    insurable_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    missing_fields: Mapped[list[str]] = mapped_column(JSONB, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    captured_by: Mapped[str] = mapped_column(String(16), default="CUSTOMER")
    submitted_at: Mapped[datetime | None] = _ts()
    submission_ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _ts(False, server_default=func.now())
    updated_at: Mapped[datetime] = _ts(False, server_default=func.now(), onupdate=func.now())


class ApplicationParty(Base):
    __tablename__ = "application_party"
    __table_args__ = {"schema": "domain"}

    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.application.application_id"), primary_key=True)
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.party.party_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), primary_key=True)


__all__ = [
    "SCHEMAS",
    "Application",
    "ApplicationParty",
    "Base",
    "EligibilityRule",
    "InsurableObject",
    "NeedsAssessment",
    "OnboardingSession",
    "Party",
    "Product",
    "Quote",
    "Recommendation",
    "TargetMarket",
]
