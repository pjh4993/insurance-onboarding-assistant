"""Draw a named, stratified persona sample from `personas.nemotron_ko` into `personas.samples`.

Strata are age band x employed (occupation != 무직), so a small sample still spans young and old,
working and not. Rows are ordered by stratum; generate_traces assigns situations by that order.

    uv run python -m pipeline.sample_personas --sample-id strat10-s42 --n 10 --seed 42
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

import pandas as pd
from pyiceberg.expressions import EqualTo

from registry.catalog import catalog
from registry.tables import NEMOTRON_KO, SAMPLES, append, ensure

AGE_BANDS = [18, 29, 39, 49, 64, 120]
AGE_LABELS = ["20s", "30s", "40s", "50-64", "65+"]


def stratified(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    df = df.assign(
        stratum=pd.cut(df["age"], AGE_BANDS, labels=AGE_LABELS).astype(str)
        + "/"
        + (df["occupation"] != "무직").map({True: "employed", False: "unemployed"})
    )
    groups = sorted(df.groupby("stratum"), key=lambda g: (AGE_LABELS.index(g[0].split("/")[0]), g[0]))
    per, extra = divmod(n, len(groups))
    picks = [g.sample(n=min(len(g), per + (i < extra)), random_state=seed) for i, (_, g) in enumerate(groups)]
    return pd.concat(picks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    cat = catalog()
    samples = ensure(cat, SAMPLES)
    if samples.scan(row_filter=EqualTo("sample_id", args.sample_id), limit=1).to_arrow().num_rows:
        raise SystemExit(f"sample {args.sample_id} already exists")
    df = ensure(cat, NEMOTRON_KO).scan(selected_fields=("uuid", "age", "occupation")).to_pandas()
    picked = stratified(df, args.n, args.seed)
    now = datetime.now(UTC)
    rows = [
        {
            "sample_id": args.sample_id,
            "persona_uuid": r.uuid,
            "position": i,
            "stratum": r.stratum,
            "strategy": "age_band x employed",
            "seed": args.seed,
            "created_at": now,
        }
        for i, r in enumerate(picked.itertuples())
    ]
    append(cat, SAMPLES, rows)
    print(picked[["uuid", "age", "occupation", "stratum"]].to_string(index=False))


if __name__ == "__main__":
    main()
