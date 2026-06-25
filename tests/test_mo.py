"""GARUDA — local MO-fingerprinting evaluation (no Catalyst).

Clusters every synthetic incident by modus operandi and checks the Phase-4 gate:
  - every incident gets an mo_cluster_id (or noise) and MO_Clusters carry a signature (G4),
  - the planted gang's chain-snatchings (identical MO) land in one coherent cluster (G5).

Run:  python tests/test_mo.py
Prereqs: python data/generate.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))   # AppSail-style imports (engines/, shared/)

from engines.mo import fit_mo            # noqa: E402

SYN = REPO / "data" / "synthetic"


def run():
    inc = pd.read_csv(SYN / "incidents.csv", dtype=str, keep_default_na=False)
    ground = json.loads((SYN / "ground_truth.json").read_text(encoding="utf-8"))

    rows = inc[["incident_id", "mo_text", "crime_type", "occurred_at"]].to_dict("records")
    res = fit_mo(rows)
    assign, clusters = res["assignments"], res["clusters"]

    n = len(rows)
    noise = sum(1 for v in assign.values() if v == "")
    print(f"incidents: {n:,}  mo clusters: {len(clusters):,}  "
          f"noise: {noise:,} ({noise / n:.1%})")
    # show a few signatures
    for c in sorted(clusters, key=lambda x: -x["size"])[:5]:
        print(f"  {c['cluster_id']}  n={c['size']:>4}  {c['label']}")

    # ---- G4: every incident assigned; signatures present ----
    assert len(assign) == n, "not every incident got an mo_cluster_id"
    assert clusters, "no MO_Clusters produced"
    for c in clusters:
        sig = json.loads(c["centroid_features"])
        assert sig.get("dominant_crime") and "flag_rate" in sig, "cluster missing signature"
        assert c["exemplar_incident_id"], "cluster missing exemplar"

    # ---- G5: planted gang lands in a coherent MO cluster ----
    net_ids = ground["network"]["incident_ids"]
    net_clusters = [assign[i] for i in net_ids]
    modal, modal_n = Counter(c for c in net_clusters if c).most_common(1)[0]
    sig = next(json.loads(c["centroid_features"]) for c in clusters if c["cluster_id"] == modal)
    print(f"\nplanted gang (G5): {modal_n}/{len(net_ids)} incidents in {modal} "
          f"(dominant crime: {sig['dominant_crime']})")

    assert modal_n >= 8, f"gang incidents not coherent: only {modal_n}/{len(net_ids)} in one cluster"
    assert sig["dominant_crime"] == ground["network"]["crime_type"], "gang cluster not chain-snatching"
    print("\nPASS")


def test_mo():
    run()


if __name__ == "__main__":
    run()
