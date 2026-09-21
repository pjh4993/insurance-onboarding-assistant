import json
import re
from pathlib import Path

import pytest

from mock_server.seed import DEFAULT_SEED_PATH

CONSENT = {"X-Consent-At": "2026-09-21T01:00:00Z"}
A = {"full_name": "김하늘", "email": "haneul.kim@example.com", "phone": "+821011112222"}


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_seed_copy_matches_contract():
    contract_copy = Path(__file__).resolve().parents[2] / "contracts" / "seed-customers.json"
    if not contract_copy.exists():
        pytest.skip("contracts/ not present (e.g. inside the Docker build context)")
    assert json.loads(DEFAULT_SEED_PATH.read_text()) == json.loads(contract_copy.read_text())


# --- partner ---


def test_partner_requires_consent(client):
    assert client.post("/partner/v1/customers/match", json=A).status_code == 403
    assert client.get("/partner/v1/customers/P-000101/purchases").status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        A,
        {**A, "phone": None},
        {**A, "email": None},
        {**A, "email": "other@example.com"},
        {**A, "phone": "010-1111-2222", "email": None},
    ],
)
def test_partner_match_a(client, body):
    r = client.post("/partner/v1/customers/match", json=body, headers=CONSENT)
    assert r.status_code == 200
    assert r.json() == {"matched": True, "partner_customer_ref": "P-000101", "date_of_birth": "1991-03-14"}


@pytest.mark.parametrize(
    "body",
    [
        {**A, "email": "x@example.com", "phone": "+820000000000"},
        {**A, "full_name": "김하나"},
        {"full_name": "이서준", "email": "seojun.lee@example.com", "phone": "+821033334444"},
        {"full_name": "Nobody", "email": "n@example.com", "phone": "+10000000000"},
    ],
)
def test_partner_no_match(client, body):
    r = client.post("/partner/v1/customers/match", json=body, headers=CONSENT)
    assert r.json() == {"matched": False}


def test_partner_purchases(client):
    r = client.get("/partner/v1/customers/P-000101/purchases", headers=CONSENT)
    assert r.status_code == 200
    (purchase,) = r.json()["purchases"]
    assert purchase["order_id"] == "O-778812"
    assert purchase["item"]["model"] == "Galaxy S26"
    assert purchase["item"]["price_minor"] == 1350000
    assert client.get("/partner/v1/customers/P-999/purchases", headers=CONSENT).status_code == 404


# --- identity ---


def _otp(client, phone):
    r = client.post("/identity/v1/otp", json={"phone": phone})
    assert r.status_code == 201
    body = r.json()
    assert body["otp_request_id"] and body["expires_at"].endswith("Z")
    return body["otp_request_id"]


def test_otp_b_succeeds_with_000000(client):
    otp_id = _otp(client, "+821033334444")
    assert client.post(f"/identity/v1/otp/{otp_id}/verify", json={"code": "123456"}).json() == {
        "verified": False,
        "reason": "MISMATCH",
    }
    assert client.post(f"/identity/v1/otp/{otp_id}/verify", json={"code": "000000"}).json() == {
        "verified": True
    }


@pytest.mark.parametrize("phone", ["+12065550101", "+12065550102", "+821099999999"])
def test_otp_c_d_unknown_always_fail(client, phone):
    otp_id = _otp(client, phone)
    for code in ("000000", "123456"):
        r = client.post(f"/identity/v1/otp/{otp_id}/verify", json={"code": code})
        assert r.json() == {"verified": False, "reason": "MISMATCH"}


def test_otp_expired(client, monkeypatch):
    monkeypatch.setenv("MOCK_OTP_TTL_SECONDS", "0")
    otp_id = _otp(client, "+821033334444")
    r = client.post(f"/identity/v1/otp/{otp_id}/verify", json={"code": "000000"})
    assert r.json() == {"verified": False, "reason": "EXPIRED"}


def test_otp_unknown_request(client):
    assert client.post("/identity/v1/otp/otp_nope/verify", json={"code": "000000"}).status_code == 404


@pytest.mark.parametrize(
    ("doc", "expected"),
    [
        (("NATIONAL_ID", "910314-2000001", "김하늘", "1991-03-14"), {"verified": True}),
        (("NATIONAL_ID", "8511021000002", "이서준", "1985-11-02"), {"verified": True}),
        (("PASSPORT", "M12345678", "jane  doe", "1990-06-01"), {"verified": True}),
        (("PASSPORT", "M12345678", "Jane Doe", None), {"verified": True}),
        (
            ("PASSPORT", "M12345678", "Janet Doe", "1990-06-01"),
            {"verified": False, "reason": "NAME_MISMATCH"},
        ),
        (("PASSPORT", "M12345678", "Jane Doe", "1991-06-01"), {"verified": False, "reason": "NAME_MISMATCH"}),
        (
            ("DRIVER_LICENSE", "WDL0000000", "John Roe", "1978-01-20"),
            {"verified": False, "reason": "NOT_FOUND"},
        ),
        (("PASSPORT", "X0000000", "Someone", "2000-01-01"), {"verified": False, "reason": "NOT_FOUND"}),
    ],
)
def test_document_verify(client, doc, expected):
    document_type, number, name, dob = doc
    body = {
        "document_type": document_type,
        "document_number": number,
        "full_name": name,
        "date_of_birth": dob,
    }
    r = client.post("/identity/v1/documents/verify", json=body)
    assert r.status_code == 200
    assert r.json() == expected


# --- contract ---

APPLICATION = {"application_id": "app-1", "product_code": "DEVICE_PROTECTION_STD", "answers": {}}


def test_contract_requires_idempotency_key(client):
    assert client.post("/contract/v1/applications", json=APPLICATION).status_code == 400


def test_contract_idempotent(client):
    first = client.post("/contract/v1/applications", json=APPLICATION, headers={"Idempotency-Key": "k1"})
    assert first.status_code == 201
    body = first.json()
    assert re.fullmatch(r"SUB-\d{4}-\d{6}", body["submission_ref"])
    assert body["status"] == "RECEIVED" and body["received_at"].endswith("Z")

    again = client.post("/contract/v1/applications", json=APPLICATION, headers={"Idempotency-Key": "k1"})
    assert again.status_code == 200 and again.json() == body

    other = client.post("/contract/v1/applications", json=APPLICATION, headers={"Idempotency-Key": "k2"})
    assert other.status_code == 201 and other.json()["submission_ref"] != body["submission_ref"]


# --- faults ---


@pytest.mark.parametrize(
    ("target", "method", "path", "kwargs"),
    [
        ("partner", "post", "/partner/v1/customers/match", {"json": A, "headers": CONSENT}),
        ("identity", "post", "/identity/v1/otp", {"json": {"phone": "+821033334444"}}),
        (
            "contract",
            "post",
            "/contract/v1/applications",
            {"json": APPLICATION, "headers": {"Idempotency-Key": "f"}},
        ),
    ],
)
@pytest.mark.parametrize(("kind", "status"), [("500", 500), ("429", 429), ("timeout", 504)])
def test_faults_http_targets(client, target, method, path, kwargs, kind, status):
    r = client.post("/_mock/faults", json={"target": target, "kind": kind, "count": 2, "delay_seconds": 0.01})
    assert r.status_code == 200
    assert len(r.json()["armed"][target]) == 2
    call = getattr(client, method)
    assert call(path, **kwargs).status_code == status
    assert call(path, **kwargs).status_code == status
    assert call(path, **kwargs).status_code in (200, 201)


def test_fault_does_not_leak_to_other_targets(client):
    client.post("/_mock/faults", json={"target": "contract", "kind": "500", "count": 1})
    assert client.post("/partner/v1/customers/match", json=A, headers=CONSENT).status_code == 200


def test_timeout_fault_waits(client):
    import time

    client.post("/_mock/faults", json={"target": "identity", "kind": "timeout", "delay_seconds": 0.3})
    started = time.monotonic()
    assert client.post("/identity/v1/otp", json={"phone": "+1"}).status_code == 504
    assert time.monotonic() - started >= 0.3


def test_contract_fault_does_not_record_submission(client):
    client.post("/_mock/faults", json={"target": "contract", "kind": "500"})
    headers = {"Idempotency-Key": "k"}
    assert client.post("/contract/v1/applications", json=APPLICATION, headers=headers).status_code == 500
    assert client.post("/contract/v1/applications", json=APPLICATION, headers=headers).status_code == 201


def test_fault_validation(client):
    assert client.post("/_mock/faults", json={"target": "nope", "kind": "500"}).status_code == 422
    assert client.post("/_mock/faults", json={"target": "partner", "kind": "404"}).status_code == 422
    assert (
        client.post("/_mock/faults", json={"target": "partner", "kind": "500", "count": 0}).status_code == 422
    )


def test_reset_clears_everything(client):
    client.post("/_mock/faults", json={"target": "partner", "kind": "500", "count": 3})
    client.post("/contract/v1/applications", json=APPLICATION, headers={"Idempotency-Key": "k"})
    assert client.post("/_mock/reset").json() == {"status": "reset"}
    assert client.get("/_mock/faults").json()["armed"]["partner"] == []
    r = client.post("/contract/v1/applications", json=APPLICATION, headers={"Idempotency-Key": "k"})
    assert r.status_code == 201 and r.json()["submission_ref"].endswith("-000001")
