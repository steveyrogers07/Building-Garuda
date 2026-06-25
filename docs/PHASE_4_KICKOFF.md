# GARUDA — Phase 4 Kickoff (paste this into a fresh build chat)

> You are starting a fresh build session for **Phase 4** of Project GARUDA. Read this whole brief, then help me execute Phase 4 step by step. Do **not** jump ahead.

## Project context (so you understand cold)
**GARUDA** — AI crime-analytics & visualization platform for the **Karnataka State Police / SCRB**, Datathon 2026, **deploy on Zoho Catalyst**.
- **Repo:** https://github.com/steveyrogers07/Building-Garuda · **Local:** `C:\Users\hp\OneDrive\Desktop\acadflip\Building-Garuda`
- **Read in repo first:** `docs/GARUDA_BLUEPRINT.md` (engines §8.2 resolution, §8.3 MO), `docs/PHASE_2_RUNBOOK.md` + `docs/PHASE_3_RUNBOOK.md` (what's already built), `docs/CATALYST_CREDITS_AND_DEPLOYMENT.md` (**stay in the free Dev environment this phase — $0 credits**).
- **Stack:** React/Web Client Hosting · Node functions · **Python/FastAPI on AppSail** · Data Store (ZCQL) · QuickML (Qwen) · Zia.

## Where we are — Phases 1–3 DONE & merged to `main`
- **P1:** Catalyst project; Functions/Client/AppSail hello-world deploy; Auth; Stratus; Cache.
- **P2:** canonical schema (`schema/canonical_schema.yaml`); seeded synthetic generator (`data/generate.py`) → `data/synthetic/{incidents,entities,incident_edges}.csv` + **`data/synthetic/ground_truth.json`**; reference data + gazetteer; **adapter** (`ingestion/adapter/`). ~10,130 incidents / 14,608 entities / 18,214 edges. **Joins use Text business keys** (`incident_id`, `entity_id`) — NOT ROWID.
- **P3:** ingestion brain on AppSail — `app/routers/ingestion.py` (`/extract`, `/geocode`, `/promote`), `app/engines/extraction/`, **`app/engines/geocode/geocoder.py`** (already built), `app/engines/promote.py`; Review_Queue + confidence gate; rules-default extractor (Qwen opt-in, no credits). **Entity resolution is currently NAIVE** (`canonical_id == entity_id`) — *that's precisely what Phase 4 replaces.*

## Convention to follow (same as P2/P3)
**Split the work:** build a **pure-Python brain** verified locally against the P2 CSVs + `ground_truth.json` (no Catalyst creds, no credits), and keep **account-gated** steps (read/write Data Store via ZCQL, deploy AppSail) in a deferred section. Default to **local/free methods**; any QuickML/LLM use is opt-in via env. Produce a `docs/PHASE_4_RUNBOOK.md` at the end (like P2/P3).

## Phase 4 — Goal
Replace the naive mapping with real **entity resolution** (merge alias/variant mentions → one `canonical_id`) and **MO fingerprinting** (cluster incidents by modus operandi) — added to the existing AppSail service — with **precision measured against `ground_truth.json`**. This is the foundation for the Phase 5 co-offender graph (the hero).

## Exit Gate  (✅ = locally verifiable now · ⧖ = needs the live project)
- [ ] **G1** New engines `app/engines/resolution/` + `app/engines/mo/` (+ a router, e.g. `app/routers/analytics.py`); pure-Python, runnable locally on the P2 CSVs. ✅
- [ ] **G2** Resolution merges mentions → `canonical_id` + `match_confidence`; borderline pairs flagged for review (reuse the P3 confidence/review pattern), never silently merged. ✅
- [ ] **G3** **Resolution precision/recall/F1 measured vs `ground_truth.json`** and reported (target high precision, ≥0.9). ✅
- [ ] **G4** MO clustering writes `mo_cluster_id` to Incidents + populates `MO_Clusters` (each cluster has a signature). ✅
- [ ] **G5** **Planted gang resolves correctly** — members share `canonical_id`(s); the shared phone/vehicle remain single canonical entities linking the incidents across the 4 districts (BNU/KLR/RMN/TMK); the gang's incidents fall in coherent MO cluster(s) (verify vs `ground_truth.json`). ✅
- [ ] **G6** Deployed to AppSail Dev; a batch run writes `canonical_id`/`mo_cluster_id` back to Data Store via ZCQL. ⧖

## Prerequisites
Phase 1–3 outputs present (`python data/generate.py && python data/build_reference.py`). Add to `app/requirements.txt`: `scikit-learn hdbscan sentence-transformers rapidfuzz jellyfish indic-transliteration pandas zcatalyst-sdk-python` (+ `splink` or `recordlinkage`). All run locally/free — embeddings are local, **not** QuickML serving.

## Steps

### 1. Entity Resolution → `app/engines/resolution/`
- Load entities (locally from `data/synthetic/entities.csv`; in prod via ZCQL `SELECT ... FROM Entities`). Resolve **per `type`** (Person / Vehicle / Phone) separately.
- **Normalize:** lowercase, strip honorifics/punctuation; **transliterate Kannada↔English** (`indic-transliteration`) so script variants align; standardize phone/vehicle formats.
- **Phonetic keys:** Double Metaphone / NYSIIS (`jellyfish`) — plain Soundex is weak for Indian names.
- **Blocking (mandatory — ~15k entities, never all-pairs):** block by phonetic key + district, phone prefix, vehicle prefix.
- **Match within blocks:** `splink`/`recordlinkage` (Fellegi–Sunter) or weighted `rapidfuzz` (Jaro–Winkler on name + exact phone/vehicle + age/gender agreement) → pair scores.
- **Cluster** matched pairs (connected components) → one `canonical_id` per cluster; write `canonical_id` + `match_confidence` to Entities. Exact phone/vehicle = strong merge signal. **Borderline scores → review flag, never auto-merge.**

### 2. MO Fingerprinting → `app/engines/mo/`
- Per-incident feature = **embedding of `mo_text`** (sentence-transformers; multilingual model if `mo_text` contains Kannada, else MiniLM) **+ structured MO features** (hour-of-day bucket, weapon, target, entry method, crime_type — one-hot).
- **HDBSCAN** → `mo_cluster_id`; compute a **signature** per cluster (top TF-IDF terms + dominant structured features); write `mo_cluster_id` to Incidents and populate `MO_Clusters` (id, signature, top_terms, example_incident_ids).
- **Cost/perf:** precompute embeddings once and **store vectors** (NoSQL/Data Store) so re-runs + the Phase 7 copilot reuse them — don't re-embed every call.

### 3. Reuse — don't rebuild
- **Geocoding already exists** (`app/engines/geocode/geocoder.py`). Reuse it; only add a batch backfill for Incidents missing lat/long.
- Reuse the **Review_Queue + confidence** pattern from P3 for borderline merges.

### 4. Evaluate vs ground_truth.json → `tests/test_resolution.py`
- Mirror `tests/test_ingestion_pipeline.py`. Compare predicted `canonical_id` groupings to the planted groupings/alias variants in `ground_truth.json`; print **precision/recall/F1**. Assert: network members resolve to shared `canonical_id`(s); the **kingpin** is one entity across its 9/10 incidents; the **shared phone/vehicle** are single canonical entities spanning BNU/KLR/RMN/TMK; the gang's incidents land in coherent MO cluster(s).
- *If `ground_truth.json` lacks explicit alias-variant labels, add a small labeled alias set to the generator (a minor P2 addendum, keep the seed fixed) so resolution is measurable.*

### 5. Catalyst wiring (account-gated — deferred section)
- Batch endpoints on AppSail (e.g. `POST /resolve/run`, `/mo/run`) that read Entities/Incidents via ZCQL, run the brain, and write `canonical_id`/`mo_cluster_id` back (batched ~200). `catalyst deploy appsail`. (Schedule nightly via Job Scheduling in Phase 9.)

## Gotchas
- **Dev only — $0 credits.** Embeddings run locally (free); keep any Qwen use opt-in (`EXTRACTOR=qwen` pattern from P3).
- **Blocking is mandatory** — all-pairs on ~15k entities will blow up.
- **Never delete original Entities** — keep `alias_of`/lineage for audit; resolution *adds* `canonical_id`, it doesn't destroy mentions.
- **Don't auto-merge** low-confidence pairs — flag for human review (the legal/ethical posture *and* better accuracy).
- Joins/writes use **Text business keys** (P2 strategy), not ROWID.
- Phase 4 only produces **canonical entities + MO clusters** — building the graph is Phase 5.

## Out of scope (later phases)
Co-offender **graph + centrality + communities + crime-series + anomaly → Phase 5** · forecasting → P6 · copilot → P7 · frontend → P8.

## When done
Commit on `feat/phase-4-resolution` → PR → merge to `main`; write `docs/PHASE_4_RUNBOOK.md`; tick the exit gate; then ask for the **Phase 5 brief** — the co-offender **network hero reveal**.
