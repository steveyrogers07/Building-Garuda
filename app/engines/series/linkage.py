"""GARUDA crime-series linkage (Phase 5).

Groups incidents into *series* - the same offender(s) hitting again - using MO
similarity plus a space-time near-repeat test (Knox-style). Two incidents link
when they share an MO signal (Phase-4 ``mo_cluster_id``, or crime_type as a
fallback) AND occur within ``max_km`` and ``max_gap_days`` of each other.
Connected components of that link graph become a Crime_Series.

Pure Python + networkx; blocks by (district, MO) so it stays cheap on the full
synthetic set.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime

import networkx as nx

_DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")


def _parse_dt(s):
    s = (s or "").strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _mo_key(inc):
    """Prefer the Phase-4 MO cluster; fall back to crime_type if not resolved."""
    cid = (inc.get("mo_cluster_id") or "").strip()
    return ("mo", cid) if cid else ("ct", (inc.get("crime_type") or "").strip())


def link_series(incidents, max_km=2.5, max_gap_days=21, min_size=3):
    """Return ``{assignments: {incident_id: series_id}, series: [...]}``.

    A series row matches the Crime_Series schema (series_id, crime_type,
    district_code, locality, start/end_date, incident_count, method).
    """
    blocks = defaultdict(list)
    for inc in incidents:
        dt = _parse_dt(inc.get("occurred_at"))
        try:
            lat, lon = float(inc.get("lat")), float(inc.get("long"))
        except (TypeError, ValueError):
            continue
        if dt is None:
            continue
        blocks[(inc.get("district_code", ""), _mo_key(inc))].append({
            "id": inc["incident_id"], "lat": lat, "lon": lon, "dt": dt,
            "crime_type": inc.get("crime_type", ""),
            "address": inc.get("address_text", ""),
        })

    assignments, series, seq = {}, [], 0
    for (district, mokey), items in blocks.items():
        if len(items) < min_size:
            continue
        items.sort(key=lambda x: x["dt"])
        G = nx.Graph()
        G.add_nodes_from(range(len(items)))
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                gap = (items[j]["dt"] - items[i]["dt"]).days
                if gap > max_gap_days:          # sorted by time -> no closer j ahead
                    break
                if _haversine_km(items[i]["lat"], items[i]["lon"],
                                 items[j]["lat"], items[j]["lon"]) <= max_km:
                    G.add_edge(i, j)
        for comp in nx.connected_components(G):
            if len(comp) < min_size:
                continue
            members = sorted((items[k] for k in comp), key=lambda x: x["dt"])
            seq += 1
            sid = f"CS{seq:04d}"
            for m in members:
                assignments[m["id"]] = sid
            crime = Counter(m["crime_type"] for m in members).most_common(1)[0][0]
            series.append({
                "series_id": sid,
                "crime_type": crime,
                "district_code": district,
                "locality": (members[0]["address"] or "")[:80],
                "start_date": members[0]["dt"].strftime("%Y-%m-%d"),
                "end_date": members[-1]["dt"].strftime("%Y-%m-%d"),
                "incident_count": len(members),
                "method": "mo+near-repeat" if mokey[0] == "mo" else "crime_type+near-repeat",
                "incident_ids": [m["id"] for m in members],
            })
    series.sort(key=lambda s: -s["incident_count"])
    return {"assignments": assignments, "series": series}
