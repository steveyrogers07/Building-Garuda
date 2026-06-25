#!/usr/bin/env python3
"""GARUDA — build reference / lookup data (Phase 2, Step 3).

Emits representative reference data shaped to the canonical schema:
    data/reference/ipc_bns_map.csv      (IPC <-> BNS section mapping)
    data/reference/census_2011.csv      -> Socioeconomic (area_code,...)
    data/reference/geo_boundaries.csv   -> Geo_Boundaries (area_code, level, polygon=GeoJSON text)
    data/gazetteer/gazetteer.csv        (place -> lat/long for geocoding)

District list + centroids are read from generator_config.yaml (single source of truth).
Census values are approximate Karnataka 2011 figures (representative; swap precise values
later). District polygons are simple squares around the centroid — replace with the
official survey GeoJSON when available; the schema/loader/engines don't change.

Usage:  python data/build_reference.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "generator_config.yaml"
REF = HERE / "reference"
GAZ = HERE / "gazetteer"

LOCALITIES = ["Market", "Bus Stand", "1st Main", "5th Cross", "Layout", "Circle",
              "Temple Street", "Railway Station Road", "College Road",
              "Industrial Area", "Market Yard", "New Extension"]

# IPC <-> BNS mapping (representative; covers every code the generator emits + extras).
IPC_BNS = [
    ("379", "303(2)", "Theft", "Theft (incl. two-wheeler / motor-vehicle theft)"),
    ("380", "305", "Theft in dwelling", "Theft in a dwelling house"),
    ("457", "331(4)", "House-breaking", "Lurking house-trespass / house-breaking by night"),
    ("356", "304(2)", "Snatching", "Snatching of property carried by a person"),
    ("392", "309(4)", "Robbery", "Robbery"),
    ("395", "310(2)", "Dacoity", "Dacoity (robbery by five or more persons)"),
    ("420", "318(4)", "Cheating", "Cheating and dishonestly inducing delivery of property"),
    ("406", "316(2)", "Criminal breach of trust", "Criminal breach of trust"),
    ("323", "115(2)", "Hurt", "Voluntarily causing hurt"),
    ("325", "117(2)", "Grievous hurt", "Voluntarily causing grievous hurt"),
    ("326", "118(1)", "Grievous hurt by weapon", "Grievous hurt by dangerous weapon/means"),
    ("147", "191(2)", "Rioting", "Rioting"),
    ("447", "329(3)", "Criminal trespass", "Criminal trespass"),
    ("302", "103(1)", "Murder", "Murder"),
    ("307", "109", "Attempt to murder", "Attempt to murder"),
    ("363", "137(2)", "Kidnapping", "Kidnapping"),
    ("376", "64", "Rape", "Rape"),
    ("354", "74", "Outraging modesty", "Assault/criminal force to woman to outrage modesty"),
    ("498A", "85", "Cruelty to woman", "Cruelty by husband or his relatives"),
    ("384", "308(2)", "Extortion", "Extortion"),
    ("411", "317(2)", "Receiving stolen property", "Dishonestly receiving stolen property"),
    ("279", "281", "Rash driving", "Rash driving on a public way"),
    ("506", "351(2)", "Criminal intimidation", "Criminal intimidation"),
    ("341", "126(2)", "Wrongful restraint", "Wrongfully restraining a person"),
]

# Approx Karnataka 2011 census per district: population, density(/km2), literacy%, urbanization%
# (Ballari/Vijayanagara split represented approximately.)
CENSUS = {
    "BNU": (9621551, 4378, 87.7, 90.9), "BNR": (990923, 441, 77.9, 22.0),
    "MYS": (3001127, 476, 72.8, 41.4), "BEL": (4779661, 356, 73.5, 24.0),
    "KLB": (2566326, 233, 64.8, 31.7), "DK": (2089649, 457, 88.6, 47.7),
    "TMK": (2678980, 253, 75.1, 19.9), "BAL": (1400000, 300, 67.4, 36.7),
    "DVG": (1945497, 329, 75.7, 32.3), "DHW": (1847023, 434, 80.0, 56.8),
    "SMG": (1752753, 207, 80.5, 35.3), "HSN": (1776421, 261, 76.1, 21.1),
    "VJP": (2177331, 207, 67.2, 23.0), "KLR": (1536401, 384, 74.4, 32.2),
    "MDY": (1805769, 369, 70.4, 16.0), "RCR": (1928812, 228, 59.6, 22.6),
    "BID": (1703300, 312, 70.5, 24.9), "CTD": (1659456, 197, 73.7, 19.7),
    "UDP": (1177361, 304, 86.2, 28.0), "HVR": (1597668, 332, 77.6, 20.0),
    "BGK": (1889752, 288, 68.8, 27.0), "KPL": (1389920, 250, 67.3, 16.9),
    "RMN": (1082636, 309, 69.2, 24.0), "CKB": (1255104, 296, 69.8, 23.0),
    "CKM": (1137961, 158, 79.2, 21.0), "UK": (1437169, 140, 84.1, 31.0),
    "GDG": (1064570, 230, 75.2, 35.7), "VJN": (1353000, 250, 68.0, 30.0),
    "YDG": (1174271, 224, 51.8, 21.0), "KDG": (554519, 135, 82.6, 14.5),
    "CHN": (1020791, 181, 61.4, 17.0),
}


def square(lat, long, half=0.25):
    pts = [[round(long - half, 4), round(lat - half, 4)],
           [round(long + half, 4), round(lat - half, 4)],
           [round(long + half, 4), round(lat + half, 4)],
           [round(long - half, 4), round(lat + half, 4)],
           [round(long - half, 4), round(lat - half, 4)]]
    return {"type": "Polygon", "coordinates": [pts]}


def main():
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    districts = cfg["districts"]
    REF.mkdir(parents=True, exist_ok=True)
    GAZ.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(cfg["seed"]))

    # IPC<->BNS map
    with (REF / "ipc_bns_map.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ipc_code", "bns_code", "crime_head", "description"])
        w.writerows(IPC_BNS)

    # Census -> Socioeconomic
    with (REF / "census_2011.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["area_code", "district_name", "population", "density", "literacy", "urbanization"])
        for d in districts:
            pop, den, lit, urb = CENSUS[d["code"]]
            w.writerow([d["code"], d["name"], pop, den, lit, urb])

    # Geo_Boundaries (GeoJSON polygon as text)
    with (REF / "geo_boundaries.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["area_code", "level", "polygon"])
        # state bbox
        lats = [d["lat"] for d in districts]
        longs = [d["long"] for d in districts]
        state = {"type": "Polygon", "coordinates": [[
            [min(longs) - 0.5, min(lats) - 0.5], [max(longs) + 0.5, min(lats) - 0.5],
            [max(longs) + 0.5, max(lats) + 0.5], [min(longs) - 0.5, max(lats) + 0.5],
            [min(longs) - 0.5, min(lats) - 0.5]]]}
        w.writerow(["KA", "state", json.dumps(state)])
        for d in districts:
            w.writerow([d["code"], "district", json.dumps(square(d["lat"], d["long"]))])

    # Gazetteer (district centroids + synthetic taluks + localities) for geocoding
    with (GAZ / "gazetteer.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["place", "district_code", "level", "lat", "long"])
        n = 0
        for d in districts:
            w.writerow([d["name"], d["code"], "district", d["lat"], d["long"]])
            n += 1
            for k in range(1, 4):  # synthetic taluks
                off = rng.normal(0, 0.12, 2)
                w.writerow([f"{d['name']} Taluk {k}", d["code"], "taluk",
                            round(d["lat"] + off[0], 6), round(d["long"] + off[1], 6)])
                n += 1
            for loc in LOCALITIES:   # localities matching the generator's address_text
                off = rng.normal(0, 0.06, 2)
                w.writerow([f"{loc}, {d['name']}", d["code"], "locality",
                            round(d["lat"] + off[0], 6), round(d["long"] + off[1], 6)])
                n += 1

    print(f"ipc_bns_map.csv   : {len(IPC_BNS)} rows")
    print(f"census_2011.csv   : {len(districts)} districts -> Socioeconomic")
    print(f"geo_boundaries.csv: {len(districts) + 1} polygons (1 state + {len(districts)} districts)")
    print(f"gazetteer.csv     : {n} places")


if __name__ == "__main__":
    main()
