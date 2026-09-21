"""Encrypted Postgres checkpointer in the `checkpoint` schema (state-model.md §6).

Serialisation is compress-then-encrypt: `EncryptedSerializer(AES) ∘ GzipSerde ∘ JsonPlusSerializer`.
`EncryptedSerializer` stores the type as `"{inner_type}+aes"` and splits on the first `+` when
loading, so the gzip layer marks its type with a `gz_` prefix and never adds a `+`."""

from __future__ import annotations

import gzip
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.base import SerializerProtocol
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

GZ_PREFIX = "gz_"


class GzipSerde(SerializerProtocol):
    def __init__(self, serde: SerializerProtocol, level: int = 6) -> None:
        self.serde = serde
        self.level = level

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        typ, data = self.serde.dumps_typed(obj)
        return f"{GZ_PREFIX}{typ}", gzip.compress(data, compresslevel=self.level)

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        typ, payload = data
        if typ.startswith(GZ_PREFIX):
            return self.serde.loads_typed((typ[len(GZ_PREFIX) :], gzip.decompress(payload)))
        return self.serde.loads_typed(data)


def make_serde(aes_key: bytes) -> EncryptedSerializer:
    return EncryptedSerializer.from_pycryptodome_aes(serde=GzipSerde(JsonPlusSerializer()), key=aes_key)


@asynccontextmanager
async def open_checkpointer(conninfo: str, aes_key: bytes) -> AsyncIterator[AsyncPostgresSaver]:
    """Pool-backed saver whose connections use `search_path=checkpoint`. Password-less URLs work:
    libpq falls back to PGPASSWORD, and query params such as sslmode are kept."""
    async with AsyncConnectionPool(
        conninfo=conninfo,
        max_size=10,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": "-c search_path=checkpoint",
        },
    ) as pool:
        saver = AsyncPostgresSaver(pool, serde=make_serde(aes_key))
        await saver.setup()
        yield saver
