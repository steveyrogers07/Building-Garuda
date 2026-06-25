# GARUDA — Phase 4 (Entity Resolution & MO Fingerprinting) Runbook

> Goal: replace the naive `canonical_id == entity_id` mapping with real **entity
> resolution** (alias/variant mentions → one `canonical_id` + confidence) and **MO
> fingerprinting** (cluster incidents by modus operandi → `mo_cluster_id` + signatures),
> measured against `data/synthetic/ground_truth.json`. Foundation for the Phase-5
> co-offender graph.

Same split as P2/P3: the **build-side brain is done & locally verified** (on branch
`feat/phase-4-resolution`); the **account-gated** Catalyst write-back (ZCQL, deploy) is a
deferred section needing the live project from Phase 1. Everything local runs at **$0** —
embeddings are local (TF-IDF; sentence-transformers is opt-in), no QuickML credits spent.

---

## 0. What's built (locally verified)

| Area | Files | Status |
|---|---|---|
| Normalize / transliterate / phonetics | [app/engines/resolution/normalize.py](../app/engines/resolution/normalize.py) | Kannada→Latin, NYSIIS/Metaphone, phone/plate formats |
| Entity resolution (brain) | [app/engines/resolution/resolver.py](../app/engines/resolution/resolver.py) | blocking → weighted match → connected-components → `canonical_id` + `match_confidence` |
| MO structured features | [app/engines/mo/features.py](../app/engines/mo/features.py) | hour bucket, crime type, weapon/vehicle/entry/target cues |
| MO fingerprinting (brain) | [app/engines/mo/fingerprint.py](../app/engines/mo/fingerprint.py) | TF-IDF+SVD (or SBERT) + structured → HDBSCAN → signatures; vector cache |
| Batch data access | [app/shared/store.py](../app/shared/store.py) | local CSV (default) ↔ ZCQL (prod); Text business keys |
| AppSail endpoints | [app/routers/analytics.py](../app/routers/analytics.py) | `POST /resolve/run`, `/mo/run`, `/geocode/backfill` |
| Resolution eval | [tests/test_resolution.py](../tests/test_resolution.py) | precision/recall/F1 vs planted truth + gang (G5) |
| MO eval | [tests/test_mo.py](../tests/test_mo.py) | every incident clustered + gang lands in one coherent cluster |

**Verified locally** (`python tests/test_resolution.py && python tests/test_mo.py`):

- **Resolution (persons):** precision **0.946**, recall **0.896**, F1 **0.920** vs the
  planted alias groupings; **3,431** mentions merged into canonical entities; **1,052**
  borderline pairs flagged for review (never silently merged).
- **Gang (G5):** the shared phone `+916534933629` and vehicle `KA68MC3164` each stay a
  single canonical entity linking incidents across **BNU/RMN/TMK/KLR**; the kingpin
  *Aayush Zachariah* stays one entity (no wrong merge).
- **MO:** **167** clusters over 10,130 incidents (10.9% noise); the gang's **10/10**
  chain-snatchings land in one coherent `Chain snatching` cluster with a signature.

---

## 1. Exit gate (tick when ALL true)

- [x] **G1** New engines `app/engines/resolution/` + `app/engines/mo/` (+ router
  `app/routers/analytics.py`); pure-Python, runnable locally on the P2 CSVs. ✅
- [x] **G2** Resolution → `canonical_id` + `match_confidence`; borderline pairs flagged for
  review (reuses the P3 Review_Queue pattern), never silently merged. ✅
- [x] **G3** Resolution precision/recall/F1 vs `ground_truth.json` reported —
  **P=0.946 ≥ 0.90**. ✅
- [x] **G4** MO clustering writes `mo_cluster_id` to Incidents + populates `MO_Clusters`
  (each cluster has a signature: top terms + dominant structured features). ✅
- [x] **G5** Planted gang resolves correctly (shared phone/vehicle single canonical
  entities across 4 districts; kingpin one entity) and its incidents fall in one coherent
  MO cluster. ✅
- [ ] **G6** Deployed to AppSail Dev; a batch run writes `canonical_id`/`mo_cluster_id`
  back via ZCQL. ⧖ *(needs the live project — see §5)*

---

## 2. Prerequisites

```bash
pip install numpy scikit-learn rapidfuzz jellyfish indic-transliteration   # the brain
pip install pandas faker pyyaml                                            # data + tests
# opt-in only: sentence-transformers (MO_EMBEDDER=sbert), zcatalyst-sdk-python (ZCQL)
```

Phase 2 outputs must exist first (resolution/MO read the canonical CSVs):

```bash
python data/generate.py && python data/build_reference.py
```

## 3. Run the local pipeline (G1–G5, no Catalyst)

```bash
python tests/test_resolution.py    # prints precision/recall/F1; asserts P≥0.90 + gang (G5)
python tests/test_mo.py            # clusters all incidents; asserts gang coherence (G4/G5)
```

Both import the same `app/engines` modules the deployed endpoints use, so a green run here
means the brain is correct independent of Catalyst.

## 4. How it works

### 4.1 Entity resolution (`app/engines/resolution/`)
Per `type`, never all-pairs:

1. **Normalize + transliterate** — lowercase, strip honorifics/punctuation, transliterate
   Kannada→Latin so `ರವಿ ಕುಮಾರ್` aligns with `Ravi Kumar`; standardize phone/plate formats.
2. **Phonetic keys** — NYSIIS + Metaphone (better than Soundex for Indian names).
3. **Blocking (mandatory)** — multi-pass: last-name NYSIIS/Metaphone + first-name NYSIIS.
   An entity joins a block per key, so a variant that perturbs one name part still pairs.
4. **Match** — precision-first. Whole-name Jaro-Winkler over-merges (its prefix weighting
   scores any two people sharing a *first* name ≥0.9: "Jagat Bora" vs "Jagat Kari"). The
   planted variants **preserve the surname**, so a merge requires an **exact surname match**
   then strong first-name agreement (JW≥0.90, or same Metaphone for ph→f). The ambiguous
   initial form ("R. Kumar") is merged only when its `(surname, initial, gender)` maps to a
   single cluster — otherwise it goes to **review**. Vehicles/phones merge on exact
   normalized value.
5. **Cluster** — connected components → one `canonical_id` (the base record carrying age)
   + a `match_confidence`. Borderline pairs become `Review_Queue` records.

Tunables live at the top of `resolver.py` (`FIRST_MERGE`, `FIRST_META_FLOOR`,
`FIRST_REVIEW`, `AGE_GAP_SPLIT`).

### 4.2 MO fingerprinting (`app/engines/mo/`)
Per incident: a **text embedding** of `mo_text` (TF-IDF + TruncatedSVD by default; set
`MO_EMBEDDER=sbert` for sentence-transformers — multilingual if `mo_text` has Kannada) plus
**structured MO features** (hour bucket, crime type, weapon/vehicle/entry/target cues),
L2-normalized and concatenated. **HDBSCAN** → `mo_cluster_id` (`-1` noise → empty). Each
cluster gets a **signature** (top TF-IDF terms + dominant crime/hour + flag rates) and an
exemplar. Vectors are persisted (`data/synthetic/mo_vectors.npz`; Data Store in prod) so
re-runs and the Phase-7 copilot reuse them instead of re-embedding.

### 4.3 Reuse, not rebuild
- **Geocoder** (`app/engines/geocode/geocoder.py`) is reused by `/geocode/backfill` — only
  Incidents missing coords are geocoded (the synthetic set already has them).
- **Review_Queue + confidence** pattern from P3 is reused for borderline merges
  (`resolver.to_review_record` → the same columns as the ingestion review records).

## 5. Catalyst wiring (account-gated — deferred → G6)

The brain is backend-agnostic via `app/shared/store.py`:

1. **Deploy** — `catalyst deploy appsail` ships the updated AppSail app (adds
   `numpy/scikit-learn/rapidfuzz/jellyfish/indic-transliteration/zcatalyst-sdk-python`).
2. **Switch backend** — set AppSail env `GARUDA_BACKEND=zcql` so `store.py` reads
   Entities/Incidents from the Data Store and writes back via ZCQL (batched ~200, Text
   business keys, never ROWID).
3. **Run the batch** — `POST /resolve/run` then `POST /mo/run` (e.g.
   `{"write": true}`): resolution writes `canonical_id`/`match_confidence` to Entities and
   borderline pairs to `Review_Queue`; MO writes `mo_cluster_id` to Incidents and inserts
   `MO_Clusters`. Optionally `POST /geocode/backfill` first.
4. **Verify (G6)** — query a few `Entities`/`Incidents` rows and confirm `canonical_id` /
   `mo_cluster_id` are populated and `MO_Clusters` has signatures.

> Nightly scheduling of these batches comes in **Phase 9** (Job Scheduling). Original
> Entities are never deleted — resolution only *adds* `canonical_id`/`match_confidence`;
> `alias_of` lineage is preserved for audit.

## 6. REST contract (AppSail)

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/resolve/run` | `{write?, limit?}` | `{ok, stats, entities_written, review_records, review_total}` |
| POST | `/mo/run` | `{write?, limit?}` | `{ok, incidents, clusters, noise, ..., sample_signatures}` |
| POST | `/geocode/backfill` | `{write?, limit?}` | `{ok, scanned, backfilled, written}` |

`{write:false}` runs the brain without persisting (smoke test); `limit` caps rows.

## 7. Gotchas

- **Dev only — $0 credits.** Embeddings run locally; keep SBERT/Qwen opt-in.
- **Blocking is mandatory** — all-pairs over ~15k entities blows up. Surname-anchored
  matching also prevents first-name *chaining* blobs (the main precision trap here).
- **Don't auto-merge ambiguous pairs** — initials and weak matches go to `Review_Queue`.
- **Never delete Entities** — resolution adds `canonical_id`; `alias_of` lineage stays.
- **Text business keys, not ROWID**, for all reads/writes (P2 strategy).
- Phase 4 produces **canonical entities + MO clusters only** — the co-offender **graph** is
  Phase 5.

## 8. When the exit gate is green
Commit on `feat/phase-4-resolution`, open the PR, merge to `main`, tick G1–G5 (G6 after
deploy), then ask for the **Phase 5 brief** — the co-offender **network hero reveal**.
