"""GARUDA — Phase 5 local runner (no Catalyst account needed).

Builds the co-offender network, links crime series, and flags emerging-trend
anomalies over the synthetic dataset, then writes every artifact to the local
storage root and prints the hero reveal:

    crime_series.csv  incidents_series.csv  alerts.csv
    network/<kingpin>.json   phase5_report.json

Local storage defaults to  ~/OneDrive/Desktop/garuda  (override with GARUDA_HOME).
The engines here are exactly what deploys to AppSail; only the storage is local.

    python app/run_phase5.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Local-storage root — set BEFORE importing shared.store (it binds OUT_DIR at import).
if "GARUDA_HOME" not in os.environ:
    os.environ["GARUDA_HOME"] = str(Path.home() / "OneDrive" / "Desktop" / "garuda")
HOME = Path(os.environ["GARUDA_HOME"])
HOME.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(REPO / "app"))

from engines import network as net           # noqa: E402
from engines.anomaly import detect           # noqa: E402
from engines.series import link_series       # noqa: E402
from shared import store                      # noqa: E402


def main():
    print("GARUDA Phase 5 -> local storage:", HOME)
    inc = store.fetch_incidents_p5()
    ent = store.fetch_entities_p5()
    edg = store.fetch_edges_p5()
    print("loaded: %d incidents, %d entities, %d edges" % (len(inc), len(ent), len(edg)))

    # ---- network ----
    a = net.analyze(inc, ent, edg)
    G = a["graph"]
    rings = net.cross_district_rings(G, a["communities"], top=10)
    print("\nnetwork: %d nodes, %d edges, %d communities, %d cross-district rings"
          % (G.number_of_nodes(), G.number_of_edges(),
             len(set(a["communities"].values())), len(rings)))

    kingpin_id = ego = None
    if rings:
        r = rings[0]
        kingpin_id = r["kingpin_id"]
        ego = net.ego_json(G, kingpin_id, a["betweenness"], a["degree"],
                           a["communities"], radius=2)
        store.write_network_cache(kingpin_id, ego)
        print("\n  TOP RING (organized gang)")
        print("    kingpin     :", r["kingpin_label"], "(%s)" % kingpin_id)
        print("    members     :", r["persons"], "persons")
        print("    districts   :", ", ".join(r["districts"]),
              "(%d districts)" % r["district_count"])
        print("    incidents   :", r["incident_count"])
        print("    shared links:", ", ".join(r["shared_links"]) or "-")

    # ---- crime series ----
    sres = link_series(inc)
    store.write_crime_series(sres["series"])
    store.write_incident_series(sres["assignments"])
    print("\ncrime series: %d linked series (%d incidents)"
          % (len(sres["series"]), len(sres["assignments"])))
    for s in sres["series"][:3]:
        print("    %s  %s x%d  %s..%s  %s" % (s["series_id"], s["crime_type"],
              s["incident_count"], s["start_date"], s["end_date"], s["district_code"]))

    # ---- anomalies ----
    ares = detect(inc)
    store.write_alerts(ares["alerts"])
    print("\nalerts: %d emerging-trend spikes" % len(ares["alerts"]))
    for al in ares["alerts"][:5]:
        print("    [%s] %s" % (al["severity"], al["detail"]))

    # ---- report ----
    report = {
        "incidents": len(inc), "entities": len(ent), "edges": len(edg),
        "network": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                    "communities": len(set(a["communities"].values())),
                    "rings": rings[:5]},
        "kingpin": kingpin_id,
        "series_count": len(sres["series"]),
        "alerts_count": len(ares["alerts"]),
        "top_alerts": ares["alerts"][:5],
    }
    (HOME / "phase5_report.json").write_text(json.dumps(report, indent=2,
                                             ensure_ascii=False), encoding="utf-8")
    written = ["crime_series.csv", "incidents_series.csv", "alerts.csv",
               "phase5_report.json"]
    if kingpin_id:
        written.append("network/%s.json" % kingpin_id)
    print("\nwrote to", HOME)
    for name in written:
        print("   ", name)
    print("done.")


if __name__ == "__main__":
    main()
