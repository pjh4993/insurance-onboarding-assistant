"""Catalog reference data: products, their eligibility rules and target markets."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(eq=False, kw_only=True)
class Product:
    product_code: str
    product_type: str
    marketing_name: str
    insurable_object_type: str
    coverages: list[dict]
    rating: dict
    billing_period: str
    currency: str
    jurisdictions: list[str]
    sale_effective_date: date
    sale_expiration_date: date | None = None
    term_rule: dict
    required_application_fields: list[str]
    status: str = "ACTIVE"


@dataclass(eq=False, kw_only=True)
class EligibilityRule:
    rule_id: uuid.UUID
    product_code: str
    subject: str
    attribute: str
    operator: str
    value: Any
    failure_reason_code: str
    description: str


@dataclass(eq=False, kw_only=True)
class TargetMarket:
    target_market_id: uuid.UUID
    product_code: str
    attribute: str
    values: list
    weight: float
    rationale: str
