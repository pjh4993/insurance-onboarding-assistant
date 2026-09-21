"""Tables and ORM mapping. Schemas: `catalog` (read-only reference data), `domain` (customer + transaction
records). The `checkpoint` schema belongs to langgraph-checkpoint-postgres.

The domain entities are plain dataclasses in `onboarding_core`; this module maps them onto the tables
imperatively, so the core and the agent never import SQLAlchemy. `OnboardingSession` is the backend's
own record and stays declarative. Importing this module installs the mappings.

Field names follow wiki/entity-dictionary.md. Only the entities the flow needs are modelled.
Columns the entities do not declare (`created_at`/`updated_at` with a server default) are still
mapped, so queries can sort on them."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry

from onboarding_core.application.models import Application, ApplicationParty
from onboarding_core.catalog.models import EligibilityRule, Product, TargetMarket
from onboarding_core.needs.models import InsurableObject, NeedsAssessment
from onboarding_core.party.models import Party
from onboarding_core.quoting.models import Quote
from onboarding_core.recommendation.models import Recommendation

SCHEMAS = ("catalog", "domain", "checkpoint")

mapper_registry = registry()
metadata = mapper_registry.metadata


class Base(DeclarativeBase):
    registry = mapper_registry


def _id(name: str, **kw) -> Column:
    return Column(name, UUID(as_uuid=True), **kw)


def _ts(name: str, nullable: bool = True, **kw) -> Column:
    return Column(name, DateTime(timezone=True), nullable=nullable, **kw)


def _audit() -> tuple[Column, Column]:
    return (
        _ts("created_at", False, server_default=func.now()),
        _ts("updated_at", False, server_default=func.now(), onupdate=func.now()),
    )


# --------------------------------------------------------------------------------------------- catalog

product = Table(
    "product",
    metadata,
    Column("product_code", String(64), primary_key=True),
    Column("product_type", String(32), nullable=False),
    Column("marketing_name", String(200), nullable=False),
    Column("insurable_object_type", String(16), nullable=False),
    Column("coverages", JSONB, nullable=False),
    Column("rating", JSONB, nullable=False),
    Column("billing_period", String(16), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("jurisdictions", ARRAY(String(2)), nullable=False),
    Column("sale_effective_date", Date, nullable=False),
    Column("sale_expiration_date", Date),
    Column("term_rule", JSONB, nullable=False),
    Column("required_application_fields", ARRAY(String(64)), nullable=False),
    Column("status", String(16), nullable=False),
    schema="catalog",
)

eligibility_rule = Table(
    "eligibility_rule",
    metadata,
    _id("rule_id", primary_key=True),
    Column("product_code", ForeignKey("catalog.product.product_code"), index=True, nullable=False),
    Column("subject", String(32), nullable=False),
    Column("attribute", String(100), nullable=False),
    Column("operator", String(16), nullable=False),
    Column("value", JSONB, nullable=False),
    Column("failure_reason_code", String(64), nullable=False),
    Column("description", Text, nullable=False),
    schema="catalog",
)

target_market = Table(
    "target_market",
    metadata,
    _id("target_market_id", primary_key=True),
    Column("product_code", ForeignKey("catalog.product.product_code"), index=True, nullable=False),
    Column("attribute", String(64), nullable=False),
    Column("values", JSONB, nullable=False),
    Column("weight", Float, nullable=False),
    Column("rationale", Text, nullable=False),
    schema="catalog",
)

# --------------------------------------------------------------------------------------------- domain

party = Table(
    "party",
    metadata,
    _id("party_id", primary_key=True),
    Column("party_type", String(16), nullable=False),
    Column("full_name", String(200)),
    Column("email", String(320)),
    Column("phone", String(32)),
    Column("date_of_birth", Date),
    Column("id_document_type", String(32)),
    # The document number is never stored in plaintext: AES-EAX ciphertext + HMAC for lookups.
    Column("id_document_number_enc", LargeBinary),
    Column("id_document_hmac", String(64), index=True),
    _ts("third_party_consent_at"),
    Column("partner_customer_ref", String(64)),
    Column("verification_status", String(16), nullable=False),
    Column("verification_method", String(16)),
    Column("verification_attempts", Integer, nullable=False),
    _ts("verified_at"),
    _id("merged_into_party_id"),
    *_audit(),
    schema="domain",
)


class OnboardingSession(Base):
    __tablename__ = "onboarding_session"
    __table_args__ = {"schema": "domain"}

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True)
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain.party.party_id"))
    market: Mapped[str] = mapped_column(String(2))
    locale: Mapped[str] = mapped_column(String(5))
    token_hmac: Mapped[str] = mapped_column(String(64), unique=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    last_stage: Mapped[str] = mapped_column(String(16), default="IDENTITY")
    waiting_for: Mapped[str | None] = mapped_column(String(16))
    current_node: Mapped[str | None] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(8), default="AUTO")
    assigned_agent_id: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


needs_assessment = Table(
    "needs_assessment",
    metadata,
    _id("needs_assessment_id", primary_key=True),
    Column("party_id", ForeignKey("domain.party.party_id"), index=True, nullable=False),
    _id("session_id", index=True, nullable=False),
    Column("version", Integer, nullable=False),
    Column("age_range", String(16)),
    Column("occupation", String(200)),
    Column("residence_country", String(2)),
    Column("existing_coverage", JSONB, nullable=False),
    Column("objectives", JSONB, nullable=False),
    Column("objectives_note", Text),
    # Device/trip the customer described, kept with the version so a CHANGE re-derives objects.
    Column("device", JSONB),
    Column("trip", JSONB),
    Column("captured_by", String(16), nullable=False),
    Column("missing_fields", JSONB, nullable=False),
    _ts("completed_at"),
    _ts("created_at", False, server_default=func.now()),
    schema="domain",
)

insurable_object = Table(
    "insurable_object",
    metadata,
    _id("insurable_object_id", primary_key=True),
    Column("owner_party_id", ForeignKey("domain.party.party_id"), index=True, nullable=False),
    Column("object_type", String(16), nullable=False),
    Column("source", String(16), nullable=False),
    Column("attributes", JSONB, nullable=False),
    *_audit(),
    schema="domain",
)

recommendation = Table(
    "recommendation",
    metadata,
    _id("recommendation_id", primary_key=True),
    Column("session_id", ForeignKey("domain.onboarding_session.session_id"), index=True, nullable=False),
    Column("party_id", ForeignKey("domain.party.party_id"), nullable=False),
    Column("needs_assessment_id", ForeignKey("domain.needs_assessment.needs_assessment_id"), nullable=False),
    Column("product_code", ForeignKey("catalog.product.product_code"), nullable=False),
    _id("insurable_object_id"),
    Column("rank", Integer, nullable=False),
    Column("score", Float, nullable=False),
    Column("eligibility_result", String(16), nullable=False),
    Column("failed_rule_ids", JSONB, nullable=False),
    Column("failed_reasons", JSONB, nullable=False),
    Column("rationale", Text),
    Column("status", String(16), nullable=False),
    Column("decided_by", String(16)),
    _ts("decided_at"),
    _ts("created_at", False, server_default=func.now()),
    schema="domain",
)

quote = Table(
    "quote",
    metadata,
    _id("quote_id", primary_key=True),
    Column("recommendation_id", ForeignKey("domain.recommendation.recommendation_id"), index=True, nullable=False),
    Column("product_code", String(64), nullable=False),
    _id("insurable_object_id", nullable=False),
    Column("coverages", JSONB, nullable=False),
    Column("term_start_date", Date, nullable=False),
    Column("term_end_date", Date, nullable=False),
    Column("premium_minor", Integer, nullable=False),
    Column("billing_period", String(16), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("rating_inputs", JSONB, nullable=False),
    Column("status", String(16), nullable=False),
    _ts("valid_until", False),
    _ts("created_at", False),
    schema="domain",
)

application = Table(
    "application",
    metadata,
    _id("application_id", primary_key=True),
    Column("session_id", ForeignKey("domain.onboarding_session.session_id"), index=True, nullable=False),
    Column("recommendation_id", ForeignKey("domain.recommendation.recommendation_id"), nullable=False),
    Column("quote_id", ForeignKey("domain.quote.quote_id"), nullable=False),
    Column("product_code", String(64), nullable=False),
    _id("insurable_object_id"),
    Column("status", String(16), nullable=False),
    Column("answers", JSONB, nullable=False),
    Column("missing_fields", JSONB, nullable=False),
    Column("summary", Text),
    Column("captured_by", String(16), nullable=False),
    _ts("submitted_at"),
    Column("submission_ref", String(64)),
    *_audit(),
    schema="domain",
)

application_party = Table(
    "application_party",
    metadata,
    Column("application_id", ForeignKey("domain.application.application_id"), primary_key=True),
    Column("party_id", ForeignKey("domain.party.party_id"), primary_key=True),
    Column("role", String(16), primary_key=True),
    schema="domain",
)

for _entity, _table in (
    (Product, product),
    (EligibilityRule, eligibility_rule),
    (TargetMarket, target_market),
    (Party, party),
    (NeedsAssessment, needs_assessment),
    (InsurableObject, insurable_object),
    (Recommendation, recommendation),
    (Quote, quote),
    (Application, application),
    (ApplicationParty, application_party),
):
    mapper_registry.map_imperatively(_entity, _table)


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
    "metadata",
]
