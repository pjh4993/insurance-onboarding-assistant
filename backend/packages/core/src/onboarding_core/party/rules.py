"""Party facts the eligibility rules read (subject PARTY)."""

from __future__ import annotations

from typing import Any

from onboarding_core.party.models import Party
from onboarding_core.util import iso


def party_view(p: Party) -> dict[str, Any]:
    return {"party_type": p.party_type, "date_of_birth": iso(p.date_of_birth)}
