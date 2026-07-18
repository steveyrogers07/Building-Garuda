"""GARUDA - structured MO feature extraction (Phase 4).

Turns an incident into interpretable modus-operandi features that complement the free-text
mo_text embedding: time-of-day bucket, crime type, and weapon / vehicle / entry-method /
target signals mined from the narrative. Pure-Python; reused by the cluster signatures so a
cluster can be described ("night, two-wheeler, gold chain") not just numbered.
"""
from __future__ import annotations

from datetime import datetime

HOUR_BUCKETS = ["night", "morning", "afternoon", "evening"]

# narrative cues -> structured flags (mo_text is lowercased before matching)
WEAPON_CUES = ["knife", "machete", "club", "weapon", "pistol", "sharp", "arm"]
VEHICLE_CUES = ["motorcycle", "two-wheeler", "scooter", "bike", "activa", "pulsar",
                "splendor", "jupiter", "enfield", "vehicle", "swift", "i20", "fz"]
ENTRY_CUES = ["lock broken", "rear door", "ignition tampered", "tampered",
              "entry via", "broke", "unlawfully entered", "trespass"]
TARGET_CUES = {
    "target_jewellery": ["gold chain", "jewellery", "chain"],
    "target_mobile": ["mobile", "phone", "otp"],
    "target_cash": ["cash", "rs.", "looted", "amount"],
    "target_vehicle": ["two-wheeler", "motorcycle", "vehicle", "decamped"],
}


def hour_bucket(occurred_at: str) -> str:
    """Map a timestamp to one of four diurnal buckets (mirrors the generator)."""
    try:
        h = datetime.strptime(occurred_at[:19], "%Y-%m-%d %H:%M:%S").hour
    except (ValueError, TypeError):
        return "unknown"
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 21:
        return "evening"
    return "night"


def structured_features(incident: dict) -> dict:
    """Interpretable MO features for one incident (dict-shaped, JSON-able)."""
    mo = (incident.get("mo_text") or "").lower()
    feats = {
        "crime_type": incident.get("crime_type") or "",
        "hour_bucket": hour_bucket(incident.get("occurred_at") or ""),
        "weapon": int(any(c in mo for c in WEAPON_CUES)),
        "vehicle": int(any(c in mo for c in VEHICLE_CUES)),
        "entry": int(any(c in mo for c in ENTRY_CUES)),
    }
    for name, cues in TARGET_CUES.items():
        feats[name] = int(any(c in mo for c in cues))
    return feats
