"""GARUDA copilot - hybrid answer with mandatory citations + guardrails (Phase 7).

Pipeline: NL -> structured filters (nl2query) -> ZCQL over Incidents (executed
locally as row filtering) -> semantic rerank (retriever) -> extractive, templated
answer that ALWAYS cites the source FIRs. Guardrail: surfaces records, never
asserts guilt; refuses guilt-determination and out-of-scope queries. An opt-in
Qwen (QuickML) step can replace the templated prose; citations stay mandatory.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from . import nl2query as nlq
from .retriever import NarrativeIndex

GUARDRAIL = ("This system surfaces FIR records matching the query; it does not "
             "determine guilt. Persons named are as recorded in the FIR, pending "
             "investigation/trial.")
_STRUCT_KEYS = ("district_code", "crime_type", "date_from", "date_to",
                "hour_from", "vehicle", "phone")
OOS_THRESHOLD = 0.04        # min top semantic score for an unfiltered query to answer
_NARRATIVE_COLS = ("incident_id", "fir_no", "occurred_at", "district_code",
                   "crime_type", "ipc_bns_code", "mo_text", "source_fir_url")


def prepare(incidents, socio=None):
    """Build the retrieval index + reference maps once (cache me)."""
    ids = [r["incident_id"] for r in incidents]
    texts = [" ".join(str(r.get(c, "")) for c in ("crime_type", "mo_text", "address_text"))
             for r in incidents]
    index = NarrativeIndex(ids, texts)
    districts = {}
    for s in (socio or []):
        name, code = (s.get("district_name") or "").strip().lower(), s.get("area_code")
        if name and code:
            districts[name] = code
    for r in incidents:                      # always allow the raw codes too
        dc = r.get("district_code")
        if dc:
            districts.setdefault(dc.lower(), dc)
    crime_types = sorted({r.get("crime_type", "") for r in incidents if r.get("crime_type")})
    data_max = max((str(r.get("occurred_at", ""))[:10] for r in incidents), default=None)
    refs = {"districts": districts, "crime_types": crime_types, "data_max": data_max}
    return index, refs


def _hour(ts):
    m = re.search(r"\b(\d{1,2}):\d{2}", str(ts or ""))
    return int(m.group(1)) if m else None


def _in_hours(h, a, b):
    if a is None:
        return h <= b
    if b is None:
        return h >= a
    return (a <= h <= b) if a <= b else (h >= a or h <= b)   # wrap past midnight


def _apply_filters(rows, f):
    out = []
    for r in rows:
        if f.get("district_code") and r.get("district_code") != f["district_code"]:
            continue
        if f.get("crime_type") and r.get("crime_type") != f["crime_type"]:
            continue
        oc = str(r.get("occurred_at", ""))[:10]
        if f.get("date_from") and (not oc or oc < f["date_from"]):
            continue
        if f.get("date_to") and (not oc or oc > f["date_to"]):
            continue
        if f.get("hour_from") is not None or f.get("hour_to") is not None:
            h = _hour(r.get("occurred_at"))
            if h is None or not _in_hours(h, f.get("hour_from"), f.get("hour_to")):
                continue
        narr = (r.get("mo_text", "") + " " + r.get("address_text", "")).upper()
        if f.get("vehicle") and f["vehicle"] not in re.sub(r"[\s-]", "", narr):
            continue
        if f.get("phone") and f["phone"] not in narr:
            continue
        out.append(r)
    return out


def _cite(r, score=None):
    c = {k: r.get(k) for k in ("incident_id", "fir_no", "district_code", "crime_type",
                               "occurred_at", "ipc_bns_code", "source_fir_url")}
    c["snippet"] = (r.get("mo_text") or "")[:160]
    if score is not None:
        c["score"] = round(score, 4)
    return c


def _compose(f, n_hits, cites):
    desc = [f.get("crime_type", "incidents").lower()]
    if f.get("district_code"):
        desc.append("in " + f["district_code"])
    if f.get("date_from") or f.get("date_to"):
        desc.append("between %s and %s" % (f.get("date_from", "?"), f.get("date_to", "?")))
    if f.get("hour_from") is not None or f.get("hour_to") is not None:
        desc.append("during %02d:00-%02d:00" % (f.get("hour_from", 0), f.get("hour_to", 23)))
    head = "Found %d FIR record(s) matching %s." % (n_hits, " ".join(desc))
    lines = ["FIR %s (%s, %s, %s) [%s]: %s" % (
        c["fir_no"], c["crime_type"], c["district_code"], str(c["occurred_at"])[:10],
        c["incident_id"], c["snippet"]) for c in cites[:5]]
    return head + " Top records:\n- " + "\n- ".join(lines)


def answer(query, incidents, index, refs, top_k=10):
    f = nlq.parse_query(query, refs["districts"], refs["crime_types"], refs.get("data_max"))

    if f.get("guilt_query"):
        return {"refused": True, "reason": "guilt_determination", "answer": GUARDRAIL,
                "filters": f, "citations": [], "count": 0, "guardrail": GUARDRAIL}

    has_struct = any(k in f for k in _STRUCT_KEYS)
    hits = _apply_filters(incidents, f) if has_struct else incidents
    cand_ids = [r["incident_id"] for r in hits] if has_struct else None
    ranked = index.rank(query, candidate_ids=cand_ids, top_k=top_k)

    by_id = {r["incident_id"]: r for r in incidents}
    cites = [_cite(by_id[i], s) for i, s in ranked if i in by_id]

    if not cites:
        return {"refused": True, "reason": "no_match", "filters": f, "count": 0,
                "citations": [], "answer": "No FIR records match that query. " + GUARDRAIL,
                "guardrail": GUARDRAIL, "zcql": nlq.to_zcql(f)}

    # out-of-scope: no structured anchor AND the best semantic match is weak
    if not has_struct and cites[0].get("score", 0.0) < OOS_THRESHOLD:
        return {"refused": True, "reason": "out_of_scope", "filters": f, "count": 0,
                "citations": [], "guardrail": GUARDRAIL,
                "answer": "That question doesn't map to the FIR records. " + GUARDRAIL}

    return {"refused": False, "answer": _compose(f, len(hits), cites),
            "filters": f, "zcql": nlq.to_zcql(f), "count": len(hits),
            "citations": cites, "guardrail": GUARDRAIL}


def audit_entry(query, result, actor="demo", role="analyst", ip=""):
    """One Audit_Log row per query (schema: log_id, actor, role, action, resource, ...)."""
    ids = ",".join(c["incident_id"] for c in result.get("citations", [])[:50])
    action = "copilot.refuse" if result.get("refused") else "copilot.query"
    return {"log_id": "AUD-" + uuid.uuid4().hex[:12], "actor": actor, "role": role,
            "action": action, "resource": "Incidents", "query_text": query,
            "ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "ip": ip,
            "returned_ids": ids}
