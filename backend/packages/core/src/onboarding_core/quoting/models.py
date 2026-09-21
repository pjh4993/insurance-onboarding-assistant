"""A priced offer for one recommendation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(eq=False, kw_only=True)
class Quote:
    quote_id: uuid.UUID | None = None
    recommendation_id: uuid.UUID | None = None
    product_code: str
    insurable_object_id: uuid.UUID
    coverages: list[dict]
    term_start_date: date
    term_end_date: date
    premium_minor: int
    billing_period: str
    currency: str
    rating_inputs: dict
    status: str = "ISSUED"
    valid_until: datetime
    created_at: datetime
