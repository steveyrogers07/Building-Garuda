"""GARUDA — investigation workbench engine (Iteration 11).

The object-centric layer that makes the console an investigation tool rather than
a dashboard: 360-degree entity dossiers, full case files with *explained* linked
cases, and universal search — every payload governance-aware (RBAC jurisdiction +
victim/witness masking incl. IPC-228A/POCSO), every claim traceable to a FIR.

Pure aggregation over shared.store + the existing engines (network graph for
associates, series linkage for case links, the copilot index for semantic search).
State is built lazily once and reused; `refresh()` drops it (nightly job).
"""
from __future__ import annotations

import re
import threading
import time
from collections import Counter, defaultdict

from engines import copilot as cp
from engines import network as net
from engines.series import link_series
from engines.series.linkage import _haversine_km, _parse_dt
from governance import masking
from shared import store

_STATE = {"v": None}
# guards the (rare) build path only — a background cache-warm thread (see
# app/main.py startup) can otherwise race a live dossier/case/search request
# into rebuilding this same expensive state twice at once.
_STATE_LOCK = threading.Lock()

# linked-case evidence weights: a shared burner phone/plate is the strongest tie
_LINK_W = {"shared_phone": 4, "shared_vehicle": 4, "shared_person": 3,
           "series": 3, "mo": 2, "near_repeat": 1}
NEAR_KM, NEAR_DAYS = 2.0, 14


# --------------------------------------------------------------------------- #
# state
# --------------------------------------------------------------------------- #
def state(rebuild=False):
    if _STATE["v"] is not None and not rebuild:
        return _STATE["v"]
    with _STATE_LOCK:
        if _STATE["v"] is None or rebuild:
            _build_state()
    return _STATE["v"]


def _build_state():
    t0 = time.time()
    inc = store.fetch_incidents_full()
    ents = store.fetch_entities_p5()          # canonical_id always set
    edges = store.fetch_edges_p5()
    officers_by_id = {o["officer_id"]: o for o in store.fetch_officers()}
    cs_by_inc = defaultdict(list)
    for c in store.fetch_chargesheets():
        cs_by_inc[c["incident_id"]].append(c)

    by_inc = {r["incident_id"]: r for r in inc}
    ent_by_id = {e["entity_id"]: e for e in ents}
    canon_meta = {}                            # canonical_id -> {type,value}
    aliases = defaultdict(list)                # canonical_id -> [entity rows]
    for e in ents:
        cid = e["canonical_id"]
        aliases[cid].append(e)
        if cid not in canon_meta or e["entity_id"] == cid:
            canon_meta[cid] = {"type": e["type"], "value": e["value"]}

    inc_canon = defaultdict(set)               # incident -> {canonical}
    canon_apps = defaultdict(list)             # canonical -> [(incident_id, role, evidence)]
    canon_roles = defaultdict(set)
    for ed in edges:
        e = ent_by_id.get(ed["entity_id"])
        if not e:
            continue
        cid = e["canonical_id"]
        inc_canon[ed["incident_id"]].add(cid)
        canon_apps[cid].append((ed["incident_id"], ed.get("role", ""), ed.get("evidence_type", "")))
        canon_roles[cid].add(ed.get("role", ""))

    # protected flag: canonical appears in any statutorily protected case
    canon_protected = {
        cid: any(masking.is_protected(by_inc.get(i, {}).get("crime_type"))
                 for i, _r, _e in apps)
        for cid, apps in canon_apps.items()
    }

    G = net.build_graph(inc, ents, edges)      # fast: no centrality here
    series = link_series(inc)                  # {assignments, series}

    _STATE["v"] = {
        "incidents": inc, "by_inc": by_inc, "entities": ents,
        "canon_meta": canon_meta, "aliases": aliases, "inc_canon": inc_canon,
        "canon_apps": canon_apps, "canon_roles": canon_roles,
        "canon_protected": canon_protected, "graph": G,
        "officers_by_id": officers_by_id, "chargesheets_by_inc": cs_by_inc,
        "series_of": series["assignments"],
        "series_rows": {s["series_id"]: s for s in series["series"]},
        "copilot": cp.prepare(inc),            # (index, refs) for semantic search
        "built_s": round(time.time() - t0, 1),
    }


def refresh():
    _STATE["v"] = None


# --------------------------------------------------------------------------- #
# governance helpers
# --------------------------------------------------------------------------- #
_VICTIM_ONLY = {"victim", "witness"}


def _subject_visible(st, cid, principal):
    """May this principal see the identity of canonical `cid`?
    Suspects/accused are operational and always visible (framed 'pending trial');
    victim/witness-only persons follow the masking rules per appearance
    jurisdiction, hard-masked if any appearance is IPC-228A/POCSO."""
    meta = st["canon_meta"].get(cid, {})
    if meta.get("type") != "person":
        return True
    roles = st["canon_roles"].get(cid, set())
    if roles - _VICTIM_ONLY:                       # has suspect/other operational role
        return True
    protected = st["canon_protected"].get(cid, False)
    for iid, _r, _e in st["canon_apps"].get(cid, ()):
        r = st["by_inc"].get(iid, {})
        if masking.can_see_victim(principal.role, principal.scope,
                                  r.get("district_code"), r.get("station_code"), protected):
            return True
    return False


def _label(st, cid, principal):
    meta = st["canon_meta"].get(cid, {"type": "", "value": cid})
    if _subject_visible(st, cid, principal):
        return meta.get("value", cid), None
    v = meta.get("value", "")
    masked = masking.mask_name(v) if meta.get("type") == "person" else masking.mask_phone(v)
    reason = "IPC-228A/POCSO" if st["canon_protected"].get(cid) else "jurisdiction"
    return masked, reason


# --------------------------------------------------------------------------- #
# dossier
# --------------------------------------------------------------------------- #
def dossier(entity_or_canonical_id, principal, max_associates=14):
    st = state()
    cid = entity_or_canonical_id
    if cid not in st["canon_meta"]:                # accept an alias entity_id too
        e = next((x for x in st["entities"] if x["entity_id"] == cid), None)
        if not e:
            return {"error": "not_found", "id": entity_or_canonical_id}
        cid = e["canonical_id"]
    meta = st["canon_meta"][cid]
    value, mask_reason = _label(st, cid, principal)

    apps = []
    for iid, role, ev in sorted(st["canon_apps"].get(cid, ()),
                                key=lambda a: st["by_inc"].get(a[0], {}).get("occurred_at", ""),
                                reverse=True):
        r = st["by_inc"].get(iid, {})
        apps.append({"incident_id": iid, "fir_no": r.get("fir_no"), "role": role,
                     "evidence_type": ev, "crime_type": r.get("crime_type"),
                     "district_code": r.get("district_code"),
                     "occurred_at": r.get("occurred_at"), "status": r.get("status")})

    districts = sorted({a["district_code"] for a in apps if a["district_code"]})
    dates = sorted(a["occurred_at"][:10] for a in apps if a["occurred_at"])
    months = Counter(a["occurred_at"][:7] for a in apps if a["occurred_at"])

    G = st["graph"]
    associates = []
    if cid in G:
        for nb in sorted(G[cid], key=lambda n: -G[cid][n]["weight"])[:max_associates]:
            lab, mrs = _label(st, nb, principal)
            d = G[cid][nb]
            associates.append({"canonical_id": nb, "label": lab, "masked": mrs,
                               "type": G.nodes[nb].get("type"), "weight": d["weight"],
                               "shared_incidents": sorted(d["incidents"])[:10],
                               "kinds": sorted(d["kinds"])})

    role_mix = Counter(a["role"] for a in apps)
    recent = sum(1 for d in dates if d >= (dates[-1] if dates else "")[:8] + "01") if dates else 0
    return {
        "canonical_id": cid, "type": meta.get("type"), "value": value,
        "masked": mask_reason,
        "aliases": [{"entity_id": a["entity_id"],
                     "value": value if mask_reason is None else masking.mask_name(a["value"])}
                    for a in st["aliases"].get(cid, []) if a["entity_id"] != cid][:8],
        "stats": {"incidents": len(apps), "districts": districts,
                  "first_seen": dates[0] if dates else None,
                  "last_seen": dates[-1] if dates else None,
                  "roles": dict(role_mix)},
        "appearances": apps[:100],
        "associates": associates,
        "timeline": [{"month": m, "count": c} for m, c in sorted(months.items())],
        # transparent activity indicators — deliberately NOT a single "risk score"
        "indicators": {"incident_count": len(apps), "district_span": len(districts),
                       "active_month_max": max(months.values()) if months else 0,
                       "recent_month_incidents": recent},
        "guardrail": "Activity indicators describe recorded involvement only; "
                     "no determination of guilt is made or implied.",
        "viewer": {"role": principal.role, "scope": principal.scope},
    }


# --------------------------------------------------------------------------- #
# case file (+ linked cases with reasons)
# --------------------------------------------------------------------------- #
def case_file(incident_id, principal, max_links=12):
    st = state()
    inc = st["by_inc"].get(incident_id)
    if not inc:
        return {"error": "not_found", "id": incident_id}

    parties = masking.mask_parties(
        store.fetch_incident_parties(incident_id), principal.role, principal.scope,
        crime_type=inc.get("crime_type"), district=inc.get("district_code"),
        station=inc.get("station_code"))

    links = defaultdict(lambda: {"reasons": [], "strength": 0})

    # 1) shared canonical entities (phones/vehicles strongest)
    for cid in st["inc_canon"].get(incident_id, ()):
        typ = st["canon_meta"].get(cid, {}).get("type", "person")
        kind = "shared_phone" if typ == "phone" else (
            "shared_vehicle" if typ == "vehicle" else "shared_person")
        lab, _m = _label(st, cid, principal)
        for oid, _r, _e in st["canon_apps"].get(cid, ()):
            if oid == incident_id:
                continue
            links[oid]["reasons"].append({"type": kind, "detail": f"{typ}: {lab}",
                                          "canonical_id": cid})
            links[oid]["strength"] += _LINK_W[kind]

    # 2) same crime series
    sid = st["series_of"].get(incident_id)
    if sid:
        for oid in st["series_rows"].get(sid, {}).get("incident_ids", []):
            if oid != incident_id:
                links[oid]["reasons"].append({"type": "series", "detail": f"series {sid}"})
                links[oid]["strength"] += _LINK_W["series"]

    # 3) same MO cluster (if Phase-4 MO has been run)
    mo = (inc.get("mo_cluster_id") or "").strip()
    if mo:
        for r in st["incidents"]:
            if r.get("mo_cluster_id") == mo and r["incident_id"] != incident_id:
                links[r["incident_id"]]["reasons"].append({"type": "mo", "detail": f"MO {mo}"})
                links[r["incident_id"]]["strength"] += _LINK_W["mo"]

    # 4) near-repeat: same district+crime within NEAR_KM / NEAR_DAYS
    t0, lat0, lon0 = _parse_dt(inc.get("occurred_at")), _f(inc.get("lat")), _f(inc.get("long"))
    if t0 and lat0 is not None and lon0 is not None:
        for r in st["incidents"]:
            if (r["incident_id"] == incident_id
                    or r.get("district_code") != inc.get("district_code")
                    or r.get("crime_type") != inc.get("crime_type")):
                continue
            t1, la, lo = _parse_dt(r.get("occurred_at")), _f(r.get("lat")), _f(r.get("long"))
            if not t1 or la is None or lo is None or abs((t1 - t0).days) > NEAR_DAYS:
                continue
            km = _haversine_km(lat0, lon0, la, lo)
            if km <= NEAR_KM:
                links[r["incident_id"]]["reasons"].append(
                    {"type": "near_repeat", "detail": f"{km:.1f} km / {abs((t1 - t0).days)} d"})
                links[r["incident_id"]]["strength"] += _LINK_W["near_repeat"]

    ranked = sorted(links.items(), key=lambda kv: -kv[1]["strength"])[:max_links]
    linked = []
    for oid, ln in ranked:
        r = st["by_inc"].get(oid, {})
        # de-dup reasons by (type, detail)
        seen, reasons = set(), []
        for rs in ln["reasons"]:
            key = (rs["type"], rs["detail"])
            if key not in seen:
                seen.add(key)
                reasons.append(rs)
        linked.append({"incident_id": oid, "fir_no": r.get("fir_no"),
                       "crime_type": r.get("crime_type"),
                       "district_code": r.get("district_code"),
                       "occurred_at": r.get("occurred_at"),
                       "strength": ln["strength"], "reasons": reasons[:4]})

    officer = st["officers_by_id"].get(inc.get("officer_id"))
    cs_rows = st["chargesheets_by_inc"].get(incident_id, [])
    chargesheet = cs_rows[0] if cs_rows else None

    timeline = [{"ts": inc.get("occurred_at"), "label": "Incident occurred"}]
    if inc.get("reported_at"):
        timeline.append({"ts": inc.get("reported_at"), "label": "FIR registered"})
    if inc.get("status"):
        timeline.append({"ts": None, "label": "Status: " + inc["status"]})
    if chargesheet:
        cs_label = {"A": "Chargesheet filed", "B": "Closed — false case",
                    "C": "Closed — undetected"}.get(chargesheet.get("cs_type"), "Final report filed")
        timeline.append({"ts": chargesheet.get("cs_date"), "label": cs_label})

    return {"incident": inc, "protected": masking.is_protected(inc.get("crime_type")),
            "parties": parties, "linked_cases": linked, "timeline": timeline,
            "series_id": sid,
            "officer": ({"name": officer.get("name"), "rank": officer.get("rank"),
                        "designation": officer.get("designation")} if officer else None),
            "chargesheet": ({"cs_type": chargesheet.get("cs_type"),
                             "cs_date": chargesheet.get("cs_date")} if chargesheet else None),
            "viewer": {"role": principal.role, "scope": principal.scope}}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# universal search
# --------------------------------------------------------------------------- #
def search(q, principal, per_group=6):
    st = state()
    t0 = time.time()
    qn = (q or "").strip()
    ql = qn.lower()
    out = {"query": qn, "groups": {"cases": [], "people": [], "vehicles": [],
                                   "phones": [], "places": []}, "semantic": []}
    if principal.role == "ethics":
        out["note"] = "ethics role: case/entity search is restricted to audit & fairness views"
        return out
    if len(ql) < 2:
        out["note"] = "type at least 2 characters"
        return out

    plate = re.sub(r"[\s\-]", "", qn.upper())
    digits = re.sub(r"\D", "", qn)

    # cases by FIR no / incident id
    for r in st["incidents"]:
        if len(out["groups"]["cases"]) >= per_group:
            break
        if ql in r.get("fir_no", "").lower() or ql in r.get("incident_id", "").lower():
            out["groups"]["cases"].append(_case_hit(r))

    # entities by value — rank matches by recorded involvement, then cap
    ent_hits = defaultdict(list)
    for cid, meta in st["canon_meta"].items():
        v = meta.get("value", "")
        typ = meta.get("type")
        hit = (typ == "vehicle" and plate and plate in re.sub(r"[\s\-]", "", v.upper())) or \
              (typ == "phone" and len(digits) >= 4 and digits in re.sub(r"\D", "", v)) or \
              (typ == "person" and ql in v.lower())
        if hit:
            ent_hits[typ].append((len(st["canon_apps"].get(cid, ())), cid))
    for typ, grp in (("person", "people"), ("vehicle", "vehicles"), ("phone", "phones")):
        for n_apps, cid in sorted(ent_hits.get(typ, ()), reverse=True)[:per_group]:
            lab, mrs = _label(st, cid, principal)
            apps = st["canon_apps"].get(cid, ())
            out["groups"][grp].append({
                "canonical_id": cid, "value": lab, "masked": mrs, "type": typ,
                "incidents": n_apps,
                "districts": sorted({st["by_inc"].get(i, {}).get("district_code")
                                     for i, _r, _e in apps} - {None, ""})})

    # places (district code or name)
    seen_d = {}
    for r in st["incidents"]:
        d = r.get("district_code", "")
        seen_d[d] = seen_d.get(d, 0) + 1
    for d, n in sorted(seen_d.items(), key=lambda kv: -kv[1]):
        if d and (ql in d.lower()) and len(out["groups"]["places"]) < per_group:
            out["groups"]["places"].append({"code": d, "incidents": n})

    # semantic over narratives (only when structured hits are thin)
    if sum(len(g) for g in out["groups"].values()) < 3:
        index, _refs = st["copilot"]
        for iid, score in index.rank(qn, top_k=per_group):
            r = st["by_inc"].get(iid)
            if r and score > 0.02:
                h = _case_hit(r)
                h["snippet"] = (r.get("mo_text") or "")[:120]
                h["score"] = round(score, 3)
                out["semantic"].append(h)

    out["took_ms"] = int((time.time() - t0) * 1000)
    return out


def _case_hit(r):
    return {"incident_id": r["incident_id"], "fir_no": r.get("fir_no"),
            "crime_type": r.get("crime_type"), "district_code": r.get("district_code"),
            "occurred_at": (r.get("occurred_at") or "")[:10], "status": r.get("status")}
