"""Seed customers A-D and the lookups every mock system uses."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_SEED_PATH = Path(__file__).parent / "data" / "seed-customers.json"


@lru_cache(maxsize=1)
def customers() -> tuple[dict[str, Any], ...]:
    path = Path(os.environ.get("MOCK_SEED_PATH", DEFAULT_SEED_PATH))
    return tuple(json.loads(path.read_text(encoding="utf-8"))["customers"])


def norm_name(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def norm_email(value: str | None) -> str:
    return (value or "").strip().casefold()


def norm_phone(value: str | None) -> str:
    """Digits only; a Korean domestic number (010...) becomes E.164 digits (8210...)."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("010"):
        digits = "82" + digits[1:]
    return digits


def norm_document(value: str | None) -> str:
    return re.sub(r"[\s-]", "", value or "").upper()


def match_partner(full_name: str, email: str | None, phone: str | None) -> dict[str, Any] | None:
    """Full name plus (email or phone). Only customers with a partner record match."""
    for c in customers():
        if c["partner"] is None or norm_name(c["full_name"]) != norm_name(full_name):
            continue
        email_ok = bool(email) and norm_email(c["email"]) == norm_email(email)
        phone_ok = bool(phone) and norm_phone(c["phone"]) == norm_phone(phone)
        if email_ok or phone_ok:
            return c
    return None


def by_partner_ref(ref: str) -> dict[str, Any] | None:
    for c in customers():
        if c["partner"] and c["partner"]["partner_customer_ref"] == ref:
            return c
    return None


def by_phone(phone: str) -> dict[str, Any] | None:
    target = norm_phone(phone)
    return next((c for c in customers() if norm_phone(c["phone"]) == target), None) if target else None


def by_document(number: str) -> dict[str, Any] | None:
    target = norm_document(number)
    return next((c for c in customers() if norm_document(c["id_document_number"]) == target), None)


def find_in_text(text: str) -> dict[str, Any] | None:
    """The seed customer whose full name, email or needs text appears earliest in `text`."""
    folded = text.casefold()
    best: tuple[int, dict[str, Any]] | None = None
    for c in customers():
        for needle in (c["full_name"], c["email"], c.get("needs_text")):
            if not needle:
                continue
            pos = folded.find(needle.casefold())
            if pos >= 0 and (best is None or pos < best[0]):
                best = (pos, c)
    return best[1] if best else None
