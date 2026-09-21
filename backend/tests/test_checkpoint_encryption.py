"""The checkpoint is compressed then encrypted: raw rows never show customer PII in plaintext."""

from __future__ import annotations

import psycopg
from langchain_core.messages import HumanMessage

from onboarding_agent.checkpointer import GzipSerde, make_serde
from tests.fakes import CUSTOMERS, identity_input
from tests.test_scenarios import send, start

KEY = bytes.fromhex("00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff")


def test_serde_roundtrip_and_type_marking():
    serde = make_serde(KEY)
    obj = {"messages": [HumanMessage(content="+821011112222", id="m1")], "n": 1}
    typ, data = serde.dumps_typed(obj)
    # EncryptedSerializer splits on the first "+": the gzip layer must not add one of its own.
    assert typ.count("+") == 1 and typ.endswith("+aes") and typ.startswith("gz_")
    assert b"821011112222" not in data
    assert serde.loads_typed((typ, data)) == obj


def test_gzip_serde_reads_uncompressed_payloads():
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    inner = JsonPlusSerializer()
    assert GzipSerde(inner).loads_typed(inner.dumps_typed({"a": 1})) == {"a": 1}


async def test_raw_checkpoint_rows_hide_seeded_phone(runtime, settings):
    rt = runtime
    c = CUSTOMERS["B"]
    sid = await start(rt, "KR")
    await send(rt, sid, "IDENTITY_INFO", identity_input("B", consent=True))
    await send(rt, sid, "OTP_CODE", {"code": c["otp"]["valid_code"]})
    await send(rt, sid, "NEEDS", {"text": c["needs_text"]})

    secrets = [c["phone"], c["phone"][1:], c["id_document_number"], c["email"], c["full_name"], "일본 여행", '"000000"']
    with psycopg.connect(settings.psycopg_conninfo) as conn:
        rows = []
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            rows += conn.execute(
                f"SELECT row_to_json(t)::text FROM checkpoint.{table} t WHERE thread_id = %s", (sid,)
            ).fetchall()
            if table != "checkpoints":
                raw = conn.execute(
                    f"SELECT blob, type FROM checkpoint.{table} WHERE thread_id = %s AND blob IS NOT NULL",
                    (sid,),
                ).fetchall()
                for blob, typ in raw:
                    assert typ in ("empty",) or typ.endswith("+aes"), typ
                    for secret in secrets:
                        assert secret.encode() not in bytes(blob)
    assert rows, "expected checkpoint rows for the thread"
    dump = "\n".join(r[0] for r in rows)
    for secret in secrets:
        assert secret not in dump, f"{secret!r} visible in raw checkpoint rows"

    # ...yet the graph reads its own state back
    values = (await rt.agent.graph.aget_state(rt.agent.config(sid))).values
    assert any(c["needs_text"] in str(m.content) for m in values["messages"])
