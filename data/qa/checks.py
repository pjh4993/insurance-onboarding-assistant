"""Deterministic checks over one trace. Each returns (status, detail): PASS, FAIL, or SKIP when it does not
apply to the scenario. The brief is the ground truth: what the customer knows is what the agent should
have captured."""

from __future__ import annotations

from collections.abc import Callable
from itertools import groupby
from typing import Any

from onboarding_core.product_lines.device import normalize_device_category, normalize_manufacturer

Result = tuple[str, str]
PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

VERIFICATION = {"PARTNER": "PARTNER_MATCH", "OTP": "OTP", "DOCUMENT": "DOCUMENT"}
DEVICE_OBJECTIVES = {"PROTECT_DEVICE", "EXTEND_WARRANTY"}
MAX_SAME_PROMPT = 3  # the same input asked for more than this many times in a row is a loop


def _entities(t: dict[str, Any]) -> dict[str, Any]:
    return t.get("entities") or {}


def outcome(t: dict[str, Any]) -> Result:
    want, got = t["expect"]["status"], (t.get("final") or {}).get("status")
    reason = (t.get("final") or {}).get("handoff_reason")
    detail = f"expected {want}, got {got}" + (f" ({reason})" if reason else "")
    return (PASS if got == want else FAIL), detail


def product(t: dict[str, Any]) -> Result:
    want = t["expect"].get("product")
    if not want:
        return SKIP, "no product expected"
    app = _entities(t).get("application") or {}
    got = app.get("product_code") if app.get("status") == "SUBMITTED" else None
    return (PASS if got == want else FAIL), f"expected {want}, submitted {got}"


def identity_path(t: dict[str, Any]) -> Result:
    """The harness itself: the customer verified the way the scenario means to."""
    path = t["situation"]["identity"]
    party = _entities(t).get("party") or {}
    if path == "HANDOFF":
        ok = party.get("verification_status") != "VERIFIED"
        return (PASS if ok else FAIL), f"status {party.get('verification_status')}"
    got = party.get("verification_method")
    return (PASS if got == VERIFICATION[path] else FAIL), f"expected {VERIFICATION[path]}, got {got}"


def _needs(t: dict[str, Any]) -> dict[str, Any] | None:
    return _entities(t).get("needs_assessment")


def needs_device(t: dict[str, Any]) -> Result:
    brief_dev, na = t["brief"].get("device"), _needs(t)
    if not brief_dev or not na or not na.get("device") or t["situation"]["identity"] == "PARTNER":
        return SKIP, "no customer-described device"
    dev, bad = na["device"], []
    if normalize_device_category(dev.get("device_category")) not in (brief_dev["category"], None):
        bad.append(f"category {dev.get('device_category')} != {brief_dev['category']}")
    if dev.get("manufacturer") and normalize_manufacturer(dev["manufacturer"]) != normalize_manufacturer(
        brief_dev["manufacturer"]
    ):
        bad.append(f"manufacturer {dev['manufacturer']} != {brief_dev['manufacturer']}")
    price = dev.get("purchase_price_minor")
    if price is not None and t["situation"]["decision"] != "CHANGE" and price != brief_dev["price_krw"]:
        bad.append(f"price {price} != {brief_dev['price_krw']}")
    return (FAIL, "; ".join(bad)) if bad else (PASS, f"{dev}")


def needs_trip(t: dict[str, Any]) -> Result:
    brief_trip, na = t["brief"].get("trip"), _needs(t)
    if not brief_trip or not na or not na.get("trip"):
        return SKIP, "no trip captured"
    trip, bad = na["trip"], []
    if brief_trip["destination_country"] not in (trip.get("destination_countries") or []):
        bad.append(f"destinations {trip.get('destination_countries')} lack {brief_trip['destination_country']}")
    if t["situation"]["decision"] != "CHANGE":
        for key in ("departure_date", "return_date"):
            if trip.get(key) and trip[key] != brief_trip[key]:
                bad.append(f"{key} {trip[key]} != {brief_trip[key]}")
    return (FAIL, "; ".join(bad)) if bad else (PASS, f"{trip}")


def objectives(t: dict[str, Any]) -> Result:
    """No cover the customer does not have a subject for (e.g. device cover on a trip-only customer)."""
    na = _needs(t)
    if not na:
        return SKIP, "no needs assessment"
    got, b = set(na.get("objectives") or []), t["brief"]
    bad = []
    if got & DEVICE_OBJECTIVES and not b.get("device"):
        bad.append(f"{sorted(got & DEVICE_OBJECTIVES)} without a device")
    if "TRAVEL_COVER" in got and not b.get("trip"):
        bad.append("TRAVEL_COVER without a trip")
    return (FAIL, "; ".join(bad)) if bad else (PASS, f"{sorted(got)}")


def parties(t: dict[str, Any]) -> Result:
    """Who is insured and who pays, by name and date of birth, as the brief says."""
    rows = _entities(t).get("application_parties") or []
    if not rows:
        return SKIP, "no application parties"
    b = t["brief"]
    me = {"full_name": b["full_name"], "date_of_birth": b["date_of_birth"]}
    others = {p["role"]: p for p in b.get("other_people") or []}
    got = {r["role"]: r for r in rows}
    bad = []
    for role in ("INSURED", "PAYER"):
        if role not in got:
            continue
        want = others.get(role, me)
        have = got[role]
        if have["full_name"] != want["full_name"] or (
            have.get("date_of_birth") and have["date_of_birth"] != want["date_of_birth"]
        ):
            bad.append(
                f"{role} {have['full_name']} {have.get('date_of_birth')} != {want['full_name']} {want['date_of_birth']}"
            )
    summary = {r: (v["full_name"], v.get("date_of_birth")) for r, v in got.items()}
    return (FAIL, "; ".join(bad)) if bad else (PASS, f"{summary}")


def no_loop(t: dict[str, Any]) -> Result:
    runs = [(k, len(list(g))) for k, g in groupby(u["waiting_for"] for u in t.get("turns") or [])]
    worst = max(runs, key=lambda r: r[1], default=("-", 0))
    return (FAIL if worst[1] > MAX_SAME_PROMPT else PASS), f"longest run {worst[0]} x{worst[1]}"


def finished(t: dict[str, Any]) -> Result:
    status = (t.get("final") or {}).get("status")
    return (FAIL, "conversation still ACTIVE at the step limit") if status == "ACTIVE" else (PASS, str(status))


def turn_budget(t: dict[str, Any]) -> Result:
    n, limit = len(t.get("turns") or []), t["expect"]["max_turns"]
    return (PASS if n <= limit else FAIL), f"{n} turns (budget {limit})"


def no_error(t: dict[str, Any]) -> Result:
    if t.get("error"):
        return FAIL, t["error"].strip().splitlines()[-1]
    if (t.get("final") or {}).get("handoff_reason") == "ERROR":
        errors = [m["text"] for m in t.get("messages") or [] if m["role"] == "system" and "failed" in m["text"]]
        return FAIL, errors[-1] if errors else "handoff for an error"
    return PASS, ""


CHECKS: dict[str, Callable[[dict[str, Any]], Result]] = {
    "outcome": outcome,
    "product": product,
    "identity_path": identity_path,
    "needs_device": needs_device,
    "needs_trip": needs_trip,
    "objectives": objectives,
    "parties": parties,
    "no_loop": no_loop,
    "finished": finished,
    "turn_budget": turn_budget,
    "no_error": no_error,
}


def run_checks(t: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    for name, check in CHECKS.items():
        try:
            status, detail = check(t)
        except Exception as exc:  # a check that cannot read the trace is itself a failure
            status, detail = FAIL, f"check error: {exc!r}"
        out.append({"check": name, "status": status, "detail": detail})
    return out
