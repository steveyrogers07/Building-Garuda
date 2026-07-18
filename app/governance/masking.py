"""GARUDA - field-level PII masking (Phase 9 governance).

Protects victim/witness identity per role + jurisdiction, with statutory hard
masking for sexual offences (**IPC 228A**) and child victims (**POCSO**) - those
identities are withheld from everyone except an admin / the assigned case officer,
regardless of jurisdiction. Suspects/accused are never labelled guilty - only
annotated "as recorded, pending investigation/trial."

Masking is applied at the API boundary so raw PII never leaves the brain
unfiltered. PROTECTED_CRIMES is config-driven (the synthetic set has none; the
rule binds the moment real data carries them).
"""
from __future__ import annotations

import re

# IPC 228A (sexual offences) + POCSO (minors): victim identity is statutorily protected.
PROTECTED_CRIMES = {
    "rape", "gang rape", "sexual assault", "aggravated sexual assault",
    "sexual harassment", "outraging modesty of woman", "stalking", "voyeurism",
    "pocso", "child sexual abuse", "assault on woman with intent to outrage modesty",
}
PROTECT_WITNESS = True                       # witness-protection by default
VICTIM_ROLES = {"victim", "complainant"}


def is_protected(crime_type):
    return (crime_type or "").strip().lower() in PROTECTED_CRIMES


def mask_name(v):
    parts = [p for p in re.split(r"\s+", (v or "").strip()) if p]
    return " ".join(p[0].upper() + "." for p in parts) if parts else "[redacted]"


def mask_phone(v):
    s = re.sub(r"\D", "", v or "")
    return ("●●●●●●" + s[-4:]) if len(s) >= 4 else "●●●●"


def can_see_victim(role, scope, district, station, protected):
    """Who may see an un-masked victim/witness identity."""
    if protected:                            # 228A / POCSO - strongest
        return role in ("scrb-admin", "case-officer")
    if role == "scrb-admin":
        return True
    if role == "analyst":                    # analysts see patterns, not identities
        return False
    if role == "district":
        return scope == district
    if role == "station":
        return scope == station
    return False                             # ethics / unknown → masked


def mask_party(party, role, scope, district, station, crime_type):
    """Return a copy of a party row masked for the given principal."""
    out = dict(party)
    prole, typ, val = party.get("role"), party.get("type"), party.get("value")
    protected = is_protected(crime_type)

    if prole in VICTIM_ROLES or (prole == "witness" and PROTECT_WITNESS):
        if not can_see_victim(role, scope, district, station, protected):
            out["value"] = mask_name(val) if typ == "person" else (
                mask_phone(val) if typ == "phone" else "[redacted]")
            out["age"] = None
            out["masked"] = "IPC-228A/POCSO" if protected else "jurisdiction"
    elif prole in ("suspect", "accused"):
        out["note"] = "as recorded in the FIR; pending investigation/trial"
    return out


def mask_parties(parties, role, scope, *, crime_type, district, station):
    return [mask_party(p, role, scope, district, station, crime_type) for p in parties]
