#!/usr/bin/env python3
"""GARUDA — synthetic FIR document generator (Phase 3, M1).

Renders Phase-2 incidents into realistic CCTNS-style FIR documents:
    data/fir_samples/<doc_id>.txt   the FIR text  (== ground-truth OCR output; test input now)
    data/fir_samples/<doc_id>.png   a rendered "scan" (real OCR input once Zia is wired)
    data/fir_samples/fir_key.json   the GOLDEN KEY (doc -> true fields) to score extraction

It deliberately includes the planted network + series incidents so the ingestion
pipeline can be measured on the interesting cases. Build-side only (no Catalyst).

Run `python data/generate.py` + `python data/build_reference.py` first.

Usage:  python data/fir_samples/generate_firs.py [--n 40] [--degrade]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
SYNTH = DATA / "synthetic"
REF = DATA / "reference"

FIR_TEMPLATE = """\
================= FIRST INFORMATION REPORT =================
        (U/s 154 Cr.P.C. r/w Section 173 BNSS, 2023)
   Karnataka State Police  |  CCTNS / e-FIR

District    : {district_name} ({district_code})
Police Stn  : {station_code}
FIR No.     : {fir_no}
Reported on : {reported_at}

1. Acts & Sections    : {code_system} Section {ipc_bns_code} - {crime_head} ({crime_type})
2. Occurrence Date/Time: {occurred_at}
3. Place of Offence   : {address_text}
   Approx GPS         : {lat}, {long}
4. Complainant        : {complainant}
5. Accused            : {accused}
6. Property / Vehicle : {vehicles}
7. Contact Number(s)  : {phones}
8. Brief Facts (MO)   : {mo_text}
9. Investigating Off. : {created_by}
   Status             : {status}
===========================================================
"""


def load_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def render_png(text, path, degrade=False):
    """Best-effort scan rendering with PIL; skipped gracefully if PIL is absent."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    lines = text.splitlines()
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    W, lh, pad = 880, 22, 24
    H = pad * 2 + lh * len(lines)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        d.text((pad, pad + i * lh), ln, fill="black", font=font)
    if degrade:
        try:
            import numpy as np
            img = img.rotate(random.uniform(-1.5, 1.5), expand=False, fillcolor="white")
            arr = np.asarray(img).astype("int16")
            arr += np.random.normal(0, 8, arr.shape).astype("int16")
            img = Image.fromarray(arr.clip(0, 255).astype("uint8"))
        except Exception:
            pass
    img.save(path)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="how many FIR docs to render")
    ap.add_argument("--degrade", action="store_true", help="add scan-like noise/rotation")
    ap.add_argument("--seed", type=int, default=20260618)
    args = ap.parse_args()
    random.seed(args.seed)

    if not (SYNTH / "incidents.csv").exists():
        raise SystemExit("Run `python data/generate.py` first (no data/synthetic/incidents.csv).")

    incidents = {r["incident_id"]: r for r in load_csv(SYNTH / "incidents.csv")}
    entities = {r["entity_id"]: r for r in load_csv(SYNTH / "entities.csv")}
    edges = load_csv(SYNTH / "incident_edges.csv")
    ground = json.loads((SYNTH / "ground_truth.json").read_text(encoding="utf-8"))

    district_name = {r["area_code"]: r["district_name"] for r in load_csv(REF / "census_2011.csv")}
    crime_head = {}
    for r in load_csv(REF / "ipc_bns_map.csv"):
        crime_head[r["ipc_code"]] = r["crime_head"]
        crime_head[r["bns_code"]] = r["crime_head"]

    edges_by_inc = {}
    for e in edges:
        edges_by_inc.setdefault(e["incident_id"], []).append(e)

    # choose sample: all planted network + series, a few anomalies, then random fill
    chosen = list(ground["network"]["incident_ids"]) + list(ground["series"]["incident_ids"])
    for a in ground["anomalies"]:
        chosen += a["incident_ids"][:2]
    pool = [i for i in incidents if i not in set(chosen)]
    random.shuffle(pool)
    while len(chosen) < args.n and pool:
        chosen.append(pool.pop())
    chosen = list(dict.fromkeys(chosen))[:args.n]

    out = HERE
    out.mkdir(parents=True, exist_ok=True)
    key = []
    png_ok = 0
    for n, iid in enumerate(chosen, 1):
        inc = incidents[iid]
        es = edges_by_inc.get(iid, [])

        def vals(role):
            return [entities[e["entity_id"]] for e in es
                    if e["role"] == role and e["entity_id"] in entities]

        accused = vals("suspect")
        victims = vals("victim")
        vehicles = [e["value"] for e in vals("vehicle_used")]
        phones = [e["value"] for e in vals("phone_used")]
        comp = victims[0] if victims else None
        code = inc["ipc_bns_code"]
        doc_id = f"FIR_{n:03d}_{iid}"

        text = FIR_TEMPLATE.format(
            district_name=district_name.get(inc["district_code"], inc["district_code"]),
            district_code=inc["district_code"], station_code=inc["station_code"],
            fir_no=inc["fir_no"], reported_at=inc["reported_at"],
            code_system="BNS" if "(" in code else "IPC", ipc_bns_code=code,
            crime_head=crime_head.get(code, inc["crime_type"]), crime_type=inc["crime_type"],
            occurred_at=inc["occurred_at"], address_text=inc["address_text"],
            lat=inc["lat"], long=inc["long"],
            complainant=(f"{comp['value']}, Age {comp['age'] or '-'}, {comp['gender'] or '-'}"
                         if comp else "State / Suo motu"),
            accused="; ".join(a["value"] for a in accused) or "Unknown",
            vehicles="; ".join(vehicles) or "Nil",
            phones="; ".join(phones) or "Nil",
            mo_text=inc["mo_text"], created_by=inc["created_by"], status=inc["status"])

        (out / f"{doc_id}.txt").write_text(text, encoding="utf-8")
        if render_png(text, out / f"{doc_id}.png", degrade=args.degrade):
            png_ok += 1

        key.append({
            "doc_id": doc_id, "txt": f"{doc_id}.txt", "png": f"{doc_id}.png",
            "source_incident_id": iid,
            "truth": {
                "fir_no": inc["fir_no"], "occurred_at": inc["occurred_at"],
                "district_code": inc["district_code"], "station_code": inc["station_code"],
                "crime_type": inc["crime_type"], "ipc_bns_code": code,
                "lat": inc["lat"], "long": inc["long"], "address_text": inc["address_text"],
                "status": inc["status"], "mo_text": inc["mo_text"],
                "persons": ([{"value": comp["value"], "role": "victim"}] if comp else [])
                           + [{"value": a["value"], "role": "suspect"} for a in accused],
                "vehicles": vehicles, "phones": phones,
            },
        })

    (out / "fir_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rendered {len(key)} FIR docs  (.txt all, .png {png_ok}) -> {out}")
    print(f"  includes {len(ground['network']['incident_ids'])} network + "
          f"{len(ground['series']['incident_ids'])} series planted incidents")
    print(f"golden key -> {out / 'fir_key.json'}")


if __name__ == "__main__":
    main()
