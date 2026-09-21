"""A session's language. It defaults to its market's; the customer or an agent can change it later."""

from __future__ import annotations

from typing import Literal

Locale = Literal["ko", "en"]

DEFAULT_LOCALE: dict[str, Locale] = {"KR": "ko", "US": "en"}


def default_locale(market: str) -> Locale:
    return DEFAULT_LOCALE.get(market, "en")
