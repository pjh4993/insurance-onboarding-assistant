"""Customer-facing copy (KR in Korean, US in English) and message constructors."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.util import iso


def t(market: str, ko: str, en: str) -> str:
    return ko if market == "KR" else en


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
    "KR": {"MONTHLY": "월", "ONE_TIME": "1회", "PER_TRIP": "여행 1건"},
    "US": {"MONTHLY": "month", "ONE_TIME": "one-time", "PER_TRIP": "trip"},
}


def price_label(market: str, premium_minor: int, currency: str, billing_period: str) -> str:
    unit = BILLING.get(market, BILLING["US"]).get(billing_period, billing_period)
    return f"{money(premium_minor, currency)}/{unit}"


FIELD_LABELS: dict[str, tuple[str, str]] = {
    # needs
    "age_range": ("나이", "your age"),
    "residence_country": ("거주 국가", "your country of residence"),
    "objectives": ("무엇을 보장받고 싶은지", "what you want to protect"),
    "device.device_category": ("기기 종류", "the device type"),
    "device.purchase_date": ("기기 구매일", "the device purchase date"),
    "device.purchase_price_minor": ("기기 구매 가격", "the device purchase price"),
    "trip.departure_date": ("출발일", "your departure date"),
    "trip.return_date": ("귀국일", "your return date"),
    "trip.destination_countries": ("여행지", "your destination"),
    "trip.trip_cost_minor": ("여행 경비 총액", "the total trip cost"),
    # application
    "imei": ("IMEI 번호", "the IMEI number"),
    "device_model": ("기기 모델명", "the device model"),
    "msrp": ("기기 출고가", "the device list price (MSRP)"),
    "activation_date": ("개통일", "the activation date"),
    "serial_number": ("시리얼 번호", "the serial number"),
    "purchase_date": ("구매일", "the purchase date"),
    "purchase_price": ("구매 가격", "the purchase price"),
    "proof_of_purchase": ("구매 증빙", "proof of purchase"),
    "order_number": ("주문 번호", "the order number"),
    "departure_date": ("출발일", "the departure date"),
    "return_date": ("귀국일", "the return date"),
    "destination": ("여행지", "the destination"),
    "traveler_name": ("여행자 이름", "the traveller's name"),
    "traveler_date_of_birth": ("여행자 생년월일", "the traveller's date of birth"),
    "traveler_gender": ("여행자 성별", "the traveller's gender"),
    "traveler_age": ("여행자 나이", "the traveller's age"),
    "trip_cost": ("여행 경비 총액", "the total trip cost"),
}


def field_list(market: str, fields: list[str]) -> str:
    labels = [FIELD_LABELS.get(f, (f, f))[0 if market == "KR" else 1] for f in fields]
    return ", ".join(labels)


def summarize_values(values: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v}" for k, v in values.items() if v not in (None, "", [], {}))
