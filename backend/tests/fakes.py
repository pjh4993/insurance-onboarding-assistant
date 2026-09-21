"""In-process fakes for the external systems (CONTRACTS.md §4) and the LLM (§5).

`FakeExternal` is an `httpx.MockTransport` handler that behaves like the mock server for the seed
customers; `FakeLLM` returns §5 shapes chosen by schema name and by which seed customer's name
appears in the prompt — the same selection rule the mock server uses."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from langchain_core.messages import BaseMessage

SEED = json.loads((Path(__file__).parent / "fixtures" / "seed-customers.json").read_text())["customers"]
CUSTOMERS = {c["key"]: c for c in SEED}


def identity_input(key: str, *, consent: bool, with_dob: bool = False) -> dict[str, Any]:
    c = CUSTOMERS[key]
    data = {
        "full_name": c["full_name"],
        "email": c["email"],
        "phone": c["phone"],
        "id_document_type": c["id_document_type"],
        "id_document_number": c["id_document_number"],
        "third_party_consent": consent,
    }
    if with_dob:
        data["date_of_birth"] = c["date_of_birth"]
    return data


class FakeExternal:
    """Partner, identity and contract systems. `fail[target] = n` fails the next n calls with 500."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], Any]] = []
        self.fail: Counter[str] = Counter()
        self.otps: dict[str, str] = {}
        self.submissions: dict[str, dict[str, Any]] = {}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def _customer_by(self, field: str, value: Any) -> dict[str, Any] | None:
        return next((c for c in SEED if c.get(field) == value), None)

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, dict(request.headers), body))
        target = path.strip("/").split("/")[0]
        if self.fail[target] > 0:
            self.fail[target] -= 1
            return httpx.Response(500, json={"error": "injected"})

        if path == "/partner/v1/customers/match":
            if not request.headers.get("x-consent-at"):
                return httpx.Response(403, json={"error": "consent required"})
            c = self._customer_by("email", body["email"])
            if c and c["partner"] and c["full_name"] == body["full_name"]:
                return httpx.Response(
                    200,
                    json={
                        "matched": True,
                        "partner_customer_ref": c["partner"]["partner_customer_ref"],
                        "date_of_birth": c["date_of_birth"],
                    },
                )
            return httpx.Response(200, json={"matched": False})
        m = re.fullmatch(r"/partner/v1/customers/([^/]+)/purchases", path)
        if m:
            if not request.headers.get("x-consent-at"):
                return httpx.Response(403, json={"error": "consent required"})
            c = next((c for c in SEED if c["partner"] and c["partner"]["partner_customer_ref"] == m[1]), None)
            return httpx.Response(200, json={"purchases": c["partner"]["purchases"] if c else []})
        if path == "/identity/v1/otp":
            otp_id = f"otp-{len(self.otps) + 1}"
            self.otps[otp_id] = body["phone"]
            expires = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            return httpx.Response(201, json={"otp_request_id": otp_id, "expires_at": expires})
        m = re.fullmatch(r"/identity/v1/otp/([^/]+)/verify", path)
        if m:
            c = self._customer_by("phone", self.otps.get(m[1]))
            valid = c and c["otp"] and c["otp"]["valid_code"]
            ok = bool(valid) and body["code"] == valid
            return httpx.Response(200, json={"verified": ok, **({} if ok else {"reason": "MISMATCH"})})
        if path == "/identity/v1/documents/verify":
            c = self._customer_by("id_document_number", body["document_number"])
            ok = bool(
                c
                and c["document_valid"]
                and c["full_name"] == body["full_name"]
                and body.get("date_of_birth") in (None, c["date_of_birth"])
            )
            return httpx.Response(200, json={"verified": ok, **({} if ok else {"reason": "NOT_FOUND"})})
        if path == "/contract/v1/applications":
            key = request.headers.get("idempotency-key")
            if not key:
                return httpx.Response(400, json={"error": "Idempotency-Key required"})
            if key in self.submissions:
                return httpx.Response(200, json=self.submissions[key]["response"])
            resp = {
                "submission_ref": f"SUB-2026-{len(self.submissions) + 1:06d}",
                "status": "RECEIVED",
                "received_at": datetime.now(UTC).isoformat(),
            }
            self.submissions[key] = {"request": body, "response": resp}
            return httpx.Response(201, json=resp)
        return httpx.Response(404, json={"error": f"no route {path}"})


NEEDS = {
    "A": {
        "age_range": "AGE_30_39",
        "occupation": "소프트웨어 엔지니어",
        "residence_country": "KR",
        "objectives": ["PROTECT_DEVICE"],
        "device": {"device_category": "SMARTPHONE", "manufacturer": "Samsung", "model": "Galaxy S26"},
    },
    "B": {
        "age_range": "AGE_40_49",
        "occupation": "회사원",
        "residence_country": "KR",
        "objectives": ["TRAVEL_COVER"],
        "trip": {"destination_countries": ["JP"], "departure_date": "2026-10-03", "return_date": "2026-10-07"},
    },
    "C": {
        "age_range": "AGE_30_39",
        "occupation": "Nurse",
        "residence_country": "US",
        "objectives": ["PROTECT_DEVICE"],
        # mirrors the mock server fixture: "LAPTOP" and no purchase date
        "device": {
            "device_category": "LAPTOP",
            "manufacturer": None,
            "model": None,
            "purchase_date": None,
            "purchase_price_minor": 129900,
        },
    },
    "D": {
        "age_range": None,
        "occupation": None,
        "residence_country": None,
        "objectives": ["PROTECT_DEVICE"],
        "device": {"device_category": "SMARTPHONE"},
        "missing_fields": ["age_range", "occupation", "residence_country"],
    },
}
ANSWERS = {
    "A": {},
    "B": {"traveler_date_of_birth": "1985-11-02", "traveler_gender": "M"},
    "C": {"serial_number": "SN-C-0001", "order_id": "ORD-C-42", "purchase_date": "2026-09-10"},
    "D": {},
}


class FakeLLM:
    """`fail[node] = n` raises a (retryable) ValueError on the next n calls of that node."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.fail: Counter[str] = Counter()
        self.overrides: dict[str, Any] = {}

    @staticmethod
    def _customer(text: str) -> str | None:
        for c in SEED:
            if c["full_name"] in text or c["email"] in text:
                return c["key"]
        return None

    async def extract(self, node: str, schema: type, messages: list[BaseMessage]) -> Any:
        text = "\n".join(str(m.content) for m in messages)
        key = self._customer(text)
        self.calls.append((node, schema.__name__, key or ""))
        if self.fail[node] > 0:
            self.fail[node] -= 1
            raise ValueError("injected LLM failure")
        name = schema.__name__
        if name in self.overrides:
            return schema.model_validate(self.overrides[name])
        if name == "NeedsExtraction":
            return schema.model_validate(NEEDS.get(key or "D", NEEDS["D"]))
        if name == "RecommendationRationale":
            ids = re.findall(r"recommendation_id:\s*([0-9a-f-]{36})", text)
            return schema.model_validate(
                {"items": [{"recommendation_id": i, "rationale": f"Fits you ({key})."} for i in ids]}
            )
        if name == "PartiesExtraction":
            return schema.model_validate({"all_self": True, "parties": []})
        if name == "AnswersExtraction":
            return schema.model_validate({"answers": ANSWERS.get(key or "D", {}), "missing_fields": []})
        if name == "ApplicationSummary":
            return schema.model_validate({"summary": f"Application summary for {key}."})
        raise AssertionError(f"unexpected schema {name}")
