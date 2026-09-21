"""The insurance application and the parties named on it."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Application:
    application_id: uuid.UUID
    session_id: uuid.UUID
    recommendation_id: uuid.UUID
    quote_id: uuid.UUID
    product_code: str
    insurable_object_id: uuid.UUID | None = None
    status: str = "DRAFT"
    answers: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    summary: str | None = None
    captured_by: str = "CUSTOMER"
    submitted_at: datetime | None = None
    submission_ref: str | None = None


@dataclass(eq=False, kw_only=True)
class ApplicationParty:
    application_id: uuid.UUID
    party_id: uuid.UUID
    role: str
