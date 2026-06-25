# GARUDA — Phase 2 Kickoff (paste this into a fresh build chat)

> You are starting a fresh build session for **Phase 2** of Project GARUDA. Read this whole brief, then help me execute Phase 2 step by step. Do **not** jump ahead to later phases.

## Project context (so you understand cold)
**Project GARUDA** — an AI-driven crime-analytics & visualization platform for the **Karnataka State Police / SCRB**, for **Datathon 2026**. **Deploy target: Zoho Catalyst.**
- **Repo:** https://github.com/steveyrogers07/Building-Garuda · **Local:** `C:\Users\hp\OneDrive\Desktop\acadflip\Building-Garuda`
- **Design docs in `docs/`:** `GARUDA_BLUEPRINT.md`, `GARUDA_DATA_READINESS.md` (read this one — it's the heart of Phase 2), `GARUDA_BUILD_WORKFLOW.md` (Stages 1–2), `GARUDA_10_PHASE_PLAN.md`.
- **Stack:** React on Web Client Hosting · Node serverless functions · **Python/FastAPI on AppSail** · **Data Store (ZCQL)** · QuickML (Qwen 2.5-14B) · Zia OCR · Zia AutoML.

**Phase 1 is assumed DONE:** the Catalyst project exists, CLI is linked, hello-world Functions/Client/AppSail deploy to Dev, Auth works, Stratus buckets (`raw-fir`, `reports`, `artifacts`) + a Cache segment exist.

**Core principle for Phase 2 — build behind an adapter:** we develop against **synthetic data shaped like the expected KSP schema**, loaded through ONE configurable adapter. When the real dataset arrives later, we only rewrite the adapter's **column-map** — no engine changes. We work in 10 gated phases; **this is Phase 2 only**: the data layer. No ingestion/OCR (Phase 3), no ML (Phases 4+), no real UI (Phase 8).

---

## Phase 2 — Goal
The canonical **Data Store** schema created, a realistic **synthetic Karnataka dataset** generated (with planted patterns for the demo), loaded through the **adapter** with a **validation gate**, and **queryable via ZCQL**.

## Phase 2 — Exit Gate (done when ALL true)
- [ ] All canonical tables exist in Data Store (core tables populated; derived tables created empty).
- [ ] Synthetic generator produces canonical-shaped CSVs incl. the **planted network + near-repeat series + anomaly spikes** + a `ground_truth.json`.
- [ ] The **adapter/loader** loads a CSV → validates → writes to Data Store, driven by a **column-map config**.
- [ ] **Validation gate** + **profiling notebook** run on any input file.
- [ ] Reference data loaded (IPC↔BNS map, Karnataka GeoJSON boundaries, Census, gazetteer).
- [ ] **ZCQL smoke tests pass**: row counts sane; JOINs work; the planted network is recoverable by query.

## Prerequisites
Python 3.11 with: `pandas faker pyyaml` (generator/adapter), `jupyter` (profiling), `zcatalyst-sdk-python` (bulk load). Phase 1 complete.

---

## Step 1 — Create the canonical Data Store tables
Create these in the Catalyst console (Data Store → Create Table) or via SDK. Catalyst auto-adds `ROWID, CREATORID, CREATEDTIME, MODIFIEDTIME`. Column types available: **Text, Int/BigInt, Decimal, Boolean, Date, DateTime, Foreign Key, AutoNumber, Encrypted Text** (confirm exact names in console). Put the create scripts/notes in `schema/`.

**Populate in Phase 2 (core + reference):**
- **Incidents** — `incident_id (Text)`, `fir_no (Text)`, `occurred_at (DateTime)`, `reported_at (DateTime)`, `district_code (Text)`, `station_code (Text)`, `crime_type (Text)`, `ipc_bns_code (Text)`, `lat (Decimal)`, `long (Decimal)`, `address_text (Text)`, `mo_text (Text)`, `status (Text)`, `mo_cluster_id (Text, null)`, `series_id (Text, null)`, `source_fir_url (Text)`, `confidence (Decimal)`, `created_by (Text)`
- **Entities** — `entity_id (Text)`, `canonical_id (Text)`, `type (Text: Person/Vehicle/Phone)`, `value (Text)`, `alias_of (Text, null)`, `age (Int, null)`, `gender (Text, null)`, `match_confidence (Decimal, null)`
- **Incident_Edges** — `incident_id (FK→Incidents)`, `entity_id (FK→Entities)`, `role (Text: Suspect/Victim/Witness/Asset)`, `edge_weight (Decimal)`, `evidence_type (Text)`
- **Socioeconomic** — `area_code (Text)`, `population (Int)`, `density (Decimal)`, `literacy (Decimal)`, `urbanization (Decimal)`
- **Geo_Boundaries** — `area_code (Text)`, `level (Text: District/Taluk/Station)`, `polygon (Text — GeoJSON)`

**Create empty now (filled in later phases):**
- **MO_Clusters** (Phase 4) · **Crime_Series** (Phase 5) · **Predictive_Risk** (Phase 6) · **Alerts** (Phase 5/6) · **Review_Queue** (Phase 3) · **Audit_Log** (Phase 9)

## Step 2 — Build the synthetic data generator  → `data/synthetic/`
Python (pandas + Faker). Output canonical-shaped CSVs: `incidents.csv`, `entities.csv`, `incident_edges.csv`, plus `ground_truth.json`. Make volumes configurable (start ~10–20k incidents to respect dev-tier quotas; scale toward 50k if quota allows).
- **Geography:** the 31 Karnataka districts (Bengaluru City as a commissionerate, weighted higher). Assign plausible station_code + lat/long jitter around district centroids.
- **Crime mix (weighted):** two-wheeler theft, chain-snatching, burglary, theft, robbery, MV theft, assault, cheating/fraud, etc.
- **Temporal realism:** time-of-day patterns (theft/snatching skew night), weekday/weekend effects, **festival spikes** (Dasara, Deepavali) and **month-end/payday** spikes.
- **Codes:** assign per crime type; ~60% rows use **BNS** (post-2024), ~40% **IPC** (older) — to exercise the IPC↔BNS map.
- **Entities (~15k):** persons (generate a canonical name, then 1–3 **alias/spelling/transliteration variants** for some — this is what entity resolution must later merge), vehicles (reg numbers), phones. Link each incident to 1–3 entities via `Incident_Edges` with roles.
- **mo_text:** short narrative templates per crime type (varied wording) — feeds MO clustering + copilot later.

**Plant these (so the demo's "aha" exists) and record them in `ground_truth.json`:**
1. **Organized network:** ~10 chain-snatching incidents across ≥3 districts (e.g., Bengaluru, Mysuru, Mandya) sharing **one phone number + one vehicle reg + near-identical MO**; 4–5 linked persons, with one "kingpin" present in most incidents (→ high betweenness later).
2. **Near-repeat series:** ~6 burglaries in one locality within ~2 weeks, same MO.
3. **Anomaly spikes:** 2–3 cases where a crime type's monthly count in a district jumps 3–4× its baseline.

`ground_truth.json` records the planted entities/kingpin, the series incident IDs, and the anomaly windows — used in Phases 4–6 to **measure** resolution precision, network recovery, and detection.

## Step 3 — Reference data  → `data/reference/`, `data/gazetteer/`
- **IPC↔BNS mapping** table (CSV) for the offense taxonomy → load into a lookup (or `Socioeconomic`-style table).
- **Karnataka district/taluk GeoJSON** boundaries → `Geo_Boundaries` (store polygon as text).
- **Census 2011** district/ward demographics → `Socioeconomic`.
- **Gazetteer** (place-name → lat/long) for geocoding (used in Phase 3).
*(Representative subsets are fine for now; sources can be small.)*

## Step 4 — Build the adapter/loader  → `ingestion/adapter/`
This is the swap-ready core. Build:
- `column_map.synthetic.yaml` — maps **source columns → canonical fields** (+ type coercion / transforms). For synthetic it's near-identity; for real KSP data you'll add `column_map.ksp.yaml` later — nothing else changes.
- `loader.py` — `load(source_csv, column_map, table)`: read → apply map → run the **validation gate** → write to Data Store via the **SDK bulk-write** API (repeatable). CLI: `python loader.py --source data/synthetic/incidents.csv --map ingestion/adapter/column_map.synthetic.yaml --table Incidents`.
- Keep ALL format-specific logic here; everything downstream reads only the canonical Data Store tables.
> Tip: to prove the adapter, optionally have the generator emit a "raw-style" variant with renamed columns, and map it back via the column-map.

## Step 5 — Profiling notebook + validation gate  → `data/notebooks/`
- `profile.ipynb` (or `profile.py`) — runs on ANY input file: row counts, dtypes, **% missing**, cardinality, date range, district coverage, candidate join keys, likely PII columns. (This is the first thing you'll run when the real dataset arrives.)
- `validate.py` (the gate, called by the loader) — schema check, required-not-null, **duplicate FIR** detection, invalid dates/coords, code-mapping coverage, encoding (Kannada/Unicode) check. Fails loudly with a triage report.

## Step 6 — Bulk-load + verify (the exit gate)
- Load synthetic CSVs through the adapter into Data Store (SDK bulk-write; or console **Data Store → Import** per table for speed).
- **ZCQL smoke tests** (run in the ZCQL console):
  - `SELECT COUNT(ROWID) FROM Incidents;` → expected volume.
  - Distribution sanity: `SELECT Crime_Type, COUNT(ROWID) FROM Incidents GROUP BY Crime_Type;`
  - JOIN works: `SELECT Incidents.Crime_Type, Entities.Value FROM Incidents JOIN Incident_Edges ON Incident_Edges.incident_id = Incidents.ROWID JOIN Entities ON Entities.ROWID = Incident_Edges.entity_id LIMIT 20;`
  - **Planted network recoverable:** query the shared phone/vehicle value and confirm it links incidents across ≥3 districts.

## Gotchas
- **Dev-tier row quotas** — if 50k is too many, generate ~10–20k (still has all planted patterns) and scale later. Don't blow the quota.
- Keep the generator **seeded** (fixed random seed) so runs are reproducible and `ground_truth.json` stays valid.
- Store GeoJSON polygons as text; don't expect spatial column types.
- The adapter writes via SDK bulk-write in batches (e.g., 200 rows) to respect API limits.

## Out of scope for Phase 2 (later phases)
OCR/ingestion pipeline → Phase 3 · entity resolution / MO clustering → Phase 4 · network/anomaly → Phase 5 · forecasting → Phase 6. Create the empty tables, but **don't populate derived data** yet.

## When Phase 2 is done
Commit & push, tick the exit gate, then start **Phase 3 — Ingestion & Extraction Pipeline** (Stratus upload → Signal → OCR → extract → Review_Queue).
