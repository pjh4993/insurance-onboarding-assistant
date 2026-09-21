"""Customer-facing copy in the session's language (`ko` or `en`) and message constructors."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from onboarding_core.locale import Locale, default_locale
from onboarding_core.product_lines import LINES
from onboarding_core.util import iso


def locale_of(state: dict[str, Any]) -> Locale:
    """The language for copy and LLM replies. Checkpoints written before `locale` existed fall back to the market."""
    return state.get("locale") or default_locale(state["market"])


def t(locale: str, ko: str, en: str) -> str:
    return ko if locale == "ko" else en


def say(text: str, now: datetime) -> AIMessage:
    return AIMessage(content=text, id=str(uuid.uuid4()), additional_kwargs={"created_at": iso(now)})


def note(text: str, now: datetime) -> SystemMessage:
    return SystemMessage(content=text, id=str(uuid.uuid4()), additional_kwargs={"created_at": iso(now)})


def human(text: str, now: datetime, *, actor: str, input_type: str) -> HumanMessage:
    return HumanMessage(
        content=text,
        id=str(uuid.uuid4()),
        additional_kwargs={
            "created_at": iso(now),
            "role": "agent" if actor == "AGENT" else "customer",
            "input_type": input_type,
        },
    )


def money(amount_minor: int, currency: str) -> str:
    if currency == "KRW":
        return f"₩{amount_minor:,}"
    if currency == "USD":
        return f"${amount_minor / 100:,.2f}"
    return f"{amount_minor} {currency}"


BILLING = {
    "ko": {"MONTHLY": "월", "ONE_TIME": "1회", "PER_TRIP": "여행 1건"},
    "en": {"MONTHLY": "month", "ONE_TIME": "one-time", "PER_TRIP": "trip"},
}


def price_label(locale: str, premium_minor: int, currency: str, billing_period: str) -> str:
    unit = BILLING.get(locale, BILLING["en"]).get(billing_period, billing_period)
    return f"{money(premium_minor, currency)}/{unit}"


FIELD_LABELS: dict[str, tuple[str, str]] = {
    # profiling fields every line shares; line-specific labels come from the product lines
    "age_range": ("나이", "your age"),
    "residence_country": ("거주 국가", "your country of residence"),
    "objectives": ("무엇을 보장받고 싶은지", "what you want to protect"),
    **{field: label for line in LINES for field, label in line.field_labels.items()},
}


def field_list(locale: str, fields: list[str]) -> str:
    labels = [FIELD_LABELS.get(f, (f, f))[0 if locale == "ko" else 1] for f in fields]
    return ", ".join(labels)


def summarize_values(values: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v}" for k, v in values.items() if v not in (None, "", [], {}))


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return "*" * max(len(phone) - 4, 0) + phone[-4:]
