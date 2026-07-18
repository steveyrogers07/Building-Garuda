"""GARUDA - geocoder. Resolves an FIR place/address to lat/long via the gazetteer
(exact, then fuzzy via stdlib difflib), falling back to the district centroid.

Returns (lat, long, confidence, method). Used by the ingestion /extract step and by
later phases. Gazetteer comes from refs (repo data locally; Data Store in prod).
"""
from __future__ import annotations

import difflib

from shared import refs


def _index():
    rows = refs.gazetteer()
    by_place = {r["place"].lower(): r for r in rows}
    return rows, by_place


def geocode(place, district_code=None):
    rows, by_place = _index()
    key = (place or "").strip().lower()

    if key and key in by_place:
        r = by_place[key]
        return float(r["lat"]), float(r["long"]), 0.95, "exact"

    if key:
        match = difflib.get_close_matches(key, list(by_place.keys()), n=1, cutoff=0.85)
        if match:
            r = by_place[match[0]]
            return float(r["lat"]), float(r["long"]), 0.85, "fuzzy"

    if district_code:
        for r in rows:
            if r["district_code"] == district_code and r["level"] == "district":
                return float(r["lat"]), float(r["long"]), 0.40, "district_centroid"

    return None, None, 0.0, "none"
