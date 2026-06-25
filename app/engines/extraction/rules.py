"""GARUDA — rule-based FIR field extractor (default extractor; no LLM/credits).

Parses OCR'd FIR text into the schema in ingestion/extraction/fir_schema.json.
Works great on the structured synthetic FIRs and is the dev/offline fallback for the
Qwen path (app/engines/extraction/qwen.py, used on messy/handwritten real FIRs).

Returns (record, provenance) where provenance[field] in {label, regex, derived, missing}.
"""
from __future__ import annotations

import re

from shared import refs

VEH_RE = re.compile(r"\bKA\d{2}[A-Z]{1,3}\d{3,4}\b")
PHONE_RE = re.compile(r"\+?91?[6-9]\d{9}\b")
DT_RE = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?")
SECT_RE = re.compile(r"section\s+([0-9]+(?:\([0-9A-Za-z]+\))?[A-Z]?)", re.I)
NUM_RE = re.compile(r"-?\d+\.\d+")

# field -> normalised label fragments to look for (left-of-colon)
LABELS = {
    "fir_no": ["fir no"],
    "district": ["district"],
    "station_code": ["police stn", "police station"],
    "reported_at": ["reported on", "information received", "reported"],
    "sections": ["acts sections", "sections", "u s"],
    "occurred_at": ["occurrence date time", "occurrence date", "occurrence"],
    "address_text": ["place of offence", "place", "location"],
    "gps": ["approx gps", "gps"],
    "complainant": ["complainant", "informant"],
    "accused": ["accused"],
    "vehicles": ["property vehicle", "vehicle", "property"],
    "phones": ["contact number", "phone", "mobile"],
    "mo_text": ["brief facts mo", "brief facts", "facts", "modus"],
    "created_by": ["investigating off", "investigating officer"],
    "status": ["status"],
}


def _norm(s):
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def _scan(text):
    found = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        nl, right = _norm(left), right.strip()
        for field, keys in LABELS.items():
            if field in found:
                continue
            if any(k in nl for k in keys):
                found[field] = right
                break
    return found


def extract_fir(text):
    raw = _scan(text)
    rec, prov = {}, {}

    def setf(field, value, source="label"):
        rec[field] = value
        prov[field] = source if value not in (None, "", []) else "missing"

    setf("fir_no", raw.get("fir_no"))
    setf("station_code", raw.get("station_code"))
    setf("status", raw.get("status"))
    setf("mo_text", raw.get("mo_text"))
    setf("address_text", raw.get("address_text"))

    # district -> code (from parentheses, else map the name)
    dval = raw.get("district", "")
    m = re.search(r"\(([A-Za-z]+)\)", dval)
    if m:
        setf("district_code", m.group(1))
    elif dval:
        _, name2code = refs.districts()
        setf("district_code", name2code.get(dval.split("(")[0].strip().lower()), "derived")
    else:
        setf("district_code", None)

    # sections -> ipc_bns_code + crime_type
    sval = raw.get("sections", "")
    sm = SECT_RE.search(sval)
    setf("ipc_bns_code", sm.group(1) if sm else None)
    cm = re.search(r"\(([^)]+)\)\s*$", sval)
    if cm:
        setf("crime_type", cm.group(1).strip())
    elif " - " in sval:
        setf("crime_type", sval.split(" - ", 1)[1].strip(), "derived")
    else:
        setf("crime_type", None)

    # datetimes
    for f in ("occurred_at", "reported_at"):
        dm = DT_RE.search(raw.get(f, "") or "")
        setf(f, dm.group(0).replace("T", " ") if dm else None)

    # gps
    gm = NUM_RE.findall(raw.get("gps", "") or "")
    if len(gm) >= 2:
        rec["lat"], rec["long"] = float(gm[0]), float(gm[1])
        prov["lat"] = prov["long"] = "label"
    else:
        rec["lat"] = rec["long"] = None
        prov["lat"] = prov["long"] = "missing"

    # persons
    persons = []
    comp = raw.get("complainant", "")
    if comp and "suo motu" not in comp.lower() and "state" not in comp.lower():
        am = re.search(r"age\s*(\d+)", comp, re.I)
        gm2 = re.search(r",\s*([MF])\b", comp)
        persons.append({"value": comp.split(",")[0].strip(),
                        "role": "victim",
                        "age": int(am.group(1)) if am else None,
                        "gender": gm2.group(1) if gm2 else None})
    for a in (raw.get("accused", "") or "").split(";"):
        a = a.strip()
        if a and a.lower() != "unknown":
            persons.append({"value": a, "role": "suspect", "age": None, "gender": None})
    rec["persons"] = persons
    prov["persons"] = "label" if persons else "missing"

    # vehicles / phones: label values, augmented by regex over the whole text
    def listfield(field, regex):
        labelled = [x.strip() for x in (raw.get(field, "") or "").split(";")
                    if x.strip() and x.strip().lower() != "nil"]
        regexed = regex.findall(text)
        merged = list(dict.fromkeys(labelled + regexed))
        rec[field] = merged
        prov[field] = "label" if labelled else ("regex" if merged else "missing")

    listfield("vehicles", VEH_RE)
    listfield("phones", PHONE_RE)
    rec["created_by"] = raw.get("created_by")  # not part of schema; kept for promote
    return rec, prov
