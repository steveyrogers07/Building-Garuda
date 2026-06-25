"""GARUDA — batch data access for the Phase-4 analytics endpoints.

Two backends, selected by GARUDA_BACKEND:
  - "local" (default): read the Phase-2 CSVs, write resolved outputs back as CSVs. Pure
    local/free — lets /resolve/run and /mo/run be exercised without Catalyst.
  - "zcql": read Entities/Incidents from the Catalyst Data Store and write canonical_id /
    mo_cluster_id back via ZCQL, batched. Account-gated (needs the live project + the
    zcatalyst SDK); imported lazily so the local path never requires it.

Writes use the Text business keys (entity_id / incident_id), never ROWID — consistent with
the Phase-2 FK strategy. Original Entities are never deleted; resolution only adds
canonical_id + match_confidence (alias_of lineage is preserved).
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYN_DIR = Path(os.environ.get("GARUDA_SYN_DIR", REPO / "data" / "synthetic"))
BACKEND = os.environ.get("GARUDA_BACKEND", "local").lower()
ZCQL_BATCH = 200

# Phase-5 outputs (crime_series / alerts / cached ego-subgraphs) land here. Defaults
# to a repo-local dir; point GARUDA_HOME at an external folder to keep generated
# artifacts out of the repo (the local PoC runner uses ~/…/Desktop/garuda).
OUT_DIR = Path(os.environ.get("GARUDA_HOME", REPO / "data" / "local"))


# --------------------------------------------------------------------------- #
# local CSV helpers
# --------------------------------------------------------------------------- #
def _read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _zcatalyst_zcql():
    import zcatalyst_sdk                       # deferred (account-gated)
    return zcatalyst_sdk.initialize().zcql()


def _zcql_rows(table, result):
    """ZCQL returns [{table: {col: val}}]; flatten to the inner dict."""
    return [r[table] for r in result]


# --------------------------------------------------------------------------- #
# reads
# --------------------------------------------------------------------------- #
def fetch_entities():
    if BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = zcql.execute_query(
            "SELECT entity_id, type, value, age, gender FROM Entities")
        return _zcql_rows("Entities", rows)
    return [
        {k: r.get(k, "") for k in ("entity_id", "type", "value", "age", "gender")}
        for r in _read_csv(SYN_DIR / "entities.csv")
    ]


def fetch_incidents():
    cols = ("incident_id", "mo_text", "crime_type", "occurred_at",
            "lat", "long", "address_text", "district_code")
    if BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = zcql.execute_query(
            "SELECT " + ", ".join(cols) + " FROM Incidents")
        return _zcql_rows("Incidents", rows)
    return [{k: r.get(k, "") for k in cols} for r in _read_csv(SYN_DIR / "incidents.csv")]


# --------------------------------------------------------------------------- #
# writes
# --------------------------------------------------------------------------- #
def _sql_escape(v):
    return str(v).replace("'", "''")


def _zcql_update_batches(statements):
    """Run UPDATE statements in batches of ZCQL_BATCH (ZCQL has no multi-row UPDATE)."""
    zcql = _zcatalyst_zcql()
    done = 0
    for i in range(0, len(statements), ZCQL_BATCH):
        for stmt in statements[i:i + ZCQL_BATCH]:
            zcql.execute_query(stmt)
            done += 1
    return done


def write_entity_resolution(assignments):
    """assignments: {entity_id: {canonical_id, match_confidence}}."""
    if BACKEND == "zcql":
        stmts = [
            f"UPDATE Entities SET canonical_id='{_sql_escape(a['canonical_id'])}', "
            f"match_confidence={float(a['match_confidence'])} "
            f"WHERE entity_id='{_sql_escape(eid)}'"
            for eid, a in assignments.items()
        ]
        return _zcql_update_batches(stmts)
    # local: emit a resolved copy (never overwrite the source of truth)
    src = _read_csv(SYN_DIR / "entities.csv")
    out = SYN_DIR / "entities_resolved.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(src[0].keys()))
        w.writeheader()
        for r in src:
            a = assignments.get(r["entity_id"])
            if a:
                r["canonical_id"] = a["canonical_id"]
                r["match_confidence"] = a["match_confidence"]
            w.writerow(r)
    return len(src)


def write_incident_mo(assignments):
    """assignments: {incident_id: mo_cluster_id}."""
    if BACKEND == "zcql":
        stmts = [
            f"UPDATE Incidents SET mo_cluster_id='{_sql_escape(cid)}' "
            f"WHERE incident_id='{_sql_escape(iid)}'"
            for iid, cid in assignments.items() if cid
        ]
        return _zcql_update_batches(stmts)
    src = _read_csv(SYN_DIR / "incidents.csv")
    out = SYN_DIR / "incidents_mo.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(src[0].keys()))
        w.writeheader()
        for r in src:
            r["mo_cluster_id"] = assignments.get(r["incident_id"], "")
            w.writerow(r)
    return len(src)


def write_incident_coords(updates):
    """updates: {incident_id: (lat, long)} — backfill of previously missing coords."""
    if BACKEND == "zcql":
        stmts = [
            f"UPDATE Incidents SET lat={float(lat)}, long={float(lng)} "
            f"WHERE incident_id='{_sql_escape(iid)}'"
            for iid, (lat, lng) in updates.items()
        ]
        return _zcql_update_batches(stmts)
    return len(updates)   # local: coords already present in the synthetic set


def write_mo_clusters(clusters):
    """Populate the MO_Clusters table (insert)."""
    if BACKEND == "zcql":
        app_zcql = _zcatalyst_zcql()
        cols = ["cluster_id", "crime_type", "size", "label",
                "centroid_features", "exemplar_incident_id"]
        done = 0
        for i in range(0, len(clusters), ZCQL_BATCH):
            for c in clusters[i:i + ZCQL_BATCH]:
                vals = ", ".join(
                    str(int(c[k])) if k == "size" else f"'{_sql_escape(c[k])}'"
                    for k in cols)
                app_zcql.execute_query(
                    f"INSERT INTO MO_Clusters ({', '.join(cols)}) VALUES ({vals})")
                done += 1
        return done
    out = SYN_DIR / "mo_clusters.csv"
    if not clusters:
        return 0
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(clusters[0].keys()))
        w.writeheader()
        w.writerows(clusters)
    return len(clusters)


# --------------------------------------------------------------------------- #
# Phase-5 reads — prefer the Phase-4 resolved/MO outputs, fall back to base CSVs
# so the network/series engines run even before Phase 4 has been executed.
# --------------------------------------------------------------------------- #
def _read_first_existing(*names):
    for n in names:
        p = SYN_DIR / n
        if p.exists():
            return _read_csv(p)
    return []


_P5_INC_COLS = ("incident_id", "crime_type", "occurred_at", "lat", "long",
                "district_code", "mo_cluster_id", "series_id", "address_text")


def fetch_incidents_p5():
    if BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = zcql.execute_query("SELECT " + ", ".join(_P5_INC_COLS) + " FROM Incidents")
        return _zcql_rows("Incidents", rows)
    rows = _read_first_existing("incidents_mo.csv", "incidents.csv")
    return [{k: r.get(k, "") for k in _P5_INC_COLS} for r in rows]


def fetch_entities_p5():
    """Canonical entities for the network graph. canonical_id falls back to
    entity_id when resolution hasn't run, so the graph is always buildable."""
    if BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = _zcql_rows("Entities", zcql.execute_query(
            "SELECT entity_id, canonical_id, type, value FROM Entities"))
    else:
        rows = _read_first_existing("entities_resolved.csv", "entities.csv")
    out = []
    for r in rows:
        cid = (r.get("canonical_id") or "").strip() or r.get("entity_id")
        out.append({"entity_id": r.get("entity_id"), "canonical_id": cid,
                    "type": r.get("type", ""), "value": r.get("value", "")})
    return out


def fetch_edges_p5():
    cols = ("incident_id", "entity_id", "role", "edge_weight", "evidence_type")
    if BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = zcql.execute_query("SELECT " + ", ".join(cols) + " FROM Incident_Edges")
        return _zcql_rows("Incident_Edges", rows)
    return [{k: r.get(k, "") for k in cols}
            for r in _read_csv(SYN_DIR / "incident_edges.csv")]


# --------------------------------------------------------------------------- #
# Phase-5 writes — Crime_Series / Alerts / Incidents.series_id / cached subgraphs
# --------------------------------------------------------------------------- #
_CRIME_SERIES_COLS = ["series_id", "crime_type", "district_code", "locality",
                      "start_date", "end_date", "incident_count", "method"]
_ALERTS_COLS = ["alert_id", "type", "district_code", "crime_type", "severity",
                "window_start", "window_end", "detail", "status"]


def _write_out_csv(name, rows, cols):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return OUT_DIR / name


def write_crime_series(series):
    if BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        for i in range(0, len(series), ZCQL_BATCH):
            for s in series[i:i + ZCQL_BATCH]:
                vals = ", ".join(
                    str(int(s["incident_count"])) if k == "incident_count"
                    else f"'{_sql_escape(s.get(k, ''))}'" for k in _CRIME_SERIES_COLS)
                zcql.execute_query(
                    f"INSERT INTO Crime_Series ({', '.join(_CRIME_SERIES_COLS)}) "
                    f"VALUES ({vals})")
        return len(series)
    _write_out_csv("crime_series.csv", series, _CRIME_SERIES_COLS)
    return len(series)


def write_incident_series(assignments):
    """assignments: {incident_id: series_id}."""
    if BACKEND == "zcql":
        stmts = [f"UPDATE Incidents SET series_id='{_sql_escape(sid)}' "
                 f"WHERE incident_id='{_sql_escape(iid)}'"
                 for iid, sid in assignments.items() if sid]
        return _zcql_update_batches(stmts)
    rows = [{"incident_id": k, "series_id": v} for k, v in assignments.items()]
    _write_out_csv("incidents_series.csv", rows, ["incident_id", "series_id"])
    return len(rows)


def write_alerts(alerts):
    if BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        for i in range(0, len(alerts), ZCQL_BATCH):
            for al in alerts[i:i + ZCQL_BATCH]:
                vals = ", ".join(f"'{_sql_escape(al.get(k, ''))}'" for k in _ALERTS_COLS)
                zcql.execute_query(
                    f"INSERT INTO Alerts ({', '.join(_ALERTS_COLS)}) VALUES ({vals})")
        return len(alerts)
    _write_out_csv("alerts.csv", alerts, _ALERTS_COLS)
    return len(alerts)


def write_network_cache(center, payload):
    """Cache an ego-subgraph JSON (NoSQL/Cache in prod; a local file for the PoC)."""
    import json
    d = OUT_DIR / "network"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{center}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(p)
