"""HTTP clients for the partner, identity and contract systems (CONTRACTS.md §4). They implement the
`PartnerGateway`, `IdentityGateway` and `ContractGateway` ports of `onboarding_core.ports`.

Each takes an `httpx.AsyncClient` whose `base_url` is the system prefix, so tests can pass a client
built on `httpx.MockTransport`. Non-2xx responses raise `httpx.HTTPStatusError`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from onboarding_core.util import iso


@dataclass
class PartnerClient:
    http: httpx.AsyncClient

    @staticmethod
    def _headers(consent_at: datetime) -> dict[str, str]:
        return {"X-Consent-At": iso(consent_at) or ""}

    async def match_customer(self, *, full_name: str, email: str, phone: str, consent_at: datetime) -> dict[str, Any]:
        r = await self.http.post(
            "/v1/customers/match",
            json={"full_name": full_name, "email": email, "phone": phone},
            headers=self._headers(consent_at),
        )
        r.raise_for_status()
        return r.json()

    async def purchases(self, ref: str, *, consent_at: datetime) -> list[dict[str, Any]]:
        r = await self.http.get(f"/v1/customers/{ref}/purchases", headers=self._headers(consent_at))
        r.raise_for_status()
        return r.json().get("purchases", [])


@dataclass
class IdentityClient:
    http: httpx.AsyncClient

    async def send_otp(self, phone: str) -> dict[str, Any]:
        r = await self.http.post("/v1/otp", json={"phone": phone})
        r.raise_for_status()
        return r.json()

    async def verify_otp(self, otp_request_id: str, code: str) -> dict[str, Any]:
        r = await self.http.post(f"/v1/otp/{otp_request_id}/verify", json={"code": code})
        r.raise_for_status()
        return r.json()

    async def verify_document(
        self, *, document_type: str, document_number: str, full_name: str, date_of_birth: str | None
    ) -> dict[str, Any]:
        r = await self.http.post(
            "/v1/documents/verify",
            json={
                "document_type": document_type,
                "document_number": document_number,
                "full_name": full_name,
                "date_of_birth": date_of_birth,
            },
        )
        r.raise_for_status()
        return r.json()


@dataclass
class ContractClient:
    http: httpx.AsyncClient

    async def submit_application(self, application_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = await self.http.post("/v1/applications", json=payload, headers={"Idempotency-Key": application_id})
        r.raise_for_status()
        return r.json()


def make_http(base_url: str, timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)
