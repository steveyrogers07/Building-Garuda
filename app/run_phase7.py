"""GARUDA — Phase 7 local runner (no Catalyst account needed, $0).

Runs a battery of plain-English questions through the hybrid copilot, prints the
cited answers + refusals, and appends the Audit_Log to local storage.

Local storage defaults to  ~/OneDrive/Desktop/garuda  (override with GARUDA_HOME).
The engine here is exactly what serves /copilot on AppSail; only storage is local.

    python app/run_phase7.py
    python app/run_phase7.py "house burglary in Mysuru in May 2024"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if "GARUDA_HOME" not in os.environ:
    os.environ["GARUDA_HOME"] = str(Path.home() / "OneDrive" / "Desktop" / "garuda")
sys.path.insert(0, str(REPO / "app"))

from engines import copilot as cp        # noqa: E402
from shared import store                   # noqa: E402

DEMO = [
    "chain snatching in BNU",
    "two-wheeler theft in BNU in March 2025",
    "house burglary in Mysuru in May 2024",
    "is the accused guilty in the chain snatching case?",   # guardrail: refuse
    "what is the weather today",                            # guardrail: out-of-scope
]


def main():
    queries = sys.argv[1:] or DEMO
    inc = store.fetch_incidents_copilot()
    index, refs = cp.prepare(inc, store.fetch_socioeconomic())
    print("GARUDA Phase 7 copilot -> %d incidents indexed\n" % len(inc))

    audit = []
    for q in queries:
        res = cp.answer(q, inc, index, refs)
        audit.append(cp.audit_entry(q, res))
        print("Q:", q)
        if res["refused"]:
            print("   [REFUSED: %s] %s" % (res.get("reason"), res["answer"]))
        else:
            print("   %s" % res["answer"].split("\n")[0])
            for c in res["citations"][:3]:
                print("     - %s | %s | %s | %s" % (c["fir_no"], c["crime_type"],
                      c["district_code"], str(c["occurred_at"])[:10]))
            print("   citations: %d  | guardrail on" % len(res["citations"]))
        print()

    n = store.write_audit_log(audit)
    print("audit: %d entries appended to %s/audit_log.csv" % (n, os.environ["GARUDA_HOME"]))
    print("done.")


if __name__ == "__main__":
    main()
