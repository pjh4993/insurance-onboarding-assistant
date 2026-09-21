"""Baseline: the schema as create_all built it before migrations existed.

Databases created before Alembic already have these tables; init_db stamps them at this revision
instead of running it (see app/db/migrate.py).

Revision ID: 0001
Revises:
Create Date: 2026-09-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = ("catalog", "domain", "checkpoint")


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    op.create_table(
        "product",
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("product_type", sa.String(length=32), nullable=False),
        sa.Column("marketing_name", sa.String(length=200), nullable=False),
        sa.Column("insurable_object_type", sa.String(length=16), nullable=False),
        sa.Column("coverages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rating", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("billing_period", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("jurisdictions", postgresql.ARRAY(sa.String(length=2)), nullable=False),
        sa.Column("sale_effective_date", sa.Date(), nullable=False),
        sa.Column("sale_expiration_date", sa.Date(), nullable=True),
        sa.Column("term_rule", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("required_application_fields", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("product_code"),
        schema="catalog",
    )
    op.create_table(
        "party",
        sa.Column("party_id", sa.UUID(), nullable=False),
        sa.Column("party_type", sa.String(length=16), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("id_document_type", sa.String(length=32), nullable=True),
        sa.Column("id_document_number_enc", sa.LargeBinary(), nullable=True),
        sa.Column("id_document_hmac", sa.String(length=64), nullable=True),
        sa.Column("third_party_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("partner_customer_ref", sa.String(length=64), nullable=True),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("verification_method", sa.String(length=16), nullable=True),
        sa.Column("verification_attempts", sa.Integer(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_into_party_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("party_id"),
        schema="domain",
    )
    op.create_index(
        op.f("ix_domain_party_id_document_hmac"), "party", ["id_document_hmac"], unique=False, schema="domain"
    )
    op.create_table(
        "eligibility_rule",
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("attribute", sa.String(length=100), nullable=False),
        sa.Column("operator", sa.String(length=16), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_reason_code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_code"],
            ["catalog.product.product_code"],
        ),
        sa.PrimaryKeyConstraint("rule_id"),
        schema="catalog",
    )
    op.create_index(
        op.f("ix_catalog_eligibility_rule_product_code"),
        "eligibility_rule",
        ["product_code"],
        unique=False,
        schema="catalog",
    )
    op.create_table(
        "target_market",
        sa.Column("target_market_id", sa.UUID(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("attribute", sa.String(length=64), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_code"],
            ["catalog.product.product_code"],
        ),
        sa.PrimaryKeyConstraint("target_market_id"),
        schema="catalog",
    )
    op.create_index(
        op.f("ix_catalog_target_market_product_code"), "target_market", ["product_code"], unique=False, schema="catalog"
    )
    op.create_table(
        "insurable_object",
        sa.Column("insurable_object_id", sa.UUID(), nullable=False),
        sa.Column("owner_party_id", sa.UUID(), nullable=False),
        sa.Column("object_type", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_party_id"],
            ["domain.party.party_id"],
        ),
        sa.PrimaryKeyConstraint("insurable_object_id"),
        schema="domain",
    )
    op.create_index(
        op.f("ix_domain_insurable_object_owner_party_id"),
        "insurable_object",
        ["owner_party_id"],
        unique=False,
        schema="domain",
    )
    op.create_table(
        "needs_assessment",
        sa.Column("needs_assessment_id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("age_range", sa.String(length=16), nullable=True),
        sa.Column("occupation", sa.String(length=200), nullable=True),
        sa.Column("residence_country", sa.String(length=2), nullable=True),
        sa.Column("existing_coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("objectives", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("objectives_note", sa.Text(), nullable=True),
        sa.Column("device", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trip", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("captured_by", sa.String(length=16), nullable=False),
        sa.Column("missing_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["domain.party.party_id"],
        ),
        sa.PrimaryKeyConstraint("needs_assessment_id"),
        schema="domain",
    )
    op.create_index(
        op.f("ix_domain_needs_assessment_party_id"), "needs_assessment", ["party_id"], unique=False, schema="domain"
    )
    op.create_index(
        op.f("ix_domain_needs_assessment_session_id"), "needs_assessment", ["session_id"], unique=False, schema="domain"
    )
    op.create_table(
        "onboarding_session",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("token_hmac", sa.String(length=64), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_stage", sa.String(length=16), nullable=False),
        sa.Column("waiting_for", sa.String(length=16), nullable=True),
        sa.Column("current_node", sa.String(length=64), nullable=True),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("assigned_agent_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["domain.party.party_id"],
        ),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("thread_id"),
        sa.UniqueConstraint("token_hmac"),
        schema="domain",
    )
    op.create_index(
        op.f("ix_domain_onboarding_session_last_activity_at"),
        "onboarding_session",
        ["last_activity_at"],
        unique=False,
        schema="domain",
    )
    op.create_table(
        "recommendation",
        sa.Column("recommendation_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=False),
        sa.Column("needs_assessment_id", sa.UUID(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("insurable_object_id", sa.UUID(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("eligibility_result", sa.String(length=16), nullable=False),
        sa.Column("failed_rule_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failed_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.String(length=16), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["needs_assessment_id"],
            ["domain.needs_assessment.needs_assessment_id"],
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["domain.party.party_id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_code"],
            ["catalog.product.product_code"],
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["domain.onboarding_session.session_id"],
        ),
        sa.PrimaryKeyConstraint("recommendation_id"),
        schema="domain",
    )
    op.create_index(
        op.f("ix_domain_recommendation_session_id"), "recommendation", ["session_id"], unique=False, schema="domain"
    )
    op.create_table(
        "quote",
        sa.Column("quote_id", sa.UUID(), nullable=False),
        sa.Column("recommendation_id", sa.UUID(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("insurable_object_id", sa.UUID(), nullable=False),
        sa.Column("coverages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("term_start_date", sa.Date(), nullable=False),
        sa.Column("term_end_date", sa.Date(), nullable=False),
        sa.Column("premium_minor", sa.Integer(), nullable=False),
        sa.Column("billing_period", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rating_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["domain.recommendation.recommendation_id"],
        ),
        sa.PrimaryKeyConstraint("quote_id"),
        schema="domain",
    )
    op.create_index(
        op.f("ix_domain_quote_recommendation_id"), "quote", ["recommendation_id"], unique=False, schema="domain"
    )
    op.create_table(
        "application",
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("recommendation_id", sa.UUID(), nullable=False),
        sa.Column("quote_id", sa.UUID(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("insurable_object_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("captured_by", sa.String(length=16), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["domain.quote.quote_id"],
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["domain.recommendation.recommendation_id"],
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["domain.onboarding_session.session_id"],
        ),
        sa.PrimaryKeyConstraint("application_id"),
        schema="domain",
    )
    op.create_index(
        op.f("ix_domain_application_session_id"), "application", ["session_id"], unique=False, schema="domain"
    )
    op.create_table(
        "application_party",
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("party_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["domain.application.application_id"],
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["domain.party.party_id"],
        ),
        sa.PrimaryKeyConstraint("application_id", "party_id", "role"),
        schema="domain",
    )


def downgrade() -> None:
    raise NotImplementedError("the baseline is not reversible; drop the database instead")
