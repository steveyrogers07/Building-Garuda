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
