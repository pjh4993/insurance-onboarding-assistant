"""Add onboarding_session.locale, the session's language.

Existing sessions get their market's language, which is what they were already using.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onboarding_session", sa.Column("locale", sa.String(length=5), nullable=True), schema="domain")
    op.execute("UPDATE domain.onboarding_session SET locale = CASE market WHEN 'KR' THEN 'ko' ELSE 'en' END")
    op.alter_column("onboarding_session", "locale", nullable=False, schema="domain")


def downgrade() -> None:
    op.drop_column("onboarding_session", "locale", schema="domain")
