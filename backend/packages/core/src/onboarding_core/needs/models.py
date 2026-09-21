"""Profiling: what the customer needs, and the things (devices, trips) they want to insure."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(eq=False, kw_only=True)
class NeedsAssessment:
    needs_assessment_id: uuid.UUID
    party_id: uuid.UUID
    session_id: uuid.UUID
    version: int
    age_range: str | None = None
    occupation: str | None = None
    residence_country: str | None = None
    existing_coverage: list[dict] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    objectives_note: str | None = None
    # Device/trip the customer described, kept with the version so a CHANGE re-derives objects.
    device: dict | None = None
    trip: dict | None = None
    captured_by: str = "CUSTOMER"
    missing_fields: list[str] = field(default_factory=list)
    completed_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(eq=False, kw_only=True)
class InsurableObject:
    insurable_object_id: uuid.UUID
    owner_party_id: uuid.UUID
    object_type: str
    source: str
    attributes: dict
