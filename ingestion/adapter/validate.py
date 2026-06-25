"""GARUDA adapter — the validation gate.

Runs on a *canonical* DataFrame (post column-map) against schema/canonical_schema.yaml:
schema check, required-not-null, unique, duplicate FIRs, bad dates/coords, IPC<->BNS
code coverage, and a Unicode/mojibake check. Fails loudly with a triage report so
problems surface on a sample before a full load (especially the day real data arrives).

As a module:   report = validate(canonical_df, "Incidents"); validate.is_ok(report)
As a CLI:      python validate.py --source file.csv --table Incidents [--map column_map.yaml]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

ADAPTER_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADAPTER_DIR.parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "canonical_schema.yaml"
IPC_BNS_PATH = REPO_ROOT / "data" / "reference" / "ipc_bns_map.csv"

# (lat_min, lat_max, long_min, long_max) — generous Karnataka bounding box.
KARNATAKA_BBOX = (11.0, 19.5, 73.5, 79.0)


def load_schema(path=SCHEMA_PATH):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["tables"]


def known_codes(path=IPC_BNS_PATH):
    if not Path(path).exists():
        return None
    df = pd.read_csv(path, dtype=str)
    return set(df["ipc_code"].dropna()) | set(df["bns_code"].dropna())


def _empty(series):
    return series.astype(str).str.strip() == ""


def validate(df, table, schema=None, ipc_bns_path=IPC_BNS_PATH):
    schema = schema or load_schema()
    if table not in schema:
        return {"table": table, "ok": False, "errors": [f"unknown table '{table}'"],
                "warnings": [], "info": [], "stats": {"rows": len(df)}}
    cols = {c["name"]: c for c in schema[table]["columns"]}
    errors, warnings, info = [], [], []
    stats = {"rows": int(len(df))}

    # 1. schema: required columns present
    for name, c in cols.items():
        if not c.get("nullable", True) and name not in df.columns:
            errors.append(f"missing required column '{name}'")
    extra = [c for c in df.columns if c not in cols]
    if extra:
        info.append(f"non-canonical columns present (ignored on load): {extra}")

    # 2. required-not-null + uniqueness
    for name, c in cols.items():
        if name not in df.columns:
            continue
        s = df[name]
        if not c.get("nullable", True):
            n_null = int(_empty(s).sum())
            if n_null:
                errors.append(f"{name}: {n_null} null/empty value(s) in NOT NULL column")
        if c.get("unique"):
            nonempty = s[~_empty(s)]
            dups = int(nonempty.duplicated().sum())
            if dups:
                errors.append(f"{name}: {dups} duplicate value(s) in UNIQUE column")

    # 3. table-specific checks
    if table == "Incidents":
        if "fir_no" in df:
            d = int(df.loc[~_empty(df["fir_no"]), "fir_no"].duplicated().sum())
            if d:
                warnings.append(f"fir_no: {d} duplicate FIR number(s)")
        for col in ("occurred_at", "reported_at"):
            if col in df:
                dt = pd.to_datetime(df[col], errors="coerce")
                bad = int((dt.isna() & ~_empty(df[col])).sum())
                if bad:
                    warnings.append(f"{col}: {bad} unparseable datetime(s)")
                future = int((dt > pd.Timestamp.now()).sum())
                if future:
                    warnings.append(f"{col}: {future} future-dated value(s)")
        if {"occurred_at", "reported_at"} <= set(df.columns):
            o = pd.to_datetime(df["occurred_at"], errors="coerce")
            r = pd.to_datetime(df["reported_at"], errors="coerce")
            rev = int((r < o).sum())
            if rev:
                warnings.append(f"reported_at earlier than occurred_at in {rev} row(s)")
        for col, lo, hi in (("lat", KARNATAKA_BBOX[0], KARNATAKA_BBOX[1]),
                            ("long", KARNATAKA_BBOX[2], KARNATAKA_BBOX[3])):
            if col in df:
                v = pd.to_numeric(df[col], errors="coerce")
                oob = int((v.notna() & ((v < lo) | (v > hi))).sum())
                if oob:
                    warnings.append(f"{col}: {oob} value(s) outside Karnataka bbox [{lo},{hi}]")
        codes = known_codes(ipc_bns_path)
        if codes is not None and "ipc_bns_code" in df:
            present = df.loc[~_empty(df["ipc_bns_code"]), "ipc_bns_code"]
            uncovered = int((~present.isin(codes)).sum())
            cov = 1 - uncovered / max(len(present), 1)
            stats["code_coverage"] = round(cov, 3)
            if uncovered:
                warnings.append(f"ipc_bns_code: {uncovered} code(s) not in IPC<->BNS map "
                                f"({cov:.1%} covered)")

    # 4. encoding / Unicode
    repl, nonascii = 0, 0
    for c in df.columns:
        s = df[c].astype(str)
        repl += int(s.str.contains("�", regex=False).sum())
        nonascii += int(s.str.contains(r"[^\x00-\x7F]", regex=True).sum())
    if repl:
        errors.append(f"encoding: {repl} cell(s) contain U+FFFD replacement char (mojibake)")
    if nonascii:
        info.append(f"{nonascii} cell(s) contain non-ASCII text (e.g. Kannada) — fine if UTF-8")

    stats["errors"], stats["warnings"] = len(errors), len(warnings)
    return {"table": table, "ok": len(errors) == 0,
            "errors": errors, "warnings": warnings, "info": info, "stats": stats}


def is_ok(report):
    return report["ok"]


def format_report(rep):
    head = f"[{rep['table']}] rows={rep['stats']['rows']}  " + ("OK" if rep["ok"] else "FAILED")
    lines = [head, "-" * len(head)]
    for label, key in (("errors", "errors"), ("warnings", "warnings"), ("info", "info")):
        items = rep[key]
        if items:
            lines.append(f"{label}:")
            lines += [f"  - {x}" for x in items]
        else:
            lines.append(f"{label}: none")
    lines.append(f"stats: {rep['stats']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="GARUDA validation gate")
    ap.add_argument("--source", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--map", default=None, help="column map; if given, source is mapped first")
    args = ap.parse_args()

    from mapping import load_column_map, read_source, map_to_canonical
    raw = read_source(args.source)
    if args.map:
        canon, _ = map_to_canonical(raw, load_column_map(args.map, args.table))
    else:
        canon = raw
    rep = validate(canon, args.table)
    print(format_report(rep))
    raise SystemExit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
