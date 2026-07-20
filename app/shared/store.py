"""GARUDA - batch data access for the Phase-4 analytics endpoints.

Two backends, selected independently for reads and writes (Catalyst plan §4.1 Option A -
bundled-CSV serving with the Data Store as system-of-record for writes):
  - GARUDA_READ_BACKEND - "local" (default): corpus reads (Entities/Incidents/edges/
    reference tables) come from the Phase-2 CSVs. "zcql": read them from the Catalyst
    Data Store instead (requires the pagination work in plan §4.1B - do not flip
    without it, ZCQL caps rows per query and would silently truncate the corpus).
  - GARUDA_WRITE_BACKEND - "local" (default): resolved outputs / alerts / audit rows land
    as CSVs. "zcql": write them to the Data Store via ZCQL, batched. Account-gated
    (needs the live project + the zcatalyst SDK); imported lazily so the local path
    never requires it.
GARUDA_BACKEND is honored as a legacy fallback that sets both.

Writes use the Text business keys (entity_id / incident_id), never ROWID - consistent with
the Phase-2 FK strategy. Original Entities are never deleted; resolution only adds
canonical_id + match_confidence (alias_of lineage is preserved).
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

# Locally, data/ sits two levels up from shared/store.py (repo_root/app/shared/).
# But Catalyst AppSail's build_path bundles only the *contents* of app/ as the
# deployment root, so in production data/ (once bundled - see
# docs/CATALYST_CREDITS_AND_DEPLOYMENT.md) sits just one level up instead. Try
# both so the same code runs unchanged from a full checkout or a deployed
# instance, instead of hard-failing with FileNotFoundError in prod.
_HERE = Path(__file__).resolve()
for _candidate in (_HERE.parents[2], _HERE.parents[1]):
    if (_candidate / "data").is_dir():
        REPO = _candidate
        break
else:
    REPO = _HERE.parents[2]
SYN_DIR = Path(os.environ.get("GARUDA_SYN_DIR", REPO / "data" / "synthetic"))
_LEGACY_BACKEND = os.environ.get("GARUDA_BACKEND", "").lower()
READ_BACKEND = (os.environ.get("GARUDA_READ_BACKEND") or _LEGACY_BACKEND or "local").lower()
WRITE_BACKEND = (os.environ.get("GARUDA_WRITE_BACKEND") or _LEGACY_BACKEND or "local").lower()
ZCQL_BATCH = 200

def _zcql_failed(fn):
    """A zcql arm failed (typically: the console table does not exist yet).
    Log once per call site and fall through to the local arm, so setting
    GARUDA_WRITE_BACKEND=zcql before the console work is done degrades
    gracefully instead of 500ing endpoints - and self-activates the moment
    the tables appear. Local fallbacks on an AppSail instance are ephemeral;
    the log line is the operator's signal to finish the console setup."""
    import logging
    logging.getLogger("garuda").warning(
        "zcql arm failed in %s - falling back to local", fn, exc_info=True)


# Phase-5 outputs (crime_series / alerts / cached ego-subgraphs) land here. Defaults
# to a repo-local dir; point GARUDA_HOME at an external folder to keep generated
# artifacts out of the repo (the local PoC runner uses ~/…/Desktop/garuda).
OUT_DIR = Path(os.environ.get("GARUDA_HOME", REPO / "data" / "local"))


# --------------------------------------------------------------------------- #
# local CSV helpers
# --------------------------------------------------------------------------- #
# Every analytics/workbench read (stats, geo, anomaly, dossier, search, ...) goes
# through this on every request with no caller-side caching. Re-opening and
# re-parsing multi-thousand-row CSVs on each API call is the single biggest
# source of perceived UI lag (every screen navigation re-pays it). Cache the
# parsed rows keyed by (path, mtime, size); writers use plain open(path, "w"),
# which changes mtime, so the cache self-invalidates on the next read with no
# extra plumbing.
_CSV_CACHE: dict[str, tuple[float, int, list[dict]]] = {}


def _read_csv(path):
    path = str(path)
    try:
        st = os.stat(path)
    except OSError:
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    key = (st.st_mtime, st.st_size)
    cached = _CSV_CACHE.get(path)
    if cached is not None and cached[:2] == key:
        return cached[2]
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    _CSV_CACHE[path] = (st.st_mtime, st.st_size, rows)
    return rows


def _zcatalyst_zcql():
    from shared import catalyst_ctx        # request-scoped SDK context
    return catalyst_ctx.app().zcql()


def _zcql_rows(table, result):
    """ZCQL returns [{table: {col: val}}]; flatten to the inner dict."""
    return [r[table] for r in result]


# --------------------------------------------------------------------------- #
# reads
# --------------------------------------------------------------------------- #
def fetch_entities():
    if READ_BACKEND == "zcql":
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
    if READ_BACKEND == "zcql":
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
    if WRITE_BACKEND == "zcql":
        try:
            stmts = [
                f"UPDATE Entities SET canonical_id='{_sql_escape(a['canonical_id'])}', "
                f"match_confidence={float(a['match_confidence'])} "
                f"WHERE entity_id='{_sql_escape(eid)}'"
                for eid, a in assignments.items()
            ]
            return _zcql_update_batches(stmts)
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_entity_resolution")
    # local: emit a resolved copy (never overwrite the source of truth)
    src = _read_csv(SYN_DIR / "entities.csv")
    out = SYN_DIR / "entities_resolved.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(src[0].keys()))
        w.writeheader()
        for r in src:
            a = assignments.get(r["entity_id"])
            if a:
                # copy before mutating - `src` rows are shared with the cached
                # entities.csv parse; writing in place would corrupt that cache
                r = {**r, "canonical_id": a["canonical_id"], "match_confidence": a["match_confidence"]}
            w.writerow(r)
    return len(src)


def write_incident_mo(assignments):
    """assignments: {incident_id: mo_cluster_id}."""
    if WRITE_BACKEND == "zcql":
        try:
            stmts = [
                f"UPDATE Incidents SET mo_cluster_id='{_sql_escape(cid)}' "
                f"WHERE incident_id='{_sql_escape(iid)}'"
                for iid, cid in assignments.items() if cid
            ]
            return _zcql_update_batches(stmts)
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_incident_mo")
    src = _read_csv(SYN_DIR / "incidents.csv")
    out = SYN_DIR / "incidents_mo.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(src[0].keys()))
        w.writeheader()
        for r in src:
            # copy before mutating - `src` rows are shared with the cached
            # incidents.csv parse; writing in place would corrupt that cache
            r = {**r, "mo_cluster_id": assignments.get(r["incident_id"], "")}
            w.writerow(r)
    return len(src)


def write_incident_coords(updates):
    """updates: {incident_id: (lat, long)} - backfill of previously missing coords."""
    if WRITE_BACKEND == "zcql":
        try:
            stmts = [
                f"UPDATE Incidents SET lat={float(lat)}, long={float(lng)} "
                f"WHERE incident_id='{_sql_escape(iid)}'"
                for iid, (lat, lng) in updates.items()
            ]
            return _zcql_update_batches(stmts)
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_incident_coords")
    return len(updates)   # local: coords already present in the synthetic set


def write_mo_clusters(clusters):
    """Populate the MO_Clusters table (insert)."""
    if WRITE_BACKEND == "zcql":
        try:
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
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_mo_clusters")
    out = SYN_DIR / "mo_clusters.csv"
    if not clusters:
        return 0
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(clusters[0].keys()))
        w.writeheader()
        w.writerows(clusters)
    return len(clusters)


# --------------------------------------------------------------------------- #
# Phase-5 reads - prefer the Phase-4 resolved/MO outputs, fall back to base CSVs
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
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = zcql.execute_query("SELECT " + ", ".join(_P5_INC_COLS) + " FROM Incidents")
        return _zcql_rows("Incidents", rows)
    rows = _read_first_existing("incidents_mo.csv", "incidents.csv")
    return [{k: r.get(k, "") for k in _P5_INC_COLS} for r in rows]


def fetch_entities_p5():
    """Canonical entities for the network graph. canonical_id falls back to
    entity_id when resolution hasn't run, so the graph is always buildable."""
    if READ_BACKEND == "zcql":
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
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = zcql.execute_query("SELECT " + ", ".join(cols) + " FROM Incident_Edges")
        return _zcql_rows("Incident_Edges", rows)
    return [{k: r.get(k, "") for k in cols}
            for r in _read_csv(SYN_DIR / "incident_edges.csv")]


# --------------------------------------------------------------------------- #
# Phase-5 writes - Crime_Series / Alerts / Incidents.series_id / cached subgraphs
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
    if WRITE_BACKEND == "zcql":
        try:
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
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_crime_series")
    _write_out_csv("crime_series.csv", series, _CRIME_SERIES_COLS)
    return len(series)


def write_incident_series(assignments):
    """assignments: {incident_id: series_id}."""
    if WRITE_BACKEND == "zcql":
        try:
            stmts = [f"UPDATE Incidents SET series_id='{_sql_escape(sid)}' "
                     f"WHERE incident_id='{_sql_escape(iid)}'"
                     for iid, sid in assignments.items() if sid]
            return _zcql_update_batches(stmts)
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_incident_series")
    rows = [{"incident_id": k, "series_id": v} for k, v in assignments.items()]
    _write_out_csv("incidents_series.csv", rows, ["incident_id", "series_id"])
    return len(rows)


def write_alerts(alerts):
    if WRITE_BACKEND == "zcql":
        try:
            zcql = _zcatalyst_zcql()
            for i in range(0, len(alerts), ZCQL_BATCH):
                for al in alerts[i:i + ZCQL_BATCH]:
                    vals = ", ".join(f"'{_sql_escape(al.get(k, ''))}'" for k in _ALERTS_COLS)
                    zcql.execute_query(
                        f"INSERT INTO Alerts ({', '.join(_ALERTS_COLS)}) VALUES ({vals})")
            return len(alerts)
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_alerts")
    _write_out_csv("alerts.csv", alerts, _ALERTS_COLS)
    return len(alerts)


NOSQL_EGO_TABLE = os.environ.get("GARUDA_NOSQL_EGO_TABLE", "EgoGraphCache")


def _nosql_ego_table():
    from shared import catalyst_ctx        # request-scoped SDK context
    return catalyst_ctx.app().nosql().get_table(NOSQL_EGO_TABLE)


def write_network_cache(center, payload):
    """Cache an ego-subgraph JSON (plan §4.6): Catalyst NoSQL under the zcql
    write arm (variable-shape JSON that doesn't fit the relational tables);
    a local file otherwise. The NoSQL arm is best-effort - any failure falls
    back to the local file so the endpoint's contract never changes."""
    import json
    raw = json.dumps(payload, ensure_ascii=False)
    if WRITE_BACKEND == "zcql":
        try:
            _nosql_ego_table().insert_items(
                {"item": {"canonical_id": {"S": str(center)},
                          "payload": {"S": raw}}})
            return f"nosql://{NOSQL_EGO_TABLE}/{center}"
        except Exception:                      # noqa: BLE001 - degrade to file
            pass
    d = OUT_DIR / "network"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{center}.json"
    p.write_text(raw, encoding="utf-8")
    return str(p)


def read_network_cache(center):
    """Cached ego-subgraph or None (GET /network/{id}?cached=true fast path).
    Follows the write arm, like read_audit_log - it reads back what
    write_network_cache produced."""
    import json
    if WRITE_BACKEND == "zcql":
        try:
            res = _nosql_ego_table().fetch_item(
                {"keys": [{"canonical_id": {"S": str(center)}}]})
            for it in (res.get or []):
                item = it.get("item", it) if isinstance(it, dict) else {}
                raw = item.get("payload")
                if isinstance(raw, dict):      # typed attr not deserialized
                    raw = raw.get("S")
                if raw:
                    return json.loads(raw)
        except Exception:                      # noqa: BLE001 - degrade to miss
            return None
        return None
    p = OUT_DIR / "network" / f"{center}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Phase-6 reads/writes - socio-economic context + Predictive_Risk
# --------------------------------------------------------------------------- #
# district_name matters: the copilot's district parsing and the hotspot map's
# labels both read it - dropping it silently reduced "in Mysuru" to statewide.
_SOCIO_COLS = ("area_code", "district_name", "population", "density", "literacy",
               "urbanization")
_PRED_RISK_COLS = ["grid_id", "district_code", "crime_type", "period", "risk_score",
                   "rank", "top_drivers", "model_version", "backtest_pai"]


def fetch_socioeconomic():
    """Per-area socio-economic features. Locally sourced from the Census reference
    CSV; from the Socioeconomic Data Store table under GARUDA_READ_BACKEND=zcql."""
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Socioeconomic", zcql.execute_query(
            "SELECT " + ", ".join(_SOCIO_COLS) + " FROM Socioeconomic"))
    p = SYN_DIR.parent / "reference" / "census_2011.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _SOCIO_COLS} for r in rows]


def write_predictive_risk(rows):
    """Persist forecast risk per (area x period x crime_type) -> Predictive_Risk."""
    if WRITE_BACKEND == "zcql":
        try:
            zcql = _zcatalyst_zcql()
            for i in range(0, len(rows), ZCQL_BATCH):
                for r in rows[i:i + ZCQL_BATCH]:
                    vals = ", ".join(
                        (str(float(r.get(k) or 0)) if k in ("risk_score", "backtest_pai")
                         else str(int(r.get(k) or 0)) if k == "rank"
                         else f"'{_sql_escape(r.get(k, ''))}'")
                        for k in _PRED_RISK_COLS)
                    zcql.execute_query(
                        f"INSERT INTO Predictive_Risk ({', '.join(_PRED_RISK_COLS)}) "
                        f"VALUES ({vals})")
            return len(rows)
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_predictive_risk")
    _write_out_csv("predictive_risk.csv", rows, _PRED_RISK_COLS)
    return len(rows)


# --------------------------------------------------------------------------- #
# Phase-7 reads/writes - copilot narratives + Audit_Log
# --------------------------------------------------------------------------- #
_COPILOT_INC_COLS = ("incident_id", "fir_no", "occurred_at", "district_code",
                     "station_code", "crime_type", "ipc_bns_code", "mo_text",
                     "address_text", "source_fir_url")
_AUDIT_COLS = ["log_id", "actor", "role", "action", "resource", "query_text", "ts", "ip"]


def fetch_incidents_copilot():
    """Incidents with narrative + citation columns for the copilot."""
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Incidents", zcql.execute_query(
            "SELECT " + ", ".join(_COPILOT_INC_COLS) + " FROM Incidents"))
    rows = _read_first_existing("incidents_mo.csv", "incidents.csv")
    return [{k: r.get(k, "") for k in _COPILOT_INC_COLS} for r in rows]


def write_audit_log(entries):
    """Append copilot queries to Audit_Log (governance trail; never overwrite)."""
    if isinstance(entries, dict):
        entries = [entries]
    if WRITE_BACKEND == "zcql":
        try:
            zcql = _zcatalyst_zcql()
            for e in entries:
                vals = ", ".join(f"'{_sql_escape(e.get(k, ''))}'" for k in _AUDIT_COLS)
                zcql.execute_query(
                    f"INSERT INTO Audit_Log ({', '.join(_AUDIT_COLS)}) VALUES ({vals})")
            return len(entries)
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("write_audit_log")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / "audit_log.csv"
    new = not p.exists()
    with open(p, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_AUDIT_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(entries)
    return len(entries)


_CONSOLE_USER_COLS = ("email", "role", "scope", "officer_id", "display_name")


def fetch_console_user(email):
    """RBAC principal for a verified sign-in (plan §4.4): map a Catalyst-
    authenticated email to GARUDA role/scope. Branches on WRITE_BACKEND like
    read_audit_log: Console_Users is seeded into the Data Store (the write
    half's system-of-record), not part of the bundled read corpus; locally a
    committed reference CSV stands in so the prod path is testable offline."""
    if not email:
        return None
    if WRITE_BACKEND == "zcql":
        try:
            zcql = _zcatalyst_zcql()
            rows = _zcql_rows("Console_Users", zcql.execute_query(
                "SELECT " + ", ".join(_CONSOLE_USER_COLS) +
                " FROM Console_Users WHERE email='" + _sql_escape(email) + "'"))
            return rows[0] if rows else None
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("fetch_console_user")
    p = SYN_DIR.parent / "reference" / "console_users.csv"
    for r in (_read_csv(p) if p.exists() else []):
        if (r.get("email") or "").strip().lower() == email.strip().lower():
            return {k: r.get(k, "") for k in _CONSOLE_USER_COLS}
    return None


def read_audit_log(limit=100):
    """Most-recent audit entries (admin/ethics only - gated at the API layer).

    Branches on WRITE_BACKEND, not READ_BACKEND: this reads back what
    write_audit_log produced, so it must look wherever those rows landed -
    under the prod split (reads local / writes zcql) the trail lives in the
    Data Store, and reading the local CSV would show an empty audit view."""
    if WRITE_BACKEND == "zcql":
        try:
            zcql = _zcatalyst_zcql()
            return _zcql_rows("Audit_Log", zcql.execute_query(
                "SELECT " + ", ".join(_AUDIT_COLS) + " FROM Audit_Log"))[:limit]
        except Exception:  # noqa: BLE001 - table missing / unreachable
            _zcql_failed("read_audit_log")
    p = OUT_DIR / "audit_log.csv"
    return list(reversed(_read_csv(p)))[:limit] if p.exists() else []


# --------------------------------------------------------------------------- #
# Phase-9 reads - incident + its parties (governed: masking applied at API layer)
# --------------------------------------------------------------------------- #
_CASE_COLS = ("incident_id", "fir_no", "crime_no", "case_no", "occurred_at",
              "district_code", "station_code",
              "crime_type", "ipc_bns_code", "status", "source_fir_url",
              "case_category", "gravity", "officer_id",
              "incident_to_date", "info_received_ps_date", "court_id")


def fetch_incident(incident_id):
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = _zcql_rows("Incidents", zcql.execute_query(
            "SELECT " + ", ".join(_CASE_COLS) + " FROM Incidents WHERE incident_id='"
            + _sql_escape(incident_id) + "'"))
        return rows[0] if rows else None
    for r in _read_first_existing("incidents_mo.csv", "incidents.csv"):
        if r.get("incident_id") == incident_id:
            return {k: r.get(k, "") for k in _CASE_COLS}
    return None


def fetch_incident_parties(incident_id):
    """Persons / vehicles / phones linked to an incident, with role - for the case
    view. Raw values; the governance layer masks victim/witness PII by role."""
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        rows = _zcql_rows("Incident_Edges", zcql.execute_query(
            "SELECT entity_id, role, evidence_type, is_police FROM Incident_Edges "
            "WHERE incident_id='" + _sql_escape(incident_id) + "'"))
        ents = {e["entity_id"]: e for e in _zcql_rows("Entities", zcql.execute_query(
            "SELECT entity_id, canonical_id, type, value, age, gender FROM Entities"))}
    else:
        rows = [e for e in _read_csv(SYN_DIR / "incident_edges.csv")
                if e.get("incident_id") == incident_id]
        ents = {e["entity_id"]: e for e in _read_first_existing("entities_resolved.csv", "entities.csv")}
    out = []
    for e in rows:
        ent = ents.get(e.get("entity_id"), {})
        out.append({"role": e.get("role"), "entity_id": e.get("entity_id"),
                    "canonical_id": ent.get("canonical_id") or e.get("entity_id"),
                    "type": ent.get("type"), "value": ent.get("value"),
                    "age": ent.get("age"), "gender": ent.get("gender"),
                    "evidence_type": e.get("evidence_type"),
                    # VictimPolice (P2 #12) - only meaningful when role == "victim"
                    "is_police": e.get("is_police") or None})
    return out


_FULL_INC_COLS = ("incident_id", "fir_no", "crime_no", "case_no", "occurred_at",
                  "reported_at", "district_code",
                  "station_code", "crime_type", "ipc_bns_code", "lat", "long",
                  "address_text", "mo_text", "status", "mo_cluster_id", "series_id",
                  "source_fir_url", "case_category", "gravity", "officer_id",
                  "incident_to_date", "info_received_ps_date", "court_id")


def fetch_incidents_full():
    """Every incident with the full column set - the workbench working set."""
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Incidents", zcql.execute_query(
            "SELECT " + ", ".join(_FULL_INC_COLS) + " FROM Incidents"))
    rows = _read_first_existing("incidents_mo.csv", "incidents.csv")
    return [{k: r.get(k, "") for k in _FULL_INC_COLS} for r in rows]


# --------------------------------------------------------------------------- #
# Officers / Chargesheets - organizer schema's Employee + ChargesheetDetails.
# Powers the District Command Card (clearance/conviction rate - blueprint §B1)
# and "who registered/investigated this FIR" on the case file.
# --------------------------------------------------------------------------- #
_OFFICER_COLS = ("officer_id", "name", "rank", "designation", "district_code", "unit_code",
                 "kgid", "dob", "blood_group", "appointment_date")
_CHARGESHEET_COLS = ("cs_id", "incident_id", "cs_date", "cs_type", "officer_id")


def fetch_officers():
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Officers", zcql.execute_query(
            "SELECT " + ", ".join(_OFFICER_COLS) + " FROM Officers"))
    p = SYN_DIR / "officers.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _OFFICER_COLS} for r in rows]


def fetch_chargesheets():
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Chargesheets", zcql.execute_query(
            "SELECT " + ", ".join(_CHARGESHEET_COLS) + " FROM Chargesheets"))
    p = SYN_DIR / "chargesheets.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _CHARGESHEET_COLS} for r in rows]


# --------------------------------------------------------------------------- #
# Arrests / Case_Sections - organizer schema's ArrestSurrender + ActSectionAssociation.
# Arrests start the 60/90-day default-bail clock (docs/product/08 §1) and define the
# absconding board (§6: suspects on open cases with no arrest row); Case_Sections is
# the one-to-many legal classification behind §5's per-section evidence gaps.
# --------------------------------------------------------------------------- #
_ARREST_COLS = ("arrest_id", "incident_id", "entity_id", "event_type", "event_date",
                "district_code", "court_id", "io_officer_id",
                "is_accused", "is_complainant_accused")
_CASE_SECTION_COLS = ("incident_id", "act_code", "section_code", "section_order", "act_order")


def fetch_arrests():
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Arrests", zcql.execute_query(
            "SELECT " + ", ".join(_ARREST_COLS) + " FROM Arrests"))
    p = SYN_DIR / "arrests.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _ARREST_COLS} for r in rows]


def fetch_case_sections():
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Case_Sections", zcql.execute_query(
            "SELECT " + ", ".join(_CASE_SECTION_COLS) + " FROM Case_Sections"))
    p = SYN_DIR / "case_sections.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _CASE_SECTION_COLS} for r in rows]


# --------------------------------------------------------------------------- #
# Courts / Case_Status / Crime_Head_Sections - organizer schema's Court,
# CaseStatusMaster and CrimeHeadActSection. Reference/master tables (schema
# completeness - P2 #10/#11/#14); Incidents.status/court_id stay denormalized
# text so no engine changes are needed to consume them.
# --------------------------------------------------------------------------- #
_COURT_COLS = ("court_id", "name", "district_code", "state_code")
_CASE_STATUS_COLS = ("status_code", "status_name")
_CRIME_HEAD_SECTION_COLS = ("crime_head", "act_code", "section_code")


def fetch_courts():
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Courts", zcql.execute_query(
            "SELECT " + ", ".join(_COURT_COLS) + " FROM Courts"))
    p = SYN_DIR / "courts.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _COURT_COLS} for r in rows]


def fetch_case_status():
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Case_Status", zcql.execute_query(
            "SELECT " + ", ".join(_CASE_STATUS_COLS) + " FROM Case_Status"))
    p = SYN_DIR / "case_status.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _CASE_STATUS_COLS} for r in rows]


_UNIT_COLS = ("unit_id", "unit_name", "unit_type", "parent_unit",
              "district_code", "district_num", "station_code", "lat", "long")


def fetch_units():
    """Units master (organizer schema: Unit/UnitType hierarchy) - station names,
    numeric ids (the CrimeNo segments) and centroids for the map drill-down."""
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Units", zcql.execute_query(
            "SELECT " + ", ".join(_UNIT_COLS) + " FROM Units"))
    p = SYN_DIR / "units.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _UNIT_COLS} for r in rows]


def fetch_crime_head_sections():
    if READ_BACKEND == "zcql":
        zcql = _zcatalyst_zcql()
        return _zcql_rows("Crime_Head_Sections", zcql.execute_query(
            "SELECT " + ", ".join(_CRIME_HEAD_SECTION_COLS) + " FROM Crime_Head_Sections"))
    p = SYN_DIR / "crime_head_sections.csv"
    rows = _read_csv(p) if p.exists() else []
    return [{k: r.get(k, "") for k in _CRIME_HEAD_SECTION_COLS} for r in rows]
