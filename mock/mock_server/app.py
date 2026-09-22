"""One FastAPI app serving the partner, identity, contract and Bedrock mocks plus /_mock controls."""

from __future__ import annotations

import asyncio
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import bedrock, seed
from .state import STATE, Kind, OtpRequest, Target, otp_ttl_seconds

app = FastAPI(title="Onboarding mock servers", version="0.1.0")


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def inject_fault(target: Target) -> JSONResponse | None:
    """Consume one armed fault for `target`. Returns the error response, or None to proceed."""
    fault = STATE.take_fault(target)
    if fault is None:
        return None
    if fault.kind == "timeout":
        await asyncio.sleep(fault.delay_seconds)
    if target == "bedrock":
        return bedrock.error_response(fault.kind)
    status = {"timeout": 504, "500": 500, "429": 429}[fault.kind]
    headers = {"Retry-After": "1"} if fault.kind == "429" else None
    return JSONResponse({"error": f"MOCK_FAULT_{fault.kind.upper()}"}, status_code=status, headers=headers)


def require_consent(consent_at: str | None) -> None:
    if not consent_at or not consent_at.strip():
        raise HTTPException(status_code=403, detail="third-party consent (X-Consent-At) is required")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


# --- Partner --------------------------------------------------------------------------------------------

partner = APIRouter(prefix="/partner/v1")


class MatchBody(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None


@partner.post("/customers/match")
async def partner_match(body: MatchBody, x_consent_at: str | None = Header(default=None)) -> Any:
    require_consent(x_consent_at)
    if fault := await inject_fault("partner"):
        return fault
    customer = seed.match_partner(body.full_name, body.email, body.phone)
    if customer is None:
        return {"matched": False}
    return {
        "matched": True,
        "partner_customer_ref": customer["partner"]["partner_customer_ref"],
        "date_of_birth": customer["date_of_birth"],
    }


@partner.get("/customers/{ref}/purchases")
async def partner_purchases(ref: str, x_consent_at: str | None = Header(default=None)) -> Any:
    require_consent(x_consent_at)
    if fault := await inject_fault("partner"):
        return fault
    customer = seed.by_partner_ref(ref)
    if customer is None:
        raise HTTPException(status_code=404, detail="unknown partner_customer_ref")
    return {"purchases": customer["partner"]["purchases"]}


# --- Identity -------------------------------------------------------------------------------------------

identity = APIRouter(prefix="/identity/v1")


class OtpBody(BaseModel):
    phone: str


class OtpVerifyBody(BaseModel):
    code: str


REJECTED_OTP_CODE = "000000"  # the one code the identity mock turns down


class DocumentBody(BaseModel):
    document_type: str | None = None
    document_number: str
    full_name: str
    date_of_birth: str | None = None


@identity.post("/otp", status_code=201)
async def otp_send(body: OtpBody) -> Any:
    if fault := await inject_fault("identity"):
        return fault
    otp_id = f"otp_{secrets.token_hex(8)}"
    expires_at = datetime.now(UTC) + timedelta(seconds=otp_ttl_seconds())
    STATE.otps[otp_id] = OtpRequest(phone=body.phone, expires_at=expires_at)
    return {"otp_request_id": otp_id, "expires_at": iso(expires_at)}


@identity.post("/otp/{otp_request_id}/verify")
async def otp_verify(otp_request_id: str, body: OtpVerifyBody) -> Any:
    if fault := await inject_fault("identity"):
        return fault
    request = STATE.otps.get(otp_request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="unknown otp_request_id")
    if datetime.now(UTC) >= request.expires_at:
        return {"verified": False, "reason": "EXPIRED"}
    # No SMS is sent, so every code is accepted, for any phone, except REJECTED_OTP_CODE: entering it is how a
    # demo takes the OTP failure path (seed customers C and D).
    if secrets.compare_digest(body.code.strip(), REJECTED_OTP_CODE):
        return {"verified": False, "reason": "MISMATCH"}
    return {"verified": True}


@identity.post("/documents/verify")
async def document_verify(body: DocumentBody) -> Any:
    if fault := await inject_fault("identity"):
        return fault
    customer = seed.by_document(body.document_number)
    if customer is None or not customer["document_valid"]:
        return {"verified": False, "reason": "NOT_FOUND"}
    name_ok = seed.norm_name(customer["full_name"]) == seed.norm_name(body.full_name)
    dob_ok = not body.date_of_birth or body.date_of_birth[:10] == customer["date_of_birth"]
    if not (name_ok and dob_ok):
        return {"verified": False, "reason": "NAME_MISMATCH"}
    return {"verified": True}


# --- Contract -------------------------------------------------------------------------------------------

contract = APIRouter(prefix="/contract/v1")


@contract.post("/applications")
async def submit_application(
    body: dict[str, Any] = Body(...),
    idempotency_key: str | None = Header(default=None),
) -> Any:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    if fault := await inject_fault("contract"):
        return fault
    if (previous := STATE.submissions.get(idempotency_key)) is not None:
        return JSONResponse(previous, status_code=200)
    STATE.submission_seq += 1
    now = datetime.now(UTC)
    result = {
        "submission_ref": f"SUB-{now.year}-{STATE.submission_seq:06d}",
        "status": "RECEIVED",
        "received_at": iso(now),
    }
    STATE.submissions[idempotency_key] = result
    return JSONResponse(result, status_code=201)


# --- Bedrock Converse -----------------------------------------------------------------------------------


async def _converse_body(request: Request) -> dict[str, Any] | JSONResponse:
    try:
        body = await request.json()
    except ValueError:
        return bedrock.validation_error("Request body is not valid JSON.")
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
        return bedrock.validation_error("messages is required.")
    return body


# `:path` so an ARN-style model id with an encoded '/' still matches; ':' arrives decoded either way.
@app.post("/model/{model_id:path}/converse")
async def converse(model_id: str, request: Request) -> Any:
    started = time.monotonic()
    body = await _converse_body(request)
    if isinstance(body, JSONResponse):
        return body
    if fault := await inject_fault("bedrock"):
        return fault
    return JSONResponse(bedrock.converse_result(body, started))


@app.post("/model/{model_id:path}/converse-stream")
async def converse_stream(model_id: str, request: Request) -> Any:
    started = time.monotonic()
    body = await _converse_body(request)
    if isinstance(body, JSONResponse):
        return body
    if fault := await inject_fault("bedrock"):
        return fault
    result = bedrock.converse_result(body, started)
    return Response(bedrock.stream_events(result), media_type="application/vnd.amazon.eventstream")


# --- Mock controls --------------------------------------------------------------------------------------

controls = APIRouter(prefix="/_mock")


class FaultBody(BaseModel):
    target: Target
    kind: Kind
    count: int = Field(default=1, ge=1, le=100)
    delay_seconds: float | None = Field(default=None, ge=0, le=600)


@controls.post("/faults")
async def arm_faults(body: FaultBody) -> dict[str, Any]:
    STATE.arm(body.target, body.kind, body.count, body.delay_seconds)
    return {"armed": STATE.armed()}


@controls.get("/faults")
async def list_faults() -> dict[str, Any]:
    return {"armed": STATE.armed()}


@controls.post("/reset")
async def reset() -> dict[str, str]:
    STATE.reset()
    return {"status": "reset"}


app.include_router(partner)
app.include_router(identity)
app.include_router(contract)
app.include_router(controls)
