"""HMAC fingerprints and field encryption for PII at rest (the ID document number)."""

from __future__ import annotations

import hashlib
import hmac

from Crypto.Cipher import AES


def hmac_hex(key: str, value: str) -> str:
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


def encrypt_field(key: bytes, plaintext: str) -> bytes:
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())
    return cipher.nonce + tag + ciphertext


def decrypt_field(key: bytes, blob: bytes) -> str:
    cipher = AES.new(key, AES.MODE_EAX, nonce=blob[:16])
    return cipher.decrypt_and_verify(blob[32:], blob[16:32]).decode()
