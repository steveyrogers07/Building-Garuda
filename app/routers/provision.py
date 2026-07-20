"""GARUDA - self-provisioning of the Catalyst backend (minimal-console-steps path).

Zoho reserves *schema* creation (Data Store tables, NoSQL tables, Stratus
buckets, Cache segments) for the console/CLI - the SDK cannot create them.
Everything else this app can do for itself, from inside AppSail where the
ambient admin credentials live:

  GET  /admin/provision          what exists vs what GARUDA expects - tables
                                 (with row counts), buckets, cache segment.
                                 The console to-do list writes itself.
  POST /admin/provision/load     bulk-load every EXPECTED table that exists
                                 and is still empty, from the CSVs bundled in
                                 this very deployment (data/synthetic/_dev_subset
                                 + console_users.csv). Idempotent: non-empty
                                 tables are skipped, so re-calling never
                                 duplicates rows. Honors the Dev-tier caps by
                                 construction (the subset was carved for them).

Both are token-gated by GARUDA_JOBS_TOKEN when set (same default-off contract
as /jobs/*). Loading is safe-by-construction: synthetic rows, skip-if-nonempty.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from typing import Optional

router = APIRouter(tags=["provision"])

_HERE = Path(__file__).resolve()
for _c in (_HERE.parents[2], _HERE.parents[1]):
    if (_c / "data").is_dir():
        _REPO = _c
        break
else:
    _REPO = _HERE.parents[2]

_SUBSET = _REPO / "data" / "synthetic" / "_dev_subset"
_REFERENCE = _REPO / "data" / "reference"

# table -> bundled CSV. Console_Users seeds from the committed reference file.
EXPECTED_CORE = {
    "Incidents": _SUBSET / "Incidents.csv",
    "Entities": _SUBSET / "Entities.csv",
    "Incident_Edges": _SUBSET / "Incident_Edges.csv",
    "Case_Sections": _SUBSET / "Case_Sections.csv",
    "Arrests": _SUBSET / "Arrests.csv",
    "Chargesheets": _SUBSET / "Chargesheets.csv",
    "Officers": _SUBSET / "Officers.csv",
    "Courts": _SUBSET / "Courts.csv",
    "Case_Status": _SUBSET / "Case_Status.csv",
    "Crime_Head_Sections": _SUBSET / "Crime_Head_Sections.csv",
    "Socioeconomic": _SUBSET / "Socioeconomic.csv",
    "Geo_Boundaries": _SUBSET / "Geo_Boundaries.csv",
    "Units": _SUBSET / "Units.csv",
    "Console_Users": _REFERENCE / "console_users.csv",
}
# created empty now, filled by the engines' zcql write arms later
EXPECTED_DERIVED = ["MO_Clusters", "Crime_Series", "Predictive_Risk",
                    "Alerts", "Review_Queue", "Audit_Log"]
EXPECTED_BUCKETS = ["raw-fir", "briefs"]

_BATCH = 200
# Boolean columns in the subset (everything else loads as text/number strings,
# which the Data Store row API coerces against the column type).
_BOOL_COLS = {"is_police", "is_accused", "is_complainant_accused"}


def _check_token(token):
    expected = os.environ.get("GARUDA_JOBS_TOKEN")
    if expected and token != expected:
        raise HTTPException(403, "bad or missing X-Jobs-Token")


def _app():
    from shared import catalyst_ctx        # request-scoped SDK context
    return catalyst_ctx.app()


def _existing_tables(app):
    return {t.get("table_name"): t for t in
            (x if isinstance(x, dict) else x.to_dict()
             for x in app.datastore().get_all_tables())}


def _row_count(app, table):
    try:
        res = app.zcql().execute_query(f"SELECT COUNT(ROWID) FROM {table}")
        first = res[0] if res else {}
        inner = first.get(table, first)
        for v in inner.values():
            return int(v)
    except Exception:                          # noqa: BLE001
        return None
    return None


def _coerce(row):
    out = {}
    for k, v in row.items():
        if v == "" or v is None:
            out[k] = None
        elif k in _BOOL_COLS:
            out[k] = str(v).strip().lower() in ("true", "1", "yes")
        else:
            out[k] = v
    return out


@router.get("/admin/provision")
def provision_status(x_jobs_token: Optional[str] = Header(None)):
    """The console to-do list, computed from what actually exists."""
    _check_token(x_jobs_token)
    try:
        app = _app()
    except Exception as exc:                   # noqa: BLE001
        raise HTTPException(503, f"Catalyst SDK context unavailable: {exc}")

    existing = _existing_tables(app)
    tables = {}
    for name in list(EXPECTED_CORE) + EXPECTED_DERIVED:
        if name in existing:
            tables[name] = {"exists": True, "rows": _row_count(app, name)}
        else:
            tables[name] = {"exists": False}
    missing = [n for n, t in tables.items() if not t["exists"]]

    buckets = {}
    for b in EXPECTED_BUCKETS:
        try:
            buckets[b] = bool(app.stratus().head_bucket(b))
        except Exception:                      # noqa: BLE001
            buckets[b] = False

    from shared import kvcache
    cache_ok = bool(kvcache.put("provision:ping", {"ok": True}, ttl_hours=1)
                    and kvcache.get("provision:ping"))

    return {
        "tables": tables,
        "console_todo": {
            "create_tables": missing,
            "create_buckets": [b for b, ok in buckets.items() if not ok],
            "cache_segment_reachable": cache_ok,
        },
        "loadable_now": [n for n, t in tables.items()
                         if t["exists"] and not t.get("rows") and n in EXPECTED_CORE],
        "hint": "POST /admin/provision/load fills every empty expected table "
                "from the CSVs bundled in this deployment.",
    }


@router.post("/admin/provision/load")
def provision_load(x_jobs_token: Optional[str] = Header(None)):
    """Bulk-load empty expected tables from the bundled subset CSVs."""
    _check_token(x_jobs_token)
    try:
        app = _app()
    except Exception as exc:                   # noqa: BLE001
        raise HTTPException(503, f"Catalyst SDK context unavailable: {exc}")

    existing = _existing_tables(app)
    report = {}
    for name, path in EXPECTED_CORE.items():
        if name not in existing:
            report[name] = {"status": "missing - create it in the console first"}
            continue
        rows_present = _row_count(app, name)
        if rows_present:
            report[name] = {"status": "skipped - already has rows", "rows": rows_present}
            continue
        if not path.exists():
            report[name] = {"status": f"bundle CSV not found: {path.name}"}
            continue
        try:
            with open(path, encoding="utf-8") as f:
                rows = [_coerce(r) for r in csv.DictReader(f)]
            tbl = app.datastore().table(name)
            written = 0
            for i in range(0, len(rows), _BATCH):
                tbl.insert_rows(rows[i:i + _BATCH])
                written += len(rows[i:i + _BATCH])
            report[name] = {"status": "loaded", "rows": written}
        except Exception as exc:               # noqa: BLE001
            report[name] = {"status": f"failed after partial load: {exc}",
                            "rows_before_failure": _row_count(app, name)}
    ok = all(r.get("status") in ("loaded",) or "skipped" in r.get("status", "")
             for r in report.values())
    return {"ok": ok, "report": report}
