"""Small shared helpers: clock, deterministic ids, HMAC and field encryption."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime

from Crypto.Cipher import AES

# Namespace for node-scoped ids: uuid5(NS, f"{thread_id}:{node}:{step}:{extra}")
NODE_ID_NAMESPACE = uuid.UUID("6d1f7c43-6a5e-4c55-9d7c-0c3b1c1e0b7a")
CATALOG_NAMESPACE = uuid.UUID("0b8e2a55-2f0b-4b7e-8a3c-7f3c6b9d8e11")

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC)


def node_uuid(thread_id: str, node: str, step: int | str, extra: str = "") -> uuid.UUID:
    """Id for an entity a node creates. Re-running the same node at the same step yields the
    same id, so the write becomes an upsert (state-model.md §5)."""
    return uuid.uuid5(NODE_ID_NAMESPACE, f"{thread_id}:{node}:{step}:{extra}")


def catalog_uuid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(CATALOG_NAMESPACE, ":".join(parts))


def hmac_hex(key: str, value: str) -> str:
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


def encrypt_field(key: bytes, plaintext: str) -> bytes:
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())
    return cipher.nonce + tag + ciphertext


def decrypt_field(key: bytes, blob: bytes) -> str:
    cipher = AES.new(key, AES.MODE_EAX, nonce=blob[:16])
    return cipher.decrypt_and_verify(blob[32:], blob[16:32]).decode()


def parse_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return dt.isoformat()


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return "*" * max(len(phone) - 4, 0) + phone[-4:]
