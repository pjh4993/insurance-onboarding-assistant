"""Deterministic LLM outputs per tool name and seed customer.

Shapes mirror CONTRACTS.md §5 (NeedsExtraction, RecommendationRationale, PartiesExtraction,
AnswersExtraction, ApplicationSummary). Every fixture sets every field, including nullable ones,
so a Pydantic model with required-but-nullable fields validates.
"""

from __future__ import annotations

import re
from typing import Any

NEEDS_FIELDS = [
    "age_range",
    "occupation",
    "residence_country",
    "existing_coverage",
    "objectives",
    "device",
    "trip",
]

NEEDS: dict[str, dict[str, Any]] = {
    "A": {
        "age_range": "AGE_30_39",
        "occupation": "Software engineer",
        "residence_country": "KR",
        "existing_coverage": [],
        "objectives": ["PROTECT_DEVICE"],
        "device": {
            "device_category": "SMARTPHONE",
            "manufacturer": "Samsung",
            "model": "Galaxy S26",
            "purchase_date": "2026-09-14",
            "purchase_price_minor": 1350000,
        },
        "trip": None,
        "missing_fields": [],
    },
    "B": {
        "age_range": "AGE_40_49",
        "occupation": "Office worker",
        "residence_country": "KR",
        "existing_coverage": [],
        "objectives": ["TRAVEL_COVER"],
        "device": None,
        "trip": {
            "destination_countries": ["JP"],
            "departure_date": "2026-10-03",
            "return_date": "2026-10-07",
            "trip_cost_minor": None,
        },
        "missing_fields": [],
    },
    "C": {
        "age_range": "AGE_30_39",
        "occupation": "Nurse",
        "residence_country": "US",
        "existing_coverage": [],
        "objectives": ["PROTECT_DEVICE"],
        "device": {
            "device_category": "LAPTOP",
            "manufacturer": None,
            "model": None,
            "purchase_date": None,
            "purchase_price_minor": 129900,
        },
        "trip": None,
        "missing_fields": [],
    },
    "D": {
        "age_range": None,
        "occupation": None,
        "residence_country": None,
        "existing_coverage": [],
        "objectives": ["PROTECT_DEVICE"],
        "device": {
            "device_category": "SMARTPHONE",
            "manufacturer": None,
            "model": None,
            "purchase_date": None,
            "purchase_price_minor": None,
        },
        "trip": None,
        "missing_fields": ["age_range", "occupation", "residence_country"],
    },
}

PARTIES: dict[str, dict[str, Any]] = {key: {"all_self": True, "parties": []} for key in ("A", "B", "C", "D")}

ANSWERS: dict[str, dict[str, Any]] = {
    "A": {
        "answers": {
            "serial_number": "350000000000012",
            "device_model": "Galaxy S26",
            "purchase_date": "2026-09-14",
            "purchase_price": 1350000,
            "device_condition_confirmed": True,
            "payment_method": "CARD",
        },
        "missing_fields": [],
    },
    "B": {
        "answers": {
            "destination_countries": ["JP"],
            "departure_date": "2026-10-03",
            "return_date": "2026-10-07",
            "payment_method": "CARD",
        },
        "missing_fields": [],
    },
    "C": {
        "answers": {
            "serial_number": "C02XK0AAJG5H",
            "device_model": "Laptop",
            "purchase_price": 129900,
            "purchase_date": "2026-09-10",
            "device_condition_confirmed": True,
            "payment_method": "CARD",
        },
        "missing_fields": [],
    },
    "D": {
        "answers": {"payment_method": "CARD"},
        "missing_fields": ["serial_number", "purchase_date"],
    },
}

SUMMARY: dict[str, str] = {
    "A": (
        "김하늘 님(1991-03-14생)이 2026-09-14에 구매한 Samsung Galaxy S26(구매가 1,350,000원)의 "
        "기기 보험을 신청합니다. 계약자와 피보험자는 본인이며, 결제 수단은 카드입니다."
    ),
    "B": (
        "이서준 님(1985-11-02생)이 2026-10-03부터 2026-10-07까지 일본 여행을 위한 여행자 보험을 "
        "신청합니다. 계약자와 피보험자는 본인이며, 결제 수단은 카드입니다."
    ),
    "C": (
        "Jane Doe (born 1990-06-01) is applying for accident cover on a laptop bought for $1,299. "
        "She is both the policyholder and the insured, and pays by card."
    ),
    "D": (
        "John Roe (born 1978-01-20) is applying for smartphone protection. He is both the policyholder "
        "and the insured; the serial number and purchase date are still to be confirmed."
    ),
}
GENERIC_SUMMARY = (
    "The customer is applying for the selected product as both policyholder and insured, "
    "with the answers collected in this session."
)

TEXT_REPLY = {"KR": "네, 확인했습니다. 이어서 도와드릴게요.", "US": "Thanks, got it. Let's continue."}


def generic_needs(text: str) -> dict[str, Any]:
    """Keyword fallback for a customer the mock does not know."""
    lowered = text.casefold()
    objectives: list[str] = []
    device = None
    trip = None
    if any(w in lowered for w in ("travel", "trip", "여행")):
        objectives.append("TRAVEL_COVER")
        trip = {
            "destination_countries": [],
            "departure_date": None,
            "return_date": None,
            "trip_cost_minor": None,
        }
    if any(w in lowered for w in ("warranty", "보증")):
        objectives.append("EXTEND_WARRANTY")
    category = None
    if any(w in lowered for w in ("phone", "폰", "휴대")):
        category = "SMARTPHONE"
    elif any(w in lowered for w in ("laptop", "노트북")):
        category = "LAPTOP"
    elif any(w in lowered for w in ("tablet", "태블릿")):
        category = "TABLET"
    if category:
        objectives.insert(0, "PROTECT_DEVICE")
        device = {
            "device_category": category,
            "manufacturer": None,
            "model": None,
            "purchase_date": None,
            "purchase_price_minor": None,
        }
    missing = ["age_range", "occupation", "residence_country"]
    if not objectives:
        missing.append("objectives")
    return {
        "age_range": None,
        "occupation": None,
        "residence_country": None,
        "existing_coverage": [],
        "objectives": objectives,
        "device": device,
        "trip": trip,
        "missing_fields": missing,
    }


# --- RecommendationRationale ---------------------------------------------------------------------------

_REC_ID = re.compile(r"""recommendation_id["']?\s*[:=]\s*["']?([A-Za-z0-9][A-Za-z0-9_.\-]*)""")


def _field(segment: str, name: str) -> str | None:
    m = re.search(name + r"""["']?\s*[:=]\s*["']?([^"'\n,}]+)""", segment)
    return m.group(1).strip() if m else None


def find_recommendations(text: str) -> list[dict[str, str | None]]:
    """Each distinct recommendation_id in `text`, with product hints from the text around it."""
    matches = list(_REC_ID.finditer(text))
    # Each recommendation's text starts at the '{' or line break that opens it, so the fields of the
    # previous recommendation are not read as this one's.
    starts = []
    for i, m in enumerate(matches):
        floor = matches[i - 1].end() if i else max(0, m.start() - 300)
        opener = max(text.rfind("{", floor, m.start()), text.rfind("\n", floor, m.start()))
        starts.append(opener if opener >= 0 else m.start())
    found: dict[str, dict[str, str | None]] = {}
    for i, m in enumerate(matches):
        rec_id = m.group(1)
        if rec_id in found:
            continue
        end = starts[i + 1] if i + 1 < len(matches) else m.end() + 600
        segment = text[starts[i] : end]
        found[rec_id] = {
            "recommendation_id": rec_id,
            "marketing_name": _field(segment, "marketing_name"),
            "product_type": _field(segment, "product_type"),
            "product_code": _field(segment, "product_code"),
            "eligibility_result": _field(segment, "eligibility_result"),
        }
    return list(found.values())


_KR_RATIONALE = {
    "A": {
        "TRAVEL": "여행 계획이 없으셔서 지금은 필요성이 낮지만 비교용으로 보여 드립니다.",
        "WARRANTY": "제조사 보증이 끝난 뒤에도 Galaxy S26 고장 수리비를 보장합니다.",
        "DEVICE": "9월 14일에 산 Galaxy S26의 파손 수리비를 보장해 걱정하신 부분에 바로 맞습니다.",
    },
    "B": {
        "TRAVEL": "10월 3일부터 7일까지 일본 여행 중 의료비와 여행 취소 손해를 보장합니다.",
        "WARRANTY": "여행 보장이 목적이라 우선순위는 낮지만 비교용으로 보여 드립니다.",
        "DEVICE": "여행 보장이 목적이라 우선순위는 낮지만 비교용으로 보여 드립니다.",
    },
}
_EN_RATIONALE = {
    "C": {
        "TRAVEL": "You did not mention a trip, so this is shown for comparison only.",
        "WARRANTY": "Extends repair cover for your new laptop after the manufacturer warranty ends.",
        "DEVICE": "Covers accidental damage to the $1,299 laptop you just bought, as you asked.",
    },
    "D": {
        "TRAVEL": "You did not mention a trip, so this is shown for comparison only.",
        "WARRANTY": "Extends repair cover for your phone after the manufacturer warranty ends.",
        "DEVICE": "Covers accidental damage and breakdown for your phone, matching the cover you asked for.",
    },
}


def _category(rec: dict[str, str | None]) -> str | None:
    hint = " ".join(v for k, v in rec.items() if k != "recommendation_id" and v).upper()
    for key in ("TRAVEL", "WARRANTY", "DEVICE"):
        if key in hint:
            return key
    if any(w in hint for w in ("PHONE", "SCREEN", "GADGET", "PROTECT")):
        return "DEVICE"
    return None


def rationale_for(rec: dict[str, str | None], customer_key: str | None) -> str:
    name = rec.get("marketing_name") or rec.get("product_code") or "This product"
    korean = customer_key in _KR_RATIONALE
    if (rec.get("eligibility_result") or "").upper() == "INELIGIBLE":
        if korean:
            return f"{name}은(는) 가입 조건에 맞지 않아 비교용으로만 보여 드립니다."
        return f"{name} is shown for comparison only because you do not meet its eligibility rules."
    category = _category(rec)
    table = _KR_RATIONALE.get(customer_key or "") or _EN_RATIONALE.get(customer_key or "")
    if table and category:
        return table[category]
    if korean:
        return f"{name}은(는) 말씀하신 필요에 맞는 보장을 제공합니다."
    return f"{name} matches the needs you described."
