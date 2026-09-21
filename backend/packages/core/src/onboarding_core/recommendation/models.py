"""A product proposed to the customer, with its eligibility outcome and the customer's decision."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Recommendation:
    recommendation_id: uuid.UUID
    session_id: uuid.UUID
    party_id: uuid.UUID
    needs_assessment_id: uuid.UUID
    product_code: str
    insurable_object_id: uuid.UUID | None = None
    rank: int = 0
    score: float = 0.0
    eligibility_result: str
    failed_rule_ids: list[str] = field(default_factory=list)
    failed_reasons: list[str] = field(default_factory=list)
    rationale: str | None = None
    status: str = "PROPOSED"
    decided_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime | None = None
