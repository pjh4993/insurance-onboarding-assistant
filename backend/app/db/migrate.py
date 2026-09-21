"""Schema migrations (Alembic), run by init_db on every start under its advisory lock."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, inspect

from app.db.models import SCHEMAS

BASELINE = "0001"
MIGRATIONS = Path(__file__).parent / "migrations"


def include_name(name: str | None, type_: str, parent_names: dict[str, Any]) -> bool:
    return name in SCHEMAS if type_ == "schema" else True


def include_object(obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any) -> bool:
    # Tables Alembic does not own (LangGraph's checkpoint tables) are never dropped or reported as drift.
    return not (type_ == "table" and reflected and compare_to is None)


def alembic_config(connection: Connection | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.attributes["connection"] = connection
    return cfg


def upgrade(connection: Connection) -> None:
    """Bring the schema to head. A database that create_all built before migrations existed has the baseline
    tables but no alembic_version, so it is stamped at the baseline first instead of running it."""
    cfg = alembic_config(connection)
    insp = inspect(connection)
    if not insp.has_table("alembic_version") and insp.has_table("onboarding_session", schema="domain"):
        command.stamp(cfg, BASELINE)
    command.upgrade(cfg, "head")
