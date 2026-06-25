"""GARUDA adapter — loader / orchestrator (Phase 2, Step 4).

    read source -> map to canonical (column_map) -> validate (gate) -> write to Data Store

The format-specific logic is in mapping.py; the gate is validate.py. Downstream reads
only canonical tables. Swap datasets by swapping the --map file.

Examples:
    # verify locally without Catalyst creds (maps + validates, writes a canonical CSV):
    python ingestion/adapter/loader.py --source data/synthetic/incidents.csv \
        --map ingestion/adapter/column_map.synthetic.yaml --table Incidents --dry-run

    # live bulk-load to Data Store (run where Catalyst creds exist; batches of ~200):
    python ingestion/adapter/loader.py --source data/synthetic/incidents.csv \
        --map ingestion/adapter/column_map.synthetic.yaml --table Incidents

Note: the live write uses zcatalyst-sdk-python, which initialises from the ambient
Catalyst context (run inside a Catalyst Job/AppSail, or with the CLI's credentials).
If it isn't available, use the emitted canonical CSV with Console -> Data Store -> Import.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from mapping import load_column_map, map_to_canonical, read_source
import validate as V


def to_records(df):
    """Canonical DataFrame -> list[dict] with None for empty cells (Data Store nulls)."""
    records = []
    for row in df.to_dict(orient="records"):
        records.append({k: (None if (v == "" or pd.isna(v)) else v) for k, v in row.items()})
    return records


def sdk_write(table, records, batch_size):
    """Bulk-insert into Catalyst Data Store. Lazy-imports the SDK on purpose."""
    import zcatalyst_sdk  # noqa: WPS433 (lazy: only needed for a live load)

    app = zcatalyst_sdk.initialize()
    datastore = app.datastore()
    tbl = datastore.table(table)
    written = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        tbl.insert_rows(batch)          # confirm method name against zcatalyst-sdk-python
        written += len(batch)
        print(f"  wrote {written}/{len(records)} into {table}")
    return written


def main():
    ap = argparse.ArgumentParser(description="GARUDA canonical loader")
    ap.add_argument("--source", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="map + validate + emit canonical CSV; do not write to Data Store")
    ap.add_argument("--emit-csv", action="store_true",
                    help="also write the mapped canonical CSV (console-Import ready)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N rows (dev quotas)")
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--force", action="store_true", help="load even if validation has errors")
    args = ap.parse_args()

    table_map = load_column_map(args.map, args.table)
    raw = read_source(args.source)
    if args.limit:
        raw = raw.head(args.limit)
    canonical, missing = map_to_canonical(raw, table_map)
    if missing:
        print(f"NOTE: source missing {len(missing)} column(s), filled empty: {missing}")

    report = V.validate(canonical, args.table)
    print(V.format_report(report))
    if not report["ok"] and not args.force:
        print("\nABORT: validation failed. Fix the source/column-map, or pass --force.")
        sys.exit(1)

    out_path = None
    if args.dry_run or args.emit_csv:
        out_dir = Path(args.source).resolve().parent / "_canonical"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{args.table}.csv"
        canonical.to_csv(out_path, index=False, encoding="utf-8")
        print(f"canonical CSV -> {out_path}")

    if args.dry_run:
        print(f"\nDRY-RUN OK: {len(canonical)} rows mapped + validated for {args.table} "
              f"(nothing written to Data Store).")
        return

    try:
        n = sdk_write(args.table, to_records(canonical), args.batch_size)
        print(f"\nLOADED {n} rows into {args.table}.")
    except ImportError:
        print("\nzcatalyst-sdk-python not available in this environment. Either:\n"
              "  - run this inside a Catalyst Job/AppSail (creds present), or\n"
              "  - import the emitted canonical CSV via Console -> Data Store -> Import.\n"
              f"    canonical CSV: {out_path or 'rerun with --emit-csv'}")
        sys.exit(2)


if __name__ == "__main__":
    main()
