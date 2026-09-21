"""Load nvidia/Nemotron-Personas-Korea parquet shards into `personas.nemotron_ko`.

Shards are downloaded once to $GWT_ROOT/.data/nemotron-personas-korea/; a shard already in the
table is skipped.

    uv run python -m pipeline.ingest_personas --shards 0 1
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

import httpx
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pyiceberg.expressions import EqualTo

from registry.catalog import catalog, data_root
from registry.tables import NEMOTRON_KO, append, ensure

REPO_URL = "https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea/resolve/main/data"
N_SHARDS = 9


def shard_name(i: int) -> str:
    return f"train-{i:05d}-of-{N_SHARDS:05d}.parquet"


def download(name: str):
    path = data_root() / "nemotron-personas-korea" / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        with httpx.stream("GET", f"{REPO_URL}/{name}", follow_redirects=True, timeout=None) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
        tmp.rename(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shards", type=int, nargs="+", default=[0], choices=range(N_SHARDS))
    args = parser.parse_args()

    cat = catalog()
    table = ensure(cat, NEMOTRON_KO)
    for i in args.shards:
        name = shard_name(i)
        if table.scan(row_filter=EqualTo("source_file", name), selected_fields=("uuid",), limit=1).to_arrow().num_rows:
            print(f"{name}: already ingested")
            continue
        data = pq.read_table(download(name))
        data = data.set_column(data.schema.get_field_index("age"), "age", pc.cast(data["age"], pa.int32()))
        n = data.num_rows
        data = data.append_column("source_file", pa.array([name] * n)).append_column(
            "ingested_at", pa.array([datetime.now(UTC)] * n, NEMOTRON_KO.schema.field("ingested_at").type)
        )
        append(cat, NEMOTRON_KO, data)
        table = cat.load_table(NEMOTRON_KO.identifier)
        print(f"{name}: {n} rows")


if __name__ == "__main__":
    main()
