"""Device protection and extended warranty: phones, tablets, notebooks, TVs, appliances, wearables."""

from __future__ import annotations

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


def normalize_device_category(value: Any) -> str | None:
    if not value:
        return None
    key = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    return CATEGORY_ALIASES.get(key, key)


class DeviceLine(ProductLine):
    code = "DEVICE"
    object_type = "DEVICE"
    needs_key = "device"
    objectives = frozenset({"PROTECT_DEVICE", "EXTEND_WARRANTY"})
    answer_aliases = {
        "purchase_price": ("purchase_price_minor", "price_minor", "price"),
        "device_model": ("model",),
        "msrp": ("msrp_minor",),
        "order_number": ("order_id", "order_no"),
        "imei": ("serial_number",),
    }
    field_labels = {
        "device.device_category": ("기기 종류", "the device type"),
        "device.purchase_date": ("기기 구매일", "the device purchase date"),
        "device.purchase_price_minor": ("기기 구매 가격", "the device purchase price"),
        "imei": ("IMEI 번호", "the IMEI number"),
        "device_model": ("기기 모델명", "the device model"),
        "msrp": ("기기 출고가", "the device list price (MSRP)"),
        "activation_date": ("개통일", "the activation date"),
        "serial_number": ("시리얼 번호", "the serial number"),
        "purchase_date": ("구매일", "the purchase date"),
        "purchase_price": ("구매 가격", "the purchase price"),
        "proof_of_purchase": ("구매 증빙", "proof of purchase"),
        "order_number": ("주문 번호", "the order number"),
    }

    def required_needs(self, market: str) -> tuple[str, ...]:
        # purchase_date is not required here: when unknown, eligibility assumes "bought today" and
        # the application step asks for the real date (see object_attributes / prefill).
        return ("device_category", "purchase_price_minor")

    def normalize_needs(self, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("device_category"):
            values["device_category"] = normalize_device_category(values["device_category"])
        return values

    def object_attributes(self, values: dict[str, Any], *, residence_country: str | None, today: date) -> dict:
        attrs = {k: v for k, v in values.items() if v is not None}
        if attrs.get("device_category"):
            attrs["device_category"] = normalize_device_category(attrs["device_category"])
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
