"""`python -m registry`: create any missing table and list every table with its row count."""

from __future__ import annotations

from registry.catalog import WAREHOUSE, catalog
from registry.tables import TABLES, ensure


def main() -> None:
    cat = catalog()
    print(f"warehouse {WAREHOUSE}")
    for t in TABLES:
        table = ensure(cat, t)
        snap = table.current_snapshot()
        rows = snap.summary["total-records"] if snap and snap.summary else "0"
        print(f"  {t.identifier:24} {rows:>9} rows  {table.location()}")


if __name__ == "__main__":
    main()
