"""Eligibility rules and ranking. Code decides; the LLM only explains (lifecycle.md §3).

A rule reads `subject.attribute`, compares it with `operator value`, and fails on a missing value."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.domain.pricing import trip_length_days
from app.util import parse_date

AGE_RANGE_LOWER_BOUND = {
    "AGE_UNDER_19": 0,
    "AGE_19_29": 19,
    "AGE_30_39": 30,
    "AGE_40_49": 40,
    "AGE_50_64": 50,
    "AGE_65_PLUS": 65,
}


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    subject: str
    attribute: str
    operator: str
    value: Any
    failure_reason_code: str
    description: str


@dataclass
class EligibilityOutcome:
    eligible: bool
    failed_rules: list[RuleSpec] = field(default_factory=list)

    @property
    def failed_rule_ids(self) -> list[str]:
        return [r.rule_id for r in self.failed_rules]

    @property
    def failed_reasons(self) -> list[str]:
        return [f"{r.failure_reason_code}: {r.description}" for r in self.failed_rules]


def age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def derived_values(
    party: dict[str, Any], needs: dict[str, Any], obj: dict[str, Any] | None, today: date
) -> dict[str, Any]:
    """Values the catalog calls DERIVED: trip_length_days, applicant_age, days_until_departure."""
    attrs = (obj or {}).get("attributes", {})
    out: dict[str, Any] = {}
    days = trip_length_days(attrs)
    if days is not None:
        out["trip_length_days"] = days
    dep = parse_date(attrs.get("departure_date"))
    if dep is not None:
        out["days_until_departure"] = (dep - today).days
    dob = parse_date(party.get("date_of_birth"))
    if dob is not None:
        out["applicant_age"] = age_on(dob, today)
    elif needs.get("age_range") in AGE_RANGE_LOWER_BOUND:
        # No verified birth date (e.g. OTP path): use the lower bound of the stated age range.
        out["applicant_age"] = AGE_RANGE_LOWER_BOUND[needs["age_range"]]
    return out


def _lookup(source: dict[str, Any] | None, path: str) -> Any:
    cur: Any = source
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _norm(v: Any) -> Any:
    return v.casefold() if isinstance(v, str) else v


def _as_comparable(actual: Any, expected: Any) -> tuple[Any, Any]:
    """Dates compare with dates; everything else as-is."""
    if isinstance(expected, str) and parse_date(expected) and not isinstance(actual, (int, float)):
        return parse_date(actual), parse_date(expected)
    return actual, expected


def evaluate_rule(rule: RuleSpec, context: dict[str, dict[str, Any] | None], today: date) -> bool:
    actual = _lookup(context.get(rule.subject), rule.attribute)
    if actual is None:
        return False
    op, expected = rule.operator, rule.value
    if op == "EQ":
        return _norm(actual) == _norm(expected)
    if op == "IN":
        allowed = {_norm(v) for v in expected}
        if isinstance(actual, list):
            return bool(actual) and all(_norm(v) in allowed for v in actual)
        return _norm(actual) in allowed
    if op in ("GTE", "LTE"):
        a, e = _as_comparable(actual, expected)
        if a is None or e is None:
            return False
        try:
            return a >= e if op == "GTE" else a <= e
        except TypeError:
            return False
    if op == "WITHIN_DAYS":
        d = parse_date(actual)
        if d is None:
            return False
        elapsed = (today - d).days
        return 0 <= elapsed <= int(expected)
    raise ValueError(f"unknown operator {op!r}")


def evaluate_product(
    rules: list[RuleSpec],
    *,
    party: dict[str, Any],
    needs: dict[str, Any],
    obj: dict[str, Any] | None,
    today: date,
) -> EligibilityOutcome:
    context = {
        "PARTY": party,
        "NEEDS_ASSESSMENT": needs,
        "INSURABLE_OBJECT": obj,
        "DERIVED": derived_values(party, needs, obj, today),
    }
    failed = [r for r in rules if not evaluate_rule(r, context, today)]
    return EligibilityOutcome(eligible=not failed, failed_rules=failed)


def target_market_score(target_markets: list[dict[str, Any]], needs: dict[str, Any]) -> tuple[float, list[str]]:
    """Sum of weights whose `values` match the needs attribute; returns (score, matched rationales)."""
    score, rationales = 0.0, []
    for tm in target_markets:
        actual = needs.get(tm["attribute"])
        actual_values = actual if isinstance(actual, list) else [actual]
        if any(v is not None and v in tm["values"] for v in actual_values):
            score += float(tm["weight"])
            rationales.append(tm["rationale"])
    return round(score, 4), rationales


def rank_order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Eligible first by score (desc), then ineligible; ties broken by product code."""
    return sorted(
        items,
        key=lambda i: (i["eligibility_result"] != "ELIGIBLE", -i["score"], i["product_code"]),
    )
