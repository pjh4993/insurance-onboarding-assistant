"""Alembic environment. init_db passes its open connection; the `alembic` CLI (run from backend/) connects
with DATABASE_URL, e.g. `uv run alembic revision --autogenerate -m "..."`."""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection, create_engine

from app.db.migrate import include_name, include_object
from app.db.models import metadata

config = context.config


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=metadata,
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline (--sql) migrations are not supported")

connection = config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    from app.config import Settings

    with create_engine(Settings().database_url).connect() as conn:
        run(conn)
        conn.commit()
