"""Message constructors and value formatting for copy. The copy itself is in the config bundle."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from onboarding_agent.config import Bundle
from onboarding_core.locale import Locale, default_locale
from onboarding_core.util import iso


def locale_of(state: dict[str, Any]) -> Locale:
    """The language for copy and LLM replies. Checkpoints written before `locale` existed fall back to the market."""
    return state.get("locale") or default_locale(state["market"])


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


def price_label(bundle: Bundle, locale: str, premium_minor: int, currency: str, billing_period: str) -> str:
    return f"{money(premium_minor, currency)}/{bundle.billing_unit(locale, billing_period)}"


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return "*" * max(len(phone) - 4, 0) + phone[-4:]


def mask_id(number: str | None) -> str:
    """An ID document number for the transcript: only its last two characters."""
    if not number:
        return ""
    return "*" * max(len(number) - 2, 0) + number[-2:]
