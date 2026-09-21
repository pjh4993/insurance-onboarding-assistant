"""Add onboarding_session.origin and client_ip_hash, for sessions customers start themselves.

Existing sessions all came from agent links, so they get AGENT_LINK. The two indexes serve the self-serve
rate limits, which count recent sessions globally and per client IP.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "onboarding_session",
        sa.Column("origin", sa.String(length=16), server_default="AGENT_LINK", nullable=False),
        schema="domain",
    )
    op.add_column(
        "onboarding_session", sa.Column("client_ip_hash", sa.String(length=64), nullable=True), schema="domain"
    )
    op.create_index(
        "ix_domain_onboarding_session_origin_started_at",
        "onboarding_session",
        ["origin", "started_at"],
        unique=False,
        schema="domain",
    )
    op.create_index(
        "ix_domain_onboarding_session_client_ip_hash_started_at",
        "onboarding_session",
        ["client_ip_hash", "started_at"],
        unique=False,
        schema="domain",
    )


def downgrade() -> None:
    op.drop_index("ix_domain_onboarding_session_client_ip_hash_started_at", "onboarding_session", schema="domain")
    op.drop_index("ix_domain_onboarding_session_origin_started_at", "onboarding_session", schema="domain")
    op.drop_column("onboarding_session", "client_ip_hash", schema="domain")
    op.drop_column("onboarding_session", "origin", schema="domain")
