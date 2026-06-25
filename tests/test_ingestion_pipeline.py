"""GARUDA — local end-to-end ingestion test (no Catalyst).

Runs every synthetic FIR through the real pipeline brain:
    FIR text -> extract -> geocode -> confidence -> Review_Queue record -> promote
and scores extraction against data/fir_samples/fir_key.json (the golden key).

Run:  python tests/test_ingestion_pipeline.py   (also importable as a pytest test)
Prereqs: python data/generate.py && python data/build_reference.py &&
         python data/fir_samples/generate_firs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))   # AppSail-style imports (engines/, shared/)

from engines.extraction.rules import extract_fir          # noqa: E402
from engines.extraction.confidence import score_confidence  # noqa: E402
from engines.geocode.geocoder import geocode              # noqa: E402
from engines import promote                                # noqa: E402

SAMPLES = REPO / "data" / "fir_samples"
SCALAR_FIELDS = ["fir_no", "occurred_at", "district_code", "station_code",
                 "crime_type", "ipc_bns_code", "status", "address_text"]


def run():
    key = json.loads((SAMPLES / "fir_key.json").read_text(encoding="utf-8"))
    n = len(key)
    hits = {f: 0 for f in SCALAR_FIELDS}
    p_hit = p_tot = v_hit = v_tot = ph_hit = ph_tot = 0
    geo = pending = canon_rows = 0

    for item in key:
        text = (SAMPLES / item["txt"]).read_text(encoding="utf-8")
        rec, prov = extract_fir(text)
        if rec.get("lat") is None and rec.get("address_text"):
            lat, lng, _c, _m = geocode(rec["address_text"], rec.get("district_code"))
            rec["lat"], rec["long"] = lat, lng
            prov["lat"] = prov["long"] = "geocoded" if lat is not None else "missing"

        t = item["truth"]
        for f in SCALAR_FIELDS:
            if str(rec.get(f) or "") == str(t.get(f) or ""):
                hits[f] += 1
        if rec.get("lat") is not None:
            geo += 1

        tv = {p["value"] for p in t["persons"]}
        rv = {p["value"] for p in rec.get("persons", [])}
        p_tot += len(tv); p_hit += len(tv & rv)
        v_tot += len(t["vehicles"]); v_hit += len(set(t["vehicles"]) & set(rec.get("vehicles", [])))
        ph_tot += len(t["phones"]); ph_hit += len(set(t["phones"]) & set(rec.get("phones", [])))

        conf = score_confidence(rec, prov)
        review = promote.to_review_record(rec, conf, item["doc_id"])
        pending += (review["status"] == "pending")
        can = promote.promote_to_canonical(rec, confidence=conf["_overall"])
        canon_rows += sum(len(v) for v in can.values())

    print(f"docs: {n}")
    for f in SCALAR_FIELDS:
        print(f"  {f:14s} {hits[f] / n:6.1%}")
    print(f"  {'geocoded':14s} {geo / n:6.1%}")
    print(f"  persons recall {p_hit / max(p_tot, 1):6.1%}  ({p_hit}/{p_tot})")
    print(f"  vehicles       {v_hit / max(v_tot, 1):6.1%}  ({v_hit}/{v_tot})")
    print(f"  phones         {ph_hit / max(ph_tot, 1):6.1%}  ({ph_hit}/{ph_tot})")
    print(f"review_queue pending: {pending}/{n}; canonical rows producible: {canon_rows}")

    # gate: rule extractor must be near-perfect on the structured synthetic FIRs
    assert hits["fir_no"] == n, "fir_no not perfectly extracted"
    assert hits["ipc_bns_code"] == n, "ipc_bns_code not perfectly extracted"
    assert hits["district_code"] == n, "district_code not perfectly extracted"
    assert geo == n, "geocoding did not resolve every FIR"
    assert p_hit / max(p_tot, 1) > 0.9, "person recall below 90%"
    print("PASS")


def test_pipeline():
    run()


if __name__ == "__main__":
    run()
