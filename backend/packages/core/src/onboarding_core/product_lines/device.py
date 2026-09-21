"""Device protection and extended warranty: phones, tablets, notebooks, TVs, appliances, wearables."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from onboarding_core.party.models import Party
from onboarding_core.product_lines.base import ProductLine

CATEGORY_ALIASES = {
    "LAPTOP": "NOTEBOOK",
    "NOTEBOOK_COMPUTER": "NOTEBOOK",
    "COMPUTER": "NOTEBOOK",
    "PHONE": "SMARTPHONE",
    "MOBILE": "SMARTPHONE",
    "MOBILE_PHONE": "SMARTPHONE",
    "CELLPHONE": "SMARTPHONE",
    "CELL_PHONE": "SMARTPHONE",
    "HANDSET": "SMARTPHONE",
    "TELEVISION": "TV",
    "IPAD": "TABLET",
    "PAD": "TABLET",
    "WATCH": "WEARABLE",
    "SMARTWATCH": "WEARABLE",
    "SMART_WATCH": "WEARABLE",
}


# Makers as customers name them (Korean, product lines) -> the catalog's names (eligibility compares exactly).
MANUFACTURER_ALIASES = {
    "삼성": "Samsung",
    "삼성전자": "Samsung",
    "갤럭시": "Samsung",
    "GALAXY": "Samsung",
    "SAMSUNG": "Samsung",
    "애플": "Apple",
    "아이폰": "Apple",
    "IPHONE": "Apple",
    "APPLE": "Apple",
    "LG": "LG",
    "엘지": "LG",
    "LG전자": "LG",
}


def normalize_manufacturer(value: Any) -> str | None:
    if not value:
        return None
    name = str(value).strip()
    return MANUFACTURER_ALIASES.get(name.upper().replace(" ", ""), name)


def normalize_device_category(value: Any) -> str | None:
    if not value:
        return None
    key = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    return CATEGORY_ALIASES.get(key, key)


class DeviceLine(ProductLine):
    code = "DEVICE"
    object_type = "DEVICE"
    needs_key = "device"
    needs_fields = ("device_category", "purchase_price_minor", "manufacturer")
    objectives = frozenset({"PROTECT_DEVICE", "EXTEND_WARRANTY"})
    answer_aliases = {
        "purchase_price": ("purchase_price_minor", "price_minor", "price"),
        "device_model": ("model",),
        "msrp": ("msrp_minor",),
        "order_number": ("order_id", "order_no"),
        "imei": ("serial_number",),
    }

    def required_needs(self, market: str, values: Mapping[str, Any]) -> tuple[str, ...]:
        # purchase_date is not required here: when unknown, eligibility assumes "bought today" and
        # the application step asks for the real date (see object_attributes / prefill).
        keys = ("device_category", "purchase_price_minor")
        # Phone cover is limited to some makers, so a phone's maker decides eligibility: ask, never assume.
        if normalize_device_category(values.get("device_category")) == "SMARTPHONE":
            return (*keys, "manufacturer")
        return keys

    def normalize_needs(self, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("device_category"):
            values["device_category"] = normalize_device_category(values["device_category"])
        if values.get("manufacturer"):
            values["manufacturer"] = normalize_manufacturer(values["manufacturer"])
        return values

    def object_attributes(self, values: dict[str, Any], *, residence_country: str | None, today: date) -> dict:
        attrs = {k: v for k, v in values.items() if v is not None}
        if attrs.get("device_category"):
            attrs["device_category"] = normalize_device_category(attrs["device_category"])
        if attrs.get("manufacturer"):
            attrs["manufacturer"] = normalize_manufacturer(attrs["manufacturer"])
        # Assumptions, recorded in `assumed_fields` so they are never copied into the application:
        # a device the customer is insuring now is new, undamaged and was bought today unless stated.
        assumed = []
        for key, default in (
            ("condition", "NEW"),
            ("has_existing_damage", False),
            ("purchase_date", today.isoformat()),
        ):
            if key not in attrs:
                attrs[key] = default
                assumed.append(key)
        # A new phone is activated the day it is bought (phone cover's eligibility window runs from activation).
        if attrs.get("device_category") == "SMARTPHONE" and "activation_date" not in attrs:
            attrs["activation_date"] = attrs["purchase_date"]
            assumed.append("activation_date")
        if assumed:
            attrs["assumed_fields"] = assumed
        return attrs

    def prefill(self, attrs: dict[str, Any], insured: Party | None, today: date) -> dict[str, Any]:
        a = attrs
        return {
            "imei": a.get("imei"),
            "device_model": " ".join(x for x in (a.get("manufacturer"), a.get("model")) if x) or None,
            "msrp": a.get("msrp_minor") or a.get("purchase_price_minor"),
            "activation_date": a.get("activation_date"),
            "serial_number": a.get("serial_number"),
            "purchase_date": a.get("purchase_date"),
            "purchase_price": a.get("purchase_price_minor"),
            "order_number": a.get("order_id"),
            "proof_of_purchase": f"partner order {a['order_id']}" if a.get("order_id") else None,
        }


DEVICE = DeviceLine()
