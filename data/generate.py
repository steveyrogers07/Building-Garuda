#!/usr/bin/env python3
"""GARUDA — synthetic Karnataka crime dataset generator (Phase 2).

Emits the *canonical* contract (see schema/canonical_schema.yaml) as CSVs plus a
ground_truth.json of the planted patterns used to score later phases:

    data/synthetic/incidents.csv
    data/synthetic/entities.csv
    data/synthetic/incident_edges.csv
    data/synthetic/officers.csv
    data/synthetic/chargesheets.csv
    data/synthetic/arrests.csv
    data/synthetic/case_sections.csv
    data/synthetic/courts.csv
    data/synthetic/case_status.csv
    data/synthetic/crime_head_sections.csv
    data/synthetic/ground_truth.json

Everything is driven by data/generator_config.yaml and a fixed seed, so the output
(and therefore ground_truth.json) is reproducible. Planted patterns:
  1. organised network  — chain-snatchings across >=3 districts sharing one phone +
                          one vehicle + near-identical MO, with a "kingpin".
  2. near-repeat series — burglaries clustered in one locality within ~2 weeks.
  3. anomaly spikes     — a crime type injected 3-4x its baseline in a district-month.

Usage:
    python data/generate.py
    python data/generate.py --n-incidents 15000 --out data/synthetic
"""
from __future__ import annotations

import argparse
import json
import math
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from faker import Faker

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "generator_config.yaml"
DEFAULT_OUT = HERE / "synthetic"

fake = Faker("en_IN")

# A few Kannada renderings of common name parts -> guarantees Unicode in the data
# (exercises the encoding check in the validation gate).
KANNADA = {
    "Ravi": "ರವಿ", "Kumar": "ಕುಮಾರ್", "Suresh": "ಸುರೇಶ್", "Manju": "ಮಂಜು",
    "Raju": "ರಾಜು", "Shiva": "ಶಿವ", "Anil": "ಅನಿಲ್", "Prakash": "ಪ್ರಕಾಶ್",
    "Mahesh": "ಮಹೇಶ್", "Lakshmi": "ಲಕ್ಷ್ಮಿ", "Devi": "ದೇವಿ", "Gowda": "ಗೌಡ",
    "Reddy": "ರೆಡ್ಡಿ", "Naik": "ನಾಯ್ಕ", "Nagaraj": "ನಾಗರಾಜ್", "Basavaraj": "ಬಸವರಾಜ್",
}

LOCALITIES = ["Market", "Bus Stand", "1st Main", "5th Cross", "Layout", "Circle",
              "Temple Street", "Railway Station Road", "College Road",
              "Industrial Area", "Market Yard", "New Extension"]
VEHICLES = ["Honda Activa", "TVS Jupiter", "Bajaj Pulsar", "Hero Splendor",
            "Royal Enfield", "Maruti Swift", "Hyundai i20", "Yamaha FZ"]
ITEMS = ["gold chain", "mobile phone", "cash", "two-wheeler", "laptop", "jewellery"]
WEAPONS = ["knife", "machete", "wooden club", "sharp weapon", "country-made pistol"]

MO_TEMPLATES = {
    "Two-wheeler theft": [
        "Accused decamped with a {veh} parked near {place} during {tod} hours.",
        "{veh} stolen from {place}; ignition tampered. CCTV footage under review.",
    ],
    "Theft": [
        "{item} stolen from {place} during {tod} hours.",
        "Theft reported near {place}; {item} found missing by the complainant.",
    ],
    "House burglary": [
        "House lock broken at {place} during {tod}; {item} and {amount} reported missing.",
        "Burglary at a residence near {place}; entry via rear door, {amount} stolen.",
    ],
    "Chain snatching": [
        "Two persons on a motorcycle snatched a {item} from the complainant near {place} and fled.",
        "Miscreants snatched a gold chain near {place} during {tod} and sped away on a two-wheeler.",
    ],
    "Assault": [
        "Complainant assaulted following an altercation near {place} during {tod}.",
        "Group assault reported near {place}; complainant sustained injuries.",
    ],
    "Cheating": [
        "Complainant cheated of {amount} on a false promise near {place}.",
        "Fraudulent transaction of {amount} reported by the complainant.",
    ],
    "Robbery": [
        "Complainant robbed of {item} at {weapon}-point near {place} during {tod}.",
        "Armed robbery near {place}; {amount} looted by the accused.",
    ],
    "Motor vehicle theft": [
        "A {veh} was stolen from {place} during {tod} hours.",
        "Vehicle theft reported at {place}; no eyewitness available.",
    ],
    "Cybercrime": [
        "Complainant defrauded of {amount} via an online scam call.",
        "OTP fraud; {amount} debited from the complainant's bank account.",
    ],
    "Grievous hurt": [
        "Victim grievously injured with a {weapon} near {place} during {tod}.",
        "Assault with a {weapon} near {place}; victim hospitalised.",
    ],
    "Criminal breach of trust": [
        "Entrusted {amount} misappropriated by the accused.",
        "Breach of trust involving {amount} reported near {place}.",
    ],
    "Rioting": [
        "Unlawful assembly near {place} turned violent during {tod}.",
        "Group clash near {place}; public property damaged.",
    ],
    "Criminal trespass": [
        "Accused unlawfully entered the premises at {place} during {tod}.",
        "Criminal trespass into a property near {place}.",
    ],
    "Dacoity": [
        "Armed gang looted {amount} at {place} during {tod}.",
        "Dacoity by five or more persons near {place}; {weapon} used.",
    ],
    "Murder": [
        "Body recovered near {place}; investigation underway.",
        "Homicide reported near {place} during {tod} hours.",
    ],
    "Kidnapping": [
        "A person reported kidnapped from {place} during {tod}.",
        "Kidnapping for ransom reported near {place}.",
    ],
}
PLANTED_SNATCH_MO = ("Two helmeted persons on a black motorcycle snatched a gold "
                     "chain near {place} during night hours and fled towards the highway.")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def weighted_choice(rng, items, weights):
    w = np.asarray(weights, dtype=float)
    return items[int(rng.choice(len(items), p=w / w.sum()))]


def hour_weights(night=True):
    if night:
        w = np.array([7, 6, 5, 4, 3, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 5, 6, 7, 8, 9, 9, 9, 8, 7], float)
    else:
        w = np.array([1, 1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 8, 8, 8, 7, 7, 6, 5, 4, 3, 2, 2, 1, 1], float)
    return w / w.sum()


def tod_word(hour):
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def ka_reg(rng):
    L = string.ascii_uppercase
    return f"KA{rng.integers(1, 71):02d}{rng.choice(list(L))}{rng.choice(list(L))}{rng.integers(0, 10000):04d}"


def phone_no(rng):
    return "+91" + str(rng.integers(6, 10)) + "".join(str(d) for d in rng.integers(0, 10, 9))


def name_variant(name, rng):
    """Produce an alias/transliteration variant of a person name."""
    parts = name.replace(".", "").split()
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    choice = rng.integers(0, 5)
    if choice == 0 and first in KANNADA:                 # Kannada script variant
        return KANNADA[first] + ((" " + KANNADA.get(last, last)) if last else "")
    if choice == 1 and last:                              # initialise the first name
        return f"{first[0]}. {last}"
    if choice == 2:                                       # trailing-a transliteration
        return (first + "a" if not first.endswith("a") else first[:-1]) + ((" " + last) if last else "")
    if choice == 3:                                       # phonetic swaps
        v = first.replace("ph", "f").replace("v", "w").replace("sh", "s")
        return v + ((" " + last) if last else "")
    return f"{first} {last}".strip() + " @"               # stray token / typo


def make_mo(crime_type, rng, district_name):
    place = f"{rng.choice(LOCALITIES)}, {district_name}"
    tmpl = rng.choice(MO_TEMPLATES.get(crime_type, ["Incident reported near {place} during {tod} hours."]))
    return tmpl.format(
        place=place,
        tod=tod_word(int(rng.integers(0, 24))),
        veh=rng.choice(VEHICLES),
        item=rng.choice(ITEMS),
        amount=f"Rs.{rng.choice([5, 10, 15, 20, 25, 40, 50, 75, 100])}000",
        weapon=rng.choice(WEAPONS),
    ), place


# --------------------------------------------------------------------------- #
# main generation
# --------------------------------------------------------------------------- #
def generate(cfg, out_dir):
    seed = int(cfg["seed"])
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)
    rng = np.random.default_rng(seed)

    districts = cfg["districts"]
    dcode = {d["code"]: d for d in districts}
    dweights = np.array([d["weight"] for d in districts], float)
    crime_types = cfg["crime_types"]
    cweights = np.array([c["weight"] for c in crime_types], float)
    crime_by_name = {c["name"]: c for c in crime_types}
    day_crimes = set(cfg.get("day_crimes", []))
    bns_ratio = float(cfg["bns_ratio"])
    status_items = list(cfg["status_weights"].keys())
    status_w = np.array(list(cfg["status_weights"].values()), float)

    # stations per district (more in busier districts)
    stations = {}
    for d in districts:
        n = max(3, round(d["weight"]))
        stations[d["code"]] = [f"{d['code']}{i:02d}" for i in range(1, n + 1)]

    # Isolated RNG stream for the new organizer-schema fields (officer roster,
    # case_category, chargesheets). Drawing these from the shared rng/random/fake
    # streams would shift every subsequent draw downstream — including entity names,
    # planted-scenario identities (kingpin, shared phone/vehicle) and incident_ids —
    # breaking ground_truth.json reproducibility and every test that hardcodes them.
    # Keep them on a separate, independently-seeded stream instead.
    rng2 = np.random.default_rng(seed + 990011)
    random2 = random.Random(seed + 990011)
    fake2 = Faker("en_IN")
    fake2.seed_instance(seed + 990011)

    # A THIRD isolated stream (see the rng2 note above) for the P2 schema-completeness
    # fields: officer bio fields, incident extra dates, victim-police, and the two
    # reference tables' court/status assignment. Same reasoning — these must never
    # perturb rng2 (which case_category/officer_id/chargesheets already consume in a
    # specific order) or rng_sec/rng_arr.
    rng3 = np.random.default_rng(seed + 770088)

    # ---- Employee roster (organizer schema: Rank/Designation/District posting) ----
    off_cfg = cfg["officers"]
    off_rank_names = [r["name"] for r in off_cfg["ranks"]]
    off_rank_w = np.array([r["weight"] for r in off_cfg["ranks"]], float)
    bg_names = [b["name"] for b in off_cfg["blood_groups"]]
    bg_w = np.array([b["weight"] for b in off_cfg["blood_groups"]], float)
    svc_lo, svc_hi = off_cfg["years_of_service"]
    age_lo, age_hi = off_cfg["age_at_appointment"]
    ds_start = pd.to_datetime(cfg["dates"]["start"])
    officers, officers_by_district = [], {d["code"]: [] for d in districts}
    for i in range(int(off_cfg["n_officers"])):
        oid = f"OFF{i + 1:04d}"
        dc = str(weighted_choice(rng2, [d["code"] for d in districts], dweights))
        years_svc = int(rng3.integers(svc_lo, svc_hi + 1))
        appointment = (ds_start - pd.DateOffset(years=years_svc)).to_pydatetime()
        dob = appointment - timedelta(days=365 * int(rng3.integers(age_lo, age_hi + 1)))
        officers.append(dict(
            officer_id=oid, name=fake2.name(),
            rank=str(weighted_choice(rng2, off_rank_names, off_rank_w)),
            designation=str(rng2.choice(off_cfg["designations"])),
            district_code=dc, unit_code=random2.choice(stations[dc]),
            kgid=f"KGID{int(rng3.integers(10_000_000, 99_999_999))}",
            dob=dob.strftime("%Y-%m-%d"),
            blood_group=str(weighted_choice(rng3, bg_names, bg_w)),
            appointment_date=appointment.strftime("%Y-%m-%d")))
        officers_by_district[dc].append(oid)

    cc_items = [c["code"] for c in cfg["case_categories"]]
    cc_w = np.array([c["weight"] for c in cfg["case_categories"]], float)
    heinous_crimes = set(cfg.get("heinous_crimes", []))

    # ---- Court (organizer: Court) — 3 per district, matching Arrests' existing
    # CRT-{district}-{01..03} id scheme so arrests.csv needs no regeneration to gain
    # valid foreign keys. Pure reference data — no per-row RNG.
    court_cfg = cfg["courts"]
    courts, courts_by_district = [], {}
    for d in districts:
        dc = d["code"]
        courts_by_district[dc] = []
        for i, cname in enumerate(court_cfg["names"][: int(court_cfg["per_district"])], start=1):
            cid = f"CRT-{dc}-{i:02d}"
            courts.append(dict(court_id=cid, name=f"{cname}, {d['name']}",
                               district_code=dc, state_code="KA"))
            courts_by_district[dc].append(cid)
    court_eligible = set(court_cfg["eligible_statuses"])

    # ---- CaseStatusMaster (organizer: CaseStatusMaster) — reference-only, straight
    # from status_weights' keys; Incidents.status stays denormalized text (no engine
    # touches this table, it exists so the master/lookup layer is schema-complete).
    case_status_rows = [dict(status_code=s.replace(" ", "_").upper(), status_name=s)
                        for s in status_items]

    # ---- CrimeHeadActSection (organizer: CrimeHeadActSection) — the 2-level crime
    # classification's act+section reference, derived from crime_types' primary code
    # + case_sections.companions below. No incident-level data; built once at the end
    # once case_sections' companion config is in scope (see the write section).

    # ---- date sampling distribution with weekend / month-end / festival skew ----
    start = pd.to_datetime(cfg["dates"]["start"])
    end = pd.to_datetime(cfg["dates"]["end"])
    days = pd.date_range(start, end, freq="D")
    dw = np.ones(len(days))
    we_boost = cfg["dates"]["weekend_boost"]
    me_boost = cfg["dates"]["month_end_boost"]
    for i, d in enumerate(days):
        if d.weekday() >= 4:
            dw[i] *= we_boost
        last_day = (d + pd.offsets.MonthEnd(0)).day
        if d.day > last_day - 3:
            dw[i] *= me_boost
    for fest in cfg["dates"]["festivals"]:
        fd = pd.to_datetime(fest["date"])
        for i, d in enumerate(days):
            if abs((d - fd).days) <= fest["window_days"]:
                dw[i] *= fest["boost"]
    dw = dw / dw.sum()
    hw_night, hw_day = hour_weights(True), hour_weights(False)

    def sample_dt(crime_name, day_idx=None):
        if day_idx is None:
            day_idx = int(rng.choice(len(days), p=dw))
        d = days[day_idx]
        hw = hw_day if crime_name in day_crimes else hw_night
        hour = int(rng.choice(24, p=hw))
        return datetime(d.year, d.month, d.day, hour, int(rng.integers(0, 60)), int(rng.integers(0, 60)))

    # ---- entity pool ----
    entities = []       # dict rows
    person_idx = []     # (entity_id, weight) for suspect sampling
    eid = 0

    def new_eid():
        nonlocal eid
        eid += 1
        return f"ENT{eid:06d}"

    active_frac = float(cfg["counts"]["active_offender_fraction"])
    n_person = int(cfg["counts"]["persons_canonical"])
    alias_frac = float(cfg["counts"]["alias_fraction"])
    max_alias = int(cfg["counts"]["max_aliases"])

    for _ in range(n_person):
        name = fake.name()
        pid = new_eid()
        gender = "M" if rng.random() < 0.78 else "F"
        is_active = rng.random() < active_frac
        entities.append(dict(entity_id=pid, canonical_id=pid, type="person", value=name,
                             alias_of="", age=int(rng.integers(18, 71)), gender=gender,
                             match_confidence=""))
        person_idx.append((pid, 5.0 if is_active else 1.0))
        # aliases for some persons (the entity-resolution challenge)
        if rng.random() < alias_frac:
            for _ in range(int(rng.integers(1, max_alias + 1))):
                aid = new_eid()
                entities.append(dict(entity_id=aid, canonical_id=pid, type="person",
                                     value=name_variant(name, rng), alias_of=pid,
                                     age="", gender=gender,
                                     match_confidence=round(float(rng.uniform(0.70, 0.95)), 2)))
                person_idx.append((aid, 0.6))

    veh_ids = [new_eid() for _ in range(int(cfg["counts"]["vehicles"]))]
    for vid in veh_ids:
        entities.append(dict(entity_id=vid, canonical_id=vid, type="vehicle",
                             value=ka_reg(rng), alias_of="", age="", gender="", match_confidence=""))
    phone_ids = [new_eid() for _ in range(int(cfg["counts"]["phones"]))]
    for pid in phone_ids:
        entities.append(dict(entity_id=pid, canonical_id=pid, type="phone",
                             value=phone_no(rng), alias_of="", age="", gender="", match_confidence=""))

    p_ids = np.array([p[0] for p in person_idx])
    p_w = np.array([p[1] for p in person_idx], float)
    p_w = p_w / p_w.sum()

    incidents, edges = [], []
    inc_n = 0

    def new_incident_id():
        nonlocal inc_n
        inc_n += 1
        return f"INC{inc_n:06d}"

    fir_seq = {}

    # CaseMaster.IncidentToDate/InfoReceivedPSDate + Court (P2 #8/#11) — all rng3,
    # all appended after the fields that already exist, so nothing already-generated
    # (rng/rng2 consumption order) shifts.
    incx_cfg = cfg["incident_extra"]
    ithd_lo, ithd_hi = incx_cfg["incident_to_date_hours"]
    infolag_lo, infolag_hi = incx_cfg["info_received_lag_hours"]
    p_victim_police = float(incx_cfg["p_victim_is_police"])

    def make_incident(district_code, crime_name, when, lat=None, long=None, mo=None):
        d = dcode[district_code]
        st = random.choice(stations[district_code])
        iid = new_incident_id()
        yr = when.year
        fir_seq[st] = fir_seq.get(st, 0) + 1
        crime = crime_by_name[crime_name]
        code = crime["bns"] if rng.random() < bns_ratio else crime["ipc"]
        if lat is None:
            lat = round(d["lat"] + float(rng.normal(0, 0.06)), 6)
            long = round(d["long"] + float(rng.normal(0, 0.06)), 6)
        if mo is None:
            mo, addr = make_mo(crime_name, rng, d["name"])
        else:
            addr = f"{rng.choice(LOCALITIES)}, {d['name']}"
        reported = when + timedelta(hours=round(float(rng.uniform(0.5, 72)), 1))
        officer_pool = officers_by_district.get(district_code) or [o["officer_id"] for o in officers]
        officer_id = str(random2.choice(officer_pool))
        status_val = str(weighted_choice(rng, status_items, status_w))

        incident_to = when + timedelta(hours=float(rng3.uniform(ithd_lo, ithd_hi)))
        gap_hours = max((reported - when).total_seconds() / 3600, 0.0)
        info_received = when + timedelta(hours=min(float(rng3.uniform(infolag_lo, infolag_hi)), gap_hours))
        court_pool = courts_by_district.get(district_code) or [c["court_id"] for c in courts]
        court_id = str(rng3.choice(court_pool)) if status_val in court_eligible else ""

        incidents.append(dict(
            incident_id=iid, fir_no=f"{st}/{yr}/{fir_seq[st]:04d}",
            occurred_at=when.strftime("%Y-%m-%d %H:%M:%S"),
            reported_at=reported.strftime("%Y-%m-%d %H:%M:%S"),
            district_code=district_code, station_code=st, crime_type=crime_name,
            ipc_bns_code=code, lat=lat, long=long, address_text=addr, mo_text=mo,
            status=status_val,
            case_category=str(weighted_choice(rng2, cc_items, cc_w)),
            gravity="Heinous" if crime_name in heinous_crimes else "Non-Heinous",
            officer_id=officer_id,
            incident_to_date=incident_to.strftime("%Y-%m-%d %H:%M:%S"),
            info_received_ps_date=info_received.strftime("%Y-%m-%d %H:%M:%S"),
            court_id=court_id,
            mo_cluster_id="", series_id="",
            source_fir_url=f"stratus://raw-fir/{iid}.pdf",
            confidence=round(float(rng.uniform(0.75, 0.99)), 2),
            # unchanged from the original expression — keeps rng's per-incident draw
            # count identical, so planted-scenario identities downstream (kingpin,
            # shared phone/vehicle) stay reproducible from the same seed.
            created_by=f"{st}-OFF{int(rng.integers(1, 40)):02d}"))
        return iid, crime_name

    def add_edge(iid, entity_id, role, evidence):
        is_police = ""
        if role == "victim":
            is_police = bool(rng3.random() < p_victim_police)
        edges.append(dict(incident_id=iid, entity_id=entity_id, role=role,
                          edge_weight=round(float(rng.uniform(0.5, 1.0)), 2),
                          evidence_type=evidence, is_police=is_police))

    def attach_entities(iid, crime_name):
        # always 1 suspect; then up to 2 more (1..3 entities/incident)
        suspect = str(rng.choice(p_ids, p=p_w))
        add_edge(iid, suspect, "suspect", rng.choice(["fir_named", "cctv"]))
        slots = int(rng.choice([0, 1, 2], p=[0.35, 0.45, 0.20]))
        used = 0
        if crime_name in {"Two-wheeler theft", "Motor vehicle theft", "Robbery",
                          "Chain snatching", "Dacoity"} and used < slots and rng.random() < 0.6:
            add_edge(iid, str(rng.choice(veh_ids)), "vehicle_used", rng.choice(["cctv", "recovered"]))
            used += 1
        if crime_name in {"Cybercrime", "Cheating", "Criminal breach of trust",
                          "Chain snatching"} and used < slots and rng.random() < 0.5:
            add_edge(iid, str(rng.choice(phone_ids)), "phone_used", "call_record")
            used += 1
        if used < slots and rng.random() < 0.6:
            add_edge(iid, str(rng.choice(p_ids, p=p_w)), "victim", "fir_named")
            used += 1
        if used < slots:
            add_edge(iid, str(rng.choice(p_ids, p=p_w)), "witness", "witness")

    # ---- planted incidents are additive on top of the base target ----
    pl = cfg["planted"]
    n_base = int(cfg["counts"]["n_incidents"])
    n_net = int(pl["network"]["n_incidents"])
    n_series = int(pl["series"]["n_incidents"])

    # ---- base incidents ----
    for _ in range(n_base):
        dc = weighted_choice(rng, [d["code"] for d in districts], dweights)
        cn = weighted_choice(rng, [c["name"] for c in crime_types], cweights)
        iid, _ = make_incident(dc, cn, sample_dt(cn))
        attach_entities(iid, cn)

    ground = {"seed": seed, "generated_at": datetime.now().isoformat(timespec="seconds")}

    # ---- planted 1: organised cross-district network ----
    net = pl["network"]
    members = []
    for i in range(int(net["n_members"])):
        nm = fake.name()
        mid = new_eid()
        entities.append(dict(entity_id=mid, canonical_id=mid, type="person", value=nm,
                             alias_of="", age=int(rng.integers(22, 45)), gender="M",
                             match_confidence=""))
        members.append({"entity_id": mid, "value": nm})
    kingpin = members[0]
    shared_phone_id = new_eid()
    shared_phone_val = phone_no(rng)
    entities.append(dict(entity_id=shared_phone_id, canonical_id=shared_phone_id, type="phone",
                         value=shared_phone_val, alias_of="", age="", gender="", match_confidence=""))
    shared_veh_id = new_eid()
    shared_veh_val = ka_reg(rng)
    entities.append(dict(entity_id=shared_veh_id, canonical_id=shared_veh_id, type="vehicle",
                         value=shared_veh_val, alias_of="", age="", gender="", match_confidence=""))
    nstart = pd.to_datetime(net["window"]["start"])
    nend = pd.to_datetime(net["window"]["end"])
    span = (nend - nstart).days
    net_districts = net["districts"]
    net_incidents = []
    for i in range(n_net):
        dc = net_districts[i % len(net_districts)]   # cycle => guarantees >=3 districts
        d = dcode[dc]
        when = (nstart + timedelta(days=int(rng.integers(0, span + 1)),
                                   hours=int(rng.choice(24, p=hw_night)),
                                   minutes=int(rng.integers(0, 60)))).to_pydatetime()
        place = f"{rng.choice(LOCALITIES)}, {d['name']}"
        iid, _ = make_incident(dc, net["crime_type"], when, mo=PLANTED_SNATCH_MO.format(place=place))
        net_incidents.append(iid)
        # kingpin present in ~kingpin_presence of incidents; plus 1-2 other members
        if rng.random() < float(net["kingpin_presence"]):
            add_edge(iid, kingpin["entity_id"], "suspect", "cctv")
        for m in rng.choice(members[1:], size=int(rng.integers(1, 3)), replace=False):
            add_edge(iid, m["entity_id"], "suspect", "fir_named")
        add_edge(iid, shared_phone_id, "phone_used", "call_record")   # shared -> links all
        add_edge(iid, shared_veh_id, "vehicle_used", "cctv")          # shared -> links all
    ground["network"] = {
        "crime_type": net["crime_type"], "districts": net_districts,
        "kingpin_entity_id": kingpin["entity_id"], "kingpin_value": kingpin["value"],
        "member_entity_ids": [m["entity_id"] for m in members],
        "shared_phone": shared_phone_val, "shared_vehicle": shared_veh_val,
        "incident_ids": net_incidents,
    }

    # ---- planted 2: near-repeat series ----
    ser = pl["series"]
    sd = dcode[ser["district"]]
    loc_lat = round(sd["lat"] + 0.03, 6)
    loc_long = round(sd["long"] + 0.03, 6)
    s0 = pd.to_datetime(str(rng.choice(days))).to_pydatetime()
    jit = float(ser["locality_jitter_deg"])
    series_incidents = []
    for i in range(n_series):
        when = s0 + timedelta(days=int(rng.integers(0, int(ser["window_days"]) + 1)),
                              hours=int(rng.choice(24, p=hw_night)))
        lat = round(loc_lat + float(rng.normal(0, jit)), 6)
        long = round(loc_long + float(rng.normal(0, jit)), 6)
        iid, _ = make_incident(ser["district"], ser["crime_type"], when, lat=lat, long=long)
        attach_entities(iid, ser["crime_type"])
        series_incidents.append(iid)
    ground["series"] = {
        "crime_type": ser["crime_type"], "district_code": ser["district"],
        "locality_center": [loc_lat, loc_long],
        "window": [s0.strftime("%Y-%m-%d"),
                   (s0 + timedelta(days=int(ser["window_days"]))).strftime("%Y-%m-%d")],
        "incident_ids": series_incidents,
    }

    # ---- planted 3: anomaly spikes ----
    anomalies = []
    base_df = pd.DataFrame(incidents)
    base_df["_month"] = base_df["occurred_at"].str.slice(0, 7)
    for a in pl["anomalies"]:
        month = a["month"]
        baseline = int(((base_df["district_code"] == a["district"]) &
                        (base_df["crime_type"] == a["crime_type"]) &
                        (base_df["_month"] == month)).sum())
        mult = float(a["multiplier"])
        injected = max(round(baseline * (mult - 1)), 8)   # floor keeps the spike visible
        m0 = pd.to_datetime(month + "-01")
        mdays = (m0 + pd.offsets.MonthEnd(0)).day
        spike_ids = []
        for _ in range(injected):
            when = datetime(m0.year, m0.month, int(rng.integers(1, mdays + 1)),
                            int(rng.choice(24, p=hw_night)), int(rng.integers(0, 60)))
            iid, _ = make_incident(a["district"], a["crime_type"], when)
            attach_entities(iid, a["crime_type"])
            spike_ids.append(iid)
        total = baseline + injected
        anomalies.append({
            "district_code": a["district"], "crime_type": a["crime_type"], "month": month,
            "window": [m0.strftime("%Y-%m-%d"), (m0 + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")],
            "baseline_count": baseline, "injected_count": injected, "spiked_total": total,
            "target_multiplier": mult,
            "actual_multiplier": round(total / baseline, 2) if baseline else None,
            "incident_ids": spike_ids,
        })
    ground["anomalies"] = anomalies

    # ---- ChargesheetDetails — only cases that reached a final-report status get one ----
    cs_cfg = cfg["chargesheet"]
    eligible = set(cs_cfg["eligible_statuses"])
    cs_types = list(cs_cfg["cstype_weights"].keys())
    cs_w = np.array(list(cs_cfg["cstype_weights"].values()), float)
    lo, hi = cs_cfg["days_to_chargesheet"]
    chargesheets = []
    cs_n = 0
    for inc in incidents:
        if inc["status"] not in eligible:
            continue
        cs_n += 1
        occurred = datetime.strptime(inc["occurred_at"], "%Y-%m-%d %H:%M:%S")
        csdate = occurred + timedelta(days=int(rng2.integers(int(lo), int(hi) + 1)))
        chargesheets.append(dict(
            cs_id=f"CS{cs_n:06d}", incident_id=inc["incident_id"],
            cs_date=csdate.strftime("%Y-%m-%d"),
            cs_type=str(weighted_choice(rng2, cs_types, cs_w)),
            officer_id=inc["officer_id"]))

    # ---- ActSectionAssociation — every case invokes >=1 act+section (one-to-many).
    # The incident's ipc_bns_code stays the primary/most-serious (section_order 1);
    # crime-type companion sections follow at 2..n. Isolated stream again (see the
    # rng2 note): these draws must not perturb any existing output — and sections
    # and arrests each get their OWN stream so future changes to one never
    # reshuffle the other.
    rng_sec = np.random.default_rng(seed + 330044)
    sec_cfg = cfg["case_sections"]
    extra_k = [int(k) for k in sec_cfg["extra_weights"]]
    extra_w = np.array(list(sec_cfg["extra_weights"].values()), float)
    companions = sec_cfg["companions"]
    case_sections = []
    for inc in incidents:
        crime = crime_by_name[inc["crime_type"]]
        act = "BNS" if inc["ipc_bns_code"] == crime["bns"] else "IPC"
        seen = {(act, inc["ipc_bns_code"])}
        act_order = {act: 1}   # ActSectionAssociation.ActOrderID (P2 #15) — distinct
                               # from section_order: orders the ACT, not each section
        case_sections.append(dict(incident_id=inc["incident_id"], act_code=act,
                                  section_code=inc["ipc_bns_code"], section_order=1,
                                  act_order=1))
        pool = companions.get(inc["crime_type"], [])
        k = min(int(weighted_choice(rng_sec, extra_k, extra_w)), len(pool))
        if k == 0:
            continue
        order = 2
        for idx in rng_sec.choice(len(pool), size=k, replace=False):
            comp = pool[int(idx)]
            if "act" in comp:   # statute-fixed (e.g. IT Act) — same code under IPC or BNS
                c_act, c_sec = str(comp["act"]), str(comp["section"])
            else:               # act-matched: follow how this case is coded
                c_act, c_sec = act, str(comp["bns" if act == "BNS" else "ipc"])
            if (c_act, c_sec) in seen:
                continue
            seen.add((c_act, c_sec))
            if c_act not in act_order:
                act_order[c_act] = len(act_order) + 1
            case_sections.append(dict(incident_id=inc["incident_id"], act_code=c_act,
                                      section_code=c_sec, section_order=order,
                                      act_order=act_order[c_act]))
            order += 1

    # ---- ArrestSurrender — arrest/surrender events per accused suspect ----
    # Starts the CrPC/BNSS 60/90-day default-bail clock (docs/product/08 §1); a
    # suspect edge with no row here on an open case is the absconding board (08 §6).
    rng_arr = np.random.default_rng(seed + 440055)
    arr_cfg = cfg["arrests"]
    p_posture = arr_cfg["p_arrested_by_posture"]
    surrender_frac = float(arr_cfg["surrender_fraction"])
    lag_lo, lag_hi = arr_cfg["days_after_report"]
    recency = float(arr_cfg["open_case_recency_days"])
    p_complainant_accused = float(arr_cfg["p_complainant_accused"])
    end_dt = end.to_pydatetime()
    cs_by_inc = {c["incident_id"]: c for c in chargesheets}
    # suspects per incident in edge order (never a set — str hashing is per-process,
    # so set iteration order would break rerun-to-rerun reproducibility)
    suspects_by_inc = {}
    for e in edges:
        if e["role"] == "suspect":
            lst = suspects_by_inc.setdefault(e["incident_id"], [])
            if e["entity_id"] not in lst:
                lst.append(e["entity_id"])
    arrests = []
    arr_n = 0
    for inc in incidents:
        suspects = suspects_by_inc.get(inc["incident_id"], [])
        if not suspects:
            continue
        cs = cs_by_inc.get(inc["incident_id"])
        if cs:
            posture = "chargesheeted_A" if cs["cs_type"] == "A" else "false_or_undetected"
        elif inc["status"] == "Pending Trial":
            posture = "pending_trial"
        else:
            posture = "under_investigation"
        p = float(p_posture[posture])
        reported = datetime.strptime(inc["reported_at"], "%Y-%m-%d %H:%M:%S")
        for ent_id in suspects:
            if rng_arr.random() >= p:
                continue          # never arrested -> absconding while the case is open
            if cs:
                # custody must precede the final report: arrest in [reported, cs_date]
                cs_dt = datetime.strptime(cs["cs_date"], "%Y-%m-%d")
                span = max((cs_dt - reported).days, 1)
                event = reported + timedelta(days=float(rng_arr.uniform(0, span)))
            elif posture == "pending_trial":
                event = reported + timedelta(days=float(rng_arr.uniform(lag_lo, lag_hi)))
            else:
                # open cases: the surviving live-clock population skews recent — old
                # arrests resolve (chargesheet or default bail) and leave this pool
                event = max(reported + timedelta(days=float(rng_arr.uniform(0, 3))),
                            end_dt - timedelta(days=float(rng_arr.uniform(0, recency))))
            event = max(min(event, end_dt), reported)   # never future-dated / pre-FIR
            arr_n += 1
            officer_pool = officers_by_district.get(inc["district_code"])
            arrests.append(dict(
                arrest_id=f"ARR{arr_n:06d}", incident_id=inc["incident_id"],
                entity_id=ent_id,
                event_type="surrender" if rng_arr.random() < surrender_frac else "arrest",
                event_date=event.strftime("%Y-%m-%d"),
                district_code=inc["district_code"],
                # production court (organizer: ArrestSurrender.CourtID) — this id
                # scheme (CRT-{district}-{01..03}) now resolves against the Courts
                # reference table generated above; unchanged so this file's existing
                # rng_arr draw sequence (and therefore every other field below) stays
                # byte-identical to before Courts existed.
                court_id=f"CRT-{inc['district_code']}-{int(rng_arr.integers(1, 4)):02d}",
                io_officer_id=inc["officer_id"] if rng_arr.random() < 0.85 or not officer_pool
                else str(rng_arr.choice(officer_pool)),
                # ArrestSurrender.IsAccused/IsComplainantAccused (P2 #9): the
                # first-listed suspect is the primary accused; co-accused (any
                # later suspect on a multi-accused case) are secondary.
                is_accused=bool(ent_id == suspects[0]),
                is_complainant_accused=bool(rng_arr.random() < p_complainant_accused)))

    # ---- CrimeHeadActSection reference (P2 #14) — head -> every act+section seen
    # across the crime_types under it (primary code + companions). Deterministic,
    # no RNG: it's a lookup derived from config, not a per-incident fact.
    crime_head_rows = []
    seen_head_triples = set()

    def _add_head_section(head, act_code, sec_code):
        key = (head, act_code, sec_code)
        if key not in seen_head_triples:
            seen_head_triples.add(key)
            crime_head_rows.append(dict(crime_head=head, act_code=act_code, section_code=sec_code))

    for head, crime_names in cfg["crime_heads"].items():
        for cn in crime_names:
            crime = crime_by_name.get(cn)
            if not crime:
                continue
            _add_head_section(head, "IPC", crime["ipc"])
            _add_head_section(head, "BNS", crime["bns"])
            for comp in companions.get(cn, []):
                if "act" in comp:
                    _add_head_section(head, str(comp["act"]), str(comp["section"]))
                else:
                    _add_head_section(head, "IPC", str(comp["ipc"]))
                    _add_head_section(head, "BNS", str(comp["bns"]))

    # ---- P3 organizer-schema completeness (ER PDF audit, 2026-07-17) --------
    # Three details the organizer's ER diagram specifies that the model lacked.
    # All of it runs AFTER every existing draw, in post-passes, on its own
    # isolated stream (rng4) — the standing invariant: previously generated
    # columns stay byte-identical from the same seed.

    # (1) Units master (organizer: Unit/UnitType, self-referencing hierarchy).
    # Numeric ids are what CrimeNo's 4-digit district/unit segments encode.
    # Deterministic — a lookup derived from config, not a per-incident fact.
    sorted_dcodes = sorted(dcode)
    district_num = {dc: i + 1 for i, dc in enumerate(sorted_dcodes)}
    unit_rows = [dict(unit_id="0001", unit_name="Karnataka State Police HQ",
                      unit_type="State HQ", parent_unit="", district_code="",
                      district_num="", station_code="", lat="", long="")]
    unit_num = {}
    for dc in sorted_dcodes:
        d = dcode[dc]
        dnum = district_num[dc]
        do_id = f"{dnum:02d}00"
        unit_rows.append(dict(unit_id=do_id, unit_name=f"{d['name']} District Police Office",
                              unit_type="District Office", parent_unit="0001",
                              district_code=dc, district_num=f"{dnum:04d}",
                              station_code="", lat=d["lat"], long=d["long"]))
        for st in stations[dc]:
            st_idx = int(st[len(dc):])
            uid = f"{dnum:02d}{st_idx:02d}"
            unit_num[st] = uid
            # deterministic ring placement around the district centroid (golden
            # angle) — station markers for the map's drill-down, no RNG consumed
            ang = st_idx * 2.399963
            rad = 0.05 + (st_idx % 3) * 0.022
            unit_rows.append(dict(
                unit_id=uid, unit_name=f"{d['name']} PS {st_idx:02d}",
                unit_type="Police Station", parent_unit=do_id,
                district_code=dc, district_num=f"{dnum:04d}", station_code=st,
                lat=round(d["lat"] + rad * math.cos(ang), 6),
                long=round(d["long"] + rad * math.sin(ang), 6)))

    # (2) CaseMaster.CrimeNo / CaseNo in the organizer's exact 18-digit format:
    # 1 CaseCategory digit + 4 District + 4 Unit + 4 Year + 5 Serial, with a
    # separate running serial per (station, category, year); CaseNo = the last
    # 9 digits. Purely derived from already-drawn fields — zero RNG.
    cc_digit = {c["code"]: str(c["digit"]) for c in cfg["case_categories"]}
    crime_serial = {}
    for inc in incidents:
        yr = inc["occurred_at"][:4]
        key = (inc["station_code"], inc["case_category"], yr)
        crime_serial[key] = crime_serial.get(key, 0) + 1
        serial = f"{crime_serial[key]:05d}"
        inc["crime_no"] = (cc_digit.get(inc["case_category"], "1")
                           + f"{district_num[inc['district_code']]:04d}"
                           + unit_num[inc["station_code"]]
                           + yr + serial)
        inc["case_no"] = yr + serial

    # (3) ComplainantDetails (one-to-many off CaseMaster; every real FIR has
    # one). rng4 only: in property/economic crime the victim usually files the
    # FIR themselves, otherwise a member of the public does. The organizer's
    # Occupation/Religion/Caste columns are deliberately NOT modeled — see
    # docs/DATASET_REAL_SCHEMA.md (fairness: GARUDA profiles places and times,
    # never communities).
    rng4 = np.random.default_rng(seed + 550099)
    victims_by_inc = {}
    for e in edges:
        if e["role"] == "victim":
            victims_by_inc.setdefault(e["incident_id"], []).append(e["entity_id"])
    for inc in incidents:
        if rng4.random() >= 0.97:              # a few FIRs (UDR etc.) have none
            continue
        vics = victims_by_inc.get(inc["incident_id"])
        if vics and rng4.random() < 0.6:
            comp = vics[0]                     # victim filed their own FIR
        else:
            comp = str(rng4.choice(p_ids))     # unweighted: ordinary public
        edges.append(dict(incident_id=inc["incident_id"], entity_id=comp,
                          role="complainant",
                          edge_weight=round(float(rng4.uniform(0.5, 1.0)), 2),
                          evidence_type="fir_named", is_police=""))

    # ---- write ----
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    inc_df = pd.DataFrame(incidents)
    ent_df = pd.DataFrame(entities)
    edge_df = pd.DataFrame(edges)
    off_df = pd.DataFrame(officers)
    cs_df = pd.DataFrame(chargesheets)
    arr_df = pd.DataFrame(arrests)
    sec_df = pd.DataFrame(case_sections)
    court_df = pd.DataFrame(courts)
    status_df = pd.DataFrame(case_status_rows)
    head_df = pd.DataFrame(crime_head_rows)
    unit_df = pd.DataFrame(unit_rows)
    inc_df.to_csv(out_dir / "incidents.csv", index=False, encoding="utf-8")
    ent_df.to_csv(out_dir / "entities.csv", index=False, encoding="utf-8")
    edge_df.to_csv(out_dir / "incident_edges.csv", index=False, encoding="utf-8")
    off_df.to_csv(out_dir / "officers.csv", index=False, encoding="utf-8")
    cs_df.to_csv(out_dir / "chargesheets.csv", index=False, encoding="utf-8")
    arr_df.to_csv(out_dir / "arrests.csv", index=False, encoding="utf-8")
    sec_df.to_csv(out_dir / "case_sections.csv", index=False, encoding="utf-8")
    court_df.to_csv(out_dir / "courts.csv", index=False, encoding="utf-8")
    status_df.to_csv(out_dir / "case_status.csv", index=False, encoding="utf-8")
    head_df.to_csv(out_dir / "crime_head_sections.csv", index=False, encoding="utf-8")
    unit_df.to_csv(out_dir / "units.csv", index=False, encoding="utf-8")
    (out_dir / "ground_truth.json").write_text(
        json.dumps(ground, ensure_ascii=False, indent=2), encoding="utf-8")

    return inc_df, ent_df, edge_df, ground


def main():
    ap = argparse.ArgumentParser(description="GARUDA synthetic dataset generator")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--n-incidents", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    if args.n_incidents:
        cfg["counts"]["n_incidents"] = args.n_incidents
    if args.seed:
        cfg["seed"] = args.seed

    inc, ent, edge, ground = generate(cfg, args.out)

    print(f"incidents      : {len(inc):>7,}")
    print(f"entities       : {len(ent):>7,}  "
          f"(persons={int((ent['type']=='person').sum())}, "
          f"vehicles={int((ent['type']=='vehicle').sum())}, "
          f"phones={int((ent['type']=='phone').sum())}, "
          f"aliases={int((ent['alias_of']!='').sum())})")
    print(f"incident_edges : {len(edge):>7,}")
    print(f"districts seen  : {inc['district_code'].nunique()} / 31")
    print(f"BNS share       : {(~inc['ipc_bns_code'].str.match(r'^[0-9]+$')).mean():.0%} "
          f"(codes with parentheses are BNS)")
    print("\nplanted patterns recorded in ground_truth.json:")
    print(f"  network  : {len(ground['network']['incident_ids'])} incidents across "
          f"{len(set(ground['network']['districts']))} districts; kingpin={ground['network']['kingpin_value']!r}")
    print(f"             shared phone={ground['network']['shared_phone']}  vehicle={ground['network']['shared_vehicle']}")
    print(f"  series   : {len(ground['series']['incident_ids'])} {ground['series']['crime_type']} in "
          f"{ground['series']['district_code']} within {ground['series']['window']}")
    for a in ground["anomalies"]:
        print(f"  anomaly  : {a['crime_type']} in {a['district_code']} {a['month']} "
              f"baseline={a['baseline_count']} -> total={a['spiked_total']} (x{a['actual_multiplier']})")


if __name__ == "__main__":
    main()
