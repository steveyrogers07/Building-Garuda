"""GARUDA - promote an extracted FIR to the canonical tables.

Two steps mirroring the human-in-the-loop flow:
  - to_review_record(): build the Review_Queue row (always 'pending' - a human approves).
  - promote_to_canonical(): on approval, map the extracted JSON to canonical
    Incidents + Entities + Incident_Edges rows.

Entity creation here is NAIVE (one new entity per mention); fuzzy/transliteration
resolution that merges aliases into a canonical_id is Phase 4. Until then every entity's
canonical_id == its own entity_id (consistent with the Phase 2 contract).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

# Records with an overall confidence below this still go to review (we never auto-skip
# the human in Phase 3); the flag just lets the UI sort/triage.
REVIEW_FLAG_THRESHOLD = 0.80


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def to_review_record(extraction, confidences, source_fir_url=None, review_id=None):
    overall = float(confidences.get("_overall", 0.0))
    return {
        "review_id": review_id or ("RVW-" + uuid.uuid4().hex[:10]),
        "source_fir_url": source_fir_url or extraction.get("source_fir_url") or "",
        "extracted_json": json.dumps(extraction, ensure_ascii=False),
        "field_confidences": json.dumps(confidences),
        "status": "pending",                         # human-in-the-loop, always
        "reviewer": "",
        "created_at": _now(),
        # convenience (not a Review_Queue column): UI hint
        "_needs_attention": overall < REVIEW_FLAG_THRESHOLD,
    }


def promote_to_canonical(extraction, incident_id=None, confidence=None):
    iid = incident_id or ("INC-" + uuid.uuid4().hex[:8])
    incident = {
        "incident_id": iid,
        "fir_no": extraction.get("fir_no") or "",
        "occurred_at": extraction.get("occurred_at") or "",
        "reported_at": extraction.get("reported_at") or "",
        "district_code": extraction.get("district_code") or "",
        "station_code": extraction.get("station_code") or "",
        "crime_type": extraction.get("crime_type") or "",
        "ipc_bns_code": extraction.get("ipc_bns_code") or "",
        "lat": extraction.get("lat") if extraction.get("lat") is not None else "",
        "long": extraction.get("long") if extraction.get("long") is not None else "",
        "address_text": extraction.get("address_text") or "",
        "mo_text": extraction.get("mo_text") or "",
        "status": extraction.get("status") or "Under Investigation",
        "mo_cluster_id": "",                          # Phase 4
        "series_id": "",                              # Phase 5
        "source_fir_url": extraction.get("source_fir_url") or "",
        "confidence": confidence if confidence is not None else "",
        "created_by": extraction.get("created_by") or "ingestion",
    }
    entities, edges = [], []

    def add(value, etype, role):
        eid = "ENT-" + uuid.uuid4().hex[:8]
        return eid, value, etype, role

    def emit(value, etype, role, age="", gender=""):
        eid = "ENT-" + uuid.uuid4().hex[:8]
        entities.append({"entity_id": eid, "canonical_id": eid, "type": etype,
                         "value": value, "alias_of": "", "age": age if age else "",
                         "gender": gender or "", "match_confidence": ""})
        edges.append({"incident_id": iid, "entity_id": eid, "role": role,
                      "edge_weight": "", "evidence_type": "fir_named"})

    for p in extraction.get("persons", []):
        emit(p["value"], "person", p.get("role", "suspect"), p.get("age"), p.get("gender"))
    for v in extraction.get("vehicles", []):
        emit(v, "vehicle", "vehicle_used")
    for ph in extraction.get("phones", []):
        emit(ph, "phone", "phone_used")

    return {"Incidents": [incident], "Entities": entities, "Incident_Edges": edges}
