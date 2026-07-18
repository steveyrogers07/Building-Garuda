"""GARUDA - per-field confidence scoring for an extracted FIR record.

Combines extraction provenance (label vs regex vs missing) with validation against
reference data (date parses, district known, IPC/BNS code in the map, coords present).
The overall score gates the human-in-the-loop queue: low overall => stays for review.
"""
from __future__ import annotations

from datetime import datetime

from shared import refs

_BASE = {"label": 0.90, "llm": 0.85, "regex": 0.80, "derived": 0.72,
         "geocoded": 0.85, "missing": 0.0}
REQUIRED = ["fir_no", "occurred_at", "district_code", "crime_type", "ipc_bns_code"]


def _parses(s):
    try:
        datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return True
    except (ValueError, TypeError):
        return False


def score_confidence(rec, prov):
    code2name, _ = refs.districts()
    codes = refs.known_codes()
    c = {}

    def base(f):
        return _BASE.get(prov.get(f, "missing"), 0.0)

    c["fir_no"] = base("fir_no") if rec.get("fir_no") else 0.0
    c["occurred_at"] = (0.97 if _parses(rec.get("occurred_at")) else 0.40) if rec.get("occurred_at") else 0.0
    c["reported_at"] = 0.90 if _parses(rec.get("reported_at")) else (0.30 if rec.get("reported_at") else 0.0)
    c["district_code"] = 0.97 if rec.get("district_code") in code2name else (0.50 if rec.get("district_code") else 0.0)
    c["station_code"] = base("station_code") if rec.get("station_code") else 0.0
    c["crime_type"] = base("sections") if rec.get("crime_type") else 0.0
    c["ipc_bns_code"] = 0.95 if rec.get("ipc_bns_code") in codes else (0.50 if rec.get("ipc_bns_code") else 0.0)
    has_ll = rec.get("lat") is not None and rec.get("long") is not None
    c["lat"] = c["long"] = 0.90 if has_ll else 0.0
    c["address_text"] = 0.85 if rec.get("address_text") else 0.0
    c["mo_text"] = 0.80 if rec.get("mo_text") else 0.0
    c["status"] = base("status") if rec.get("status") else 0.0
    c["persons"] = 0.85 if rec.get("persons") else 0.0
    c["vehicles"] = 0.90 if rec.get("vehicles") else 0.0
    c["phones"] = 0.90 if rec.get("phones") else 0.0

    c = {k: round(v, 2) for k, v in c.items()}
    c["_overall"] = round(min(c[f] for f in REQUIRED), 2)
    return c
