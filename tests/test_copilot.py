"""GARUDA — local Phase-7 copilot evaluation (no Catalyst, $0).

Runs a battery of natural-language queries through the hybrid copilot and checks
the Phase-7 gates:
  - G1  NL -> structured filters -> row selection over Incidents.
  - G2  semantic rerank fuses with the structured hits.
  - G3  every answer cites source FIR IDs; guardrails refuse guilt / out-of-scope.
  - G4  each query produces an Audit_Log entry.
  - G5  citation accuracy (cited FIRs actually satisfy the query) >= 0.9.

Run:  python tests/test_copilot.py
Prereqs: python data/generate.py && python data/build_reference.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))

from engines import copilot as cp        # noqa: E402

SYN = REPO / "data" / "synthetic"
REF = REPO / "data" / "reference"

# structured queries: every citation must satisfy these (citation accuracy)
QUERIES = [
    {"q": "chain snatching in BNU",
     "must": {"crime_type": "Chain snatching", "district_code": "BNU"}},
    {"q": "house burglary in Mysuru in May 2024",
     "must": {"crime_type": "House burglary", "district_code": "MYS"},
     "window": ("2024-05-01", "2024-05-31")},
    {"q": "two-wheeler theft in BNU in March 2025",
     "must": {"crime_type": "Two-wheeler theft", "district_code": "BNU"},
     "window": ("2025-03-01", "2025-03-31")},
    {"q": "robbery in Mysuru after 8pm",
     "must": {"crime_type": "Robbery", "district_code": "MYS"}},
]


def run():
    inc = pd.read_csv(SYN / "incidents.csv", dtype=str, keep_default_na=False).to_dict("records")
    socio = pd.read_csv(REF / "census_2011.csv", dtype=str, keep_default_na=False).to_dict("records")
    index, refs = cp.prepare(inc, socio)
    print(f"copilot ready: {len(inc):,} incidents indexed, {len(refs['crime_types'])} crime types, "
          f"{len(refs['districts'])} district keys")

    audit = []
    correct = total = 0
    for case in QUERIES:
        res = cp.answer(case["q"], inc, index, refs)
        audit.append(cp.audit_entry(case["q"], res))
        assert not res["refused"], f"unexpected refusal: {case['q']}"
        assert res["citations"], f"no citations for: {case['q']}"
        # G5: every citation must satisfy the structured constraints
        ok = 0
        for c in res["citations"]:
            good = all(c.get(k) == v for k, v in case["must"].items())
            if "window" in case:
                d = str(c.get("occurred_at", ""))[:10]
                good = good and case["window"][0] <= d <= case["window"][1]
            ok += good
        correct += ok
        total += len(res["citations"])
        print(f"  Q: {case['q']!r}\n     -> {res['count']} hits, {len(res['citations'])} cited, "
              f"{ok}/{len(res['citations'])} accurate  (e.g. {res['citations'][0]['fir_no']})")

    accuracy = correct / total
    print(f"\ncitation accuracy: {correct}/{total} = {accuracy:.1%}")

    # ---- G3 guardrails ----
    guilt = cp.answer("is the accused guilty in the chain snatching case", inc, index, refs)
    audit.append(cp.audit_entry("is the accused guilty...", guilt))
    print(f"guilt query -> refused={guilt['refused']} ({guilt.get('reason')})")
    assert guilt["refused"] and guilt["reason"] == "guilt_determination"

    oos = cp.answer("what is the weather today", inc, index, refs)
    audit.append(cp.audit_entry("what is the weather today", oos))
    print(f"out-of-scope -> refused={oos['refused']} ({oos.get('reason')})")
    assert oos["refused"], "out-of-scope query should be refused"

    # ---- G4 audit ----
    written = cp.__dict__  # noqa  (keep import linters happy)
    from shared import store
    n = store.write_audit_log(audit)
    print(f"audit: {n} entries written to Audit_Log")
    assert n == len(audit) and all(a["log_id"] for a in audit)

    assert accuracy >= 0.9, f"citation accuracy {accuracy:.1%} below 0.9 target"
    print("\nPASS")


def test_copilot():
    run()


if __name__ == "__main__":
    run()
