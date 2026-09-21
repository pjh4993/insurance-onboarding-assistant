"""Registered product lines, in the order profiling asks about them."""

from __future__ import annotations

from onboarding_core.product_lines.base import ProductLine
from onboarding_core.product_lines.device import DEVICE
from onboarding_core.product_lines.travel import TRAVEL

LINES: tuple[ProductLine, ...] = (DEVICE, TRAVEL)


def line_for_object_type(object_type: str) -> ProductLine:
    for line in LINES:
        if line.object_type == object_type:
            return line
    raise LookupError(f"no product line insures {object_type!r} objects")


__all__ = ["LINES", "ProductLine", "line_for_object_type"]
