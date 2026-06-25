# GARUDA — Phase 2 (Data Layer & Synthetic Dataset) Runbook

> Goal: canonical Data Store schema created · realistic synthetic Karnataka dataset
> (with planted patterns) generated · loaded through the **swap-ready adapter** with a
> validation gate · queryable via ZCQL. No ingestion/OCR (P3), ML (P4+) or real UI (P8).

Split as before: **build-side is done & locally verified** (on branch
`feat/phase-2-data-layer`); the **account-gated** steps (create tables, bulk-load,
ZCQL) need the live Catalyst project from Phase 1.

---

## 0. What's built (locally verified)

| Area | Files | Status |
|---|---|---|
| Canonical schema | [schema/canonical_schema.yaml](../schema/canonical_schema.yaml), [schema/create_tables.md](../schema/create_tables.md) | 5 core + 6 derived tables specified |
| Synthetic generator | [data/generator_config.yaml](../data/generator_config.yaml), [data/generate.py](../data/generate.py) | seeded; emits canonical CSVs + `ground_truth.json` |
| Reference data | [data/build_reference.py](../data/build_reference.py) → `data/reference/*`, `data/gazetteer/*` | IPC↔BNS, Census, Geo (GeoJSON-as-text), gazetteer |
| Adapter (swap point) | [ingestion/adapter/](../ingestion/adapter/) `column_map.synthetic.yaml`, `mapping.py`, `validate.py`, `loader.py` | map → gate → load; `--dry-run` verified on all tables |
| Profiling | [data/notebooks/profile.ipynb](../data/notebooks/profile.ipynb), `profiling.py` | runs on ANY file |

**Verified locally:** generator → 10,130 incidents / 14,608 entities / 18,214 edges,
31/31 districts, 60% BNS; all five tables pass the validation gate (Incidents code
coverage 100%); referential integrity holds; and the planted patterns are recoverable:

- **network** — shared phone & vehicle link the 10 chain-snatchings across **4 districts**
  (BNU, KLR, RMN, TMK); kingpin in **9/10** (centrality).
- **series** — 6 burglaries in MYS within **2.6 km / 6 days**.
- **anomalies** — BNU two-wheeler theft ×4.0, BNU burglary ×3.5, MYS two-wheeler ×3.5.
- **swap** — a renamed "KSP-style" file maps to canonical and passes the gate using only
  an alternate column-map.

---

## 1. Exit gate (tick when ALL true)

- [ ] **G1** All canonical tables exist (5 core populated; 6 derived created empty).
- [ ] **G2** Synthetic generator produces canonical CSVs + planted patterns + `ground_truth.json`. ✅ *(built)*
- [ ] **G3** Adapter loads CSV → validates → writes to Data Store, driven by the column map.
- [ ] **G4** Validation gate + profiling notebook run on any input file. ✅ *(built)*
- [ ] **G5** Reference data loaded (IPC↔BNS, Karnataka GeoJSON, Census, gazetteer).
- [ ] **G6** ZCQL smoke tests pass: counts sane, JOINs work, planted network recoverable.

(G2 and G4 are code-complete; the rest need the live project.)

---

## 2. Prerequisites

```bash
pip install pandas faker pyyaml            # generator + adapter (already used to verify)
pip install jupyter                        # to run the profiling notebook
pip install zcatalyst-sdk-python           # only for loader.py live writes (optional)
```

## 3. (Re)generate the data

```bash
python data/generate.py            # -> data/synthetic/{incidents,entities,incident_edges}.csv + ground_truth.json
python data/build_reference.py     # -> data/reference/{ipc_bns_map,census_2011,geo_boundaries}.csv + data/gazetteer/gazetteer.csv
```

Seed is fixed in `generator_config.yaml`, so `ground_truth.json` stays valid. Scale with
`--n-incidents 15000` if you want more (mind dev-tier quotas). The synthetic CSVs are
git-ignored (regenerable); `ground_truth.json` and the reference CSVs are committed.

## 4. Create the tables (G1)

Follow [schema/create_tables.md](../schema/create_tables.md): create the 5 core tables and
the 6 derived (empty). Catalyst auto-adds `ROWID/CREATORID/CREATEDTIME/MODIFIEDTIME`.

## 5. Load through the adapter (G3, G5)

Always dry-run first (no creds needed — maps, validates, emits a console-Import-ready CSV):

```bash
python ingestion/adapter/loader.py --source data/synthetic/incidents.csv \
    --map ingestion/adapter/column_map.synthetic.yaml --table Incidents --dry-run
```

Then load for real — **two options**:

- **Console Import (simplest):** Data Store → each table → Import the matching CSV
  (`incidents.csv`, `entities.csv`, `incident_edges.csv`, `census_2011.csv`→Socioeconomic,
  `geo_boundaries.csv`→Geo_Boundaries). Load parents (Incidents, Entities) before edges.
- **Adapter live write:** run `loader.py` (without `--dry-run`) where Catalyst creds exist
  (a Catalyst Job/AppSail). It batches ~200 rows. Use `--limit N` to respect dev quotas.

> Join columns in `Incident_Edges` are **Text business keys** (`incident_id`,`entity_id`),
> not ROWID FKs — so console Import and ZCQL joins work without a two-pass remap. See the
> FK note in `canonical_schema.yaml`.

## 6. Profile (G4)

```bash
jupyter notebook data/notebooks/profile.ipynb     # set SOURCE, Run All
```

## 7. ZCQL smoke tests (G6)

Run in the ZCQL console (full set in [schema/create_tables.md](../schema/create_tables.md)):

```sql
SELECT COUNT(ROWID) FROM Incidents;                              -- ~10,130
SELECT crime_type, COUNT(ROWID) FROM Incidents GROUP BY crime_type;
SELECT Incidents.crime_type, Entities.value FROM Incidents
  JOIN Incident_Edges ON Incident_Edges.incident_id = Incidents.incident_id
  JOIN Entities       ON Entities.entity_id = Incident_Edges.entity_id LIMIT 20;
```

**Planted-network reveal** — take `network.shared_phone` from
`data/synthetic/ground_truth.json` and confirm it spans ≥3 districts:

```sql
SELECT DISTINCT Incidents.district_code FROM Incidents
  JOIN Incident_Edges ON Incident_Edges.incident_id = Incidents.incident_id
  JOIN Entities       ON Entities.entity_id = Incident_Edges.entity_id
  WHERE Entities.value = '<network.shared_phone>';
```

## 8. Gotchas

- **Dev-tier row quotas:** 10k incidents (+~18k edges) is the default; use `--limit` or
  lower `n_incidents` if you hit caps. Edges are the largest table.
- **Keep the seed fixed** or regenerate `ground_truth.json` alongside the CSVs.
- **GeoJSON** is stored as **text** in `Geo_Boundaries.polygon`.
- **Bulk-write in batches** (~200) — the loader already does.
- District polygons/centroids are **representative**; swap precise official GeoJSON later
  (schema/loader/engines don't change).

## 9. When the exit gate is green
Commit, push, open the PR, tick G1–G6, then ask for the **Phase 3 brief** (Ingestion &
Extraction: `raw-fir` upload → Signal/Circuit → Zia OCR → AppSail `/extract` → Review_Queue).
