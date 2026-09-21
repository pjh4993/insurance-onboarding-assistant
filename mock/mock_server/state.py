"""In-memory mock state: armed faults, OTP requests, contract submissions. Cleared by /_mock/reset."""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Target = Literal["partner", "identity", "contract", "bedrock"]
Kind = Literal["timeout", "500", "429"]
TARGETS: tuple[Target, ...] = ("partner", "identity", "contract", "bedrock")


def default_timeout_seconds() -> float:
    # Longer than botocore's 60 s default read timeout, so a "timeout" fault really times the client out.
    return float(os.environ.get("MOCK_TIMEOUT_SECONDS", "65"))


def otp_ttl_seconds() -> float:
    return float(os.environ.get("MOCK_OTP_TTL_SECONDS", "300"))


@dataclass
class Fault:
    kind: Kind
    delay_seconds: float


@dataclass
class OtpRequest:
    phone: str
    expires_at: datetime


@dataclass
class MockState:
    faults: dict[str, deque[Fault]] = field(default_factory=lambda: {t: deque() for t in TARGETS})
    otps: dict[str, OtpRequest] = field(default_factory=dict)
    submissions: dict[str, dict[str, Any]] = field(default_factory=dict)
    submission_seq: int = 0

    def arm(self, target: Target, kind: Kind, count: int, delay_seconds: float | None) -> None:
        delay = default_timeout_seconds() if delay_seconds is None else delay_seconds
        self.faults[target].extend(Fault(kind, delay) for _ in range(count))

    def take_fault(self, target: Target) -> Fault | None:
        queue = self.faults[target]
        return queue.popleft() if queue else None

    def armed(self) -> dict[str, list[dict[str, Any]]]:
        return {
            t: [{"kind": f.kind, "delay_seconds": f.delay_seconds} for f in q] for t, q in self.faults.items()
        }

    def reset(self) -> None:
        for q in self.faults.values():
            q.clear()
        self.otps.clear()
        self.submissions.clear()
        self.submission_seq = 0


STATE = MockState()
