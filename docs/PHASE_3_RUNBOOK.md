# GARUDA — Phase 3 (Ingestion & Extraction) Runbook

> Goal: a raw FIR scan becomes structured, confidence-scored fields and lands in a
> **human-in-the-loop** review queue — never auto-written to canonical.
> Flow: **Stratus upload → Event Function → Zia OCR → AppSail `/extract` → Review_Queue
> → (human approves) → `/promote` → Incidents/Entities/Incident_Edges.**

Same split as before: the **build-side brain is done & locally verified** (on branch
`feat/phase-3-ingestion`); the **account-gated** Catalyst wiring (Stratus trigger, live
Zia OCR, deploy) is deferred and needs the live project from Phase 1.

---

## 0. What's built (locally verified)

| Area | Files | Status |
|---|---|---|
| Synthetic FIRs + golden key | [data/fir_samples/generate_firs.py](../data/fir_samples/generate_firs.py) → `*.txt`, `*.png`, `fir_key.json` | 40 docs (planted network/series/anomaly first) |
| Extraction schema + prompt | [ingestion/extraction/fir_schema.json](../ingestion/extraction/fir_schema.json), [prompt.md](../ingestion/extraction/prompt.md) | JSON-schema + Qwen prompt (few-shot) |
| Extractor (brain) | [app/engines/extraction/rules.py](../app/engines/extraction/rules.py), [qwen.py](../app/engines/extraction/qwen.py), [confidence.py](../app/engines/extraction/confidence.py) | rule-based default; `EXTRACTOR=qwen` switches; graceful fallback |
| Geocoder | [app/engines/geocode/geocoder.py](../app/engines/geocode/geocoder.py) | gazetteer exact → fuzzy → district centroid |
| Promote / Review_Queue | [app/engines/promote.py](../app/engines/promote.py) | review record + naive canonical mapping (entity res = P4) |
| AppSail endpoints | [app/routers/ingestion.py](../app/routers/ingestion.py) | `POST /extract`, `/geocode`, `/promote` |
| OCR wrapper (Zia) | [functions/ingest-event/ocr.js](../functions/ingest-event/ocr.js) | `zia().extractOpticalCharacters` |
| Event Function | [functions/ingest-event/index.js](../functions/ingest-event/index.js) | Stratus → OCR → `/extract` → Review_Queue insert |
| Circuit (optional) | [ingestion/circuits/fir_ingest.json](../ingestion/circuits/fir_ingest.json) | same flow with retries/dead-letter |
| REST review surface | [functions/api/index.js](../functions/api/index.js), [review.js](../functions/api/review.js) | `/review/pending`, `/review/approve`, `/review/reject` |
| Review UI | [client/review.html](../client/review.html), [review.js](../client/review.js) | list pending · low-conf flags · approve/reject |
| Local e2e test | [tests/test_ingestion_pipeline.py](../tests/test_ingestion_pipeline.py) | scores extraction vs the golden key |

**Verified locally** (`python tests/test_ingestion_pipeline.py`): across all 40 FIRs —
every scalar field **100%**, geocoded **100%**, persons **62/62**, vehicles **17/17**,
phones **10/10**; **40/40** queued `pending`; **218** canonical rows producible. The rule
extractor is the gate (no QuickML credits spent); Qwen is opt-in.

---

## 1. Exit gate (tick when ALL true)

- [ ] **G1** A raw FIR scan in the Stratus inbox bucket fires the ingest Event Function.
- [ ] **G2** Zia OCR returns text for an image FIR (and `.txt` passthrough works). ✅ *(wrapper built)*
- [ ] **G3** `/extract` returns fields + per-field confidence + a Review_Queue record. ✅ *(built & tested)*
- [ ] **G4** A Review_Queue row is written `pending` (no auto-promote). ✅ *(built & tested)*
- [ ] **G5** Review UI lists pending, flags low-confidence fields, and approve/reject work.
- [ ] **G6** Approve calls `/promote` and inserts Incidents/Entities/Incident_Edges; row → `approved`.

(G2–G4 are code-complete & locally verified; G1/G5/G6 need the live project + deploy.)

---

## 2. Prerequisites

```bash
pip install pandas faker pyyaml pillow      # FIR generator (pillow renders the .png)
# the extraction brain itself is pure-python (stdlib + the reference CSVs from Phase 2)
```

Phase 2 outputs must exist first (the FIR generator samples real incidents and the
geocoder/confidence read the reference data):

```bash
python data/generate.py && python data/build_reference.py
```

## 3. Run the local pipeline (G2–G4, no Catalyst)

```bash
python data/fir_samples/generate_firs.py     # -> data/fir_samples/*.txt|*.png + fir_key.json
python tests/test_ingestion_pipeline.py      # full brain over all 40 FIRs; prints accuracy, asserts gate
```

The test runs `extract → geocode → confidence → Review_Queue → promote` exactly as the
deployed code paths do (it imports the same `app/engines` modules), so a green run here
means the brain is correct independent of Catalyst.

## 4. How the pieces fit

```
 Stratus bucket (fir-inbox)
        │  object-create  (Signal / bucket trigger)
        ▼
 functions/ingest-event  ── Zia OCR ──▶ text
        │ POST {APPSAIL_BASE_URL}/extract
        ▼
 AppSail brain  ──▶ {extraction, field_confidences, review_record}
        │ datastore().table('Review_Queue').insertRow(...)
        ▼
 Review_Queue (status=pending)
        ▲  GET /review/pending
 client/review.html ── approve ──▶ functions/api /review/approve
        │ POST {APPSAIL_BASE_URL}/promote   (canonical mapping = single source of truth)
        ▼ datastore().insertRows(...)
 Incidents / Entities / Incident_Edges   +   Review_Queue.status=approved
```

- **Confidence gate:** `_overall = min(confidence of required fields)`; below
  `REVIEW_FLAG_THRESHOLD = 0.80` the UI flags "needs attention". We **never auto-skip the
  human** in Phase 3 — the flag only triages.
- **Entity resolution is naive here** (one entity per mention, `canonical_id == entity_id`);
  fuzzy/transliteration merge is Phase 4.
- **Extractor:** rule-based by default; set AppSail env `EXTRACTOR=qwen` to use the LLM
  (needs `QUICKML_ENDPOINT`, `QUICKML_TOKEN`). Qwen failures fall back to rules.

## 5. Catalyst wiring (account-gated — deferred, Task #22)

1. **Stratus bucket** — create `fir-inbox` for raw FIR scans (see Phase 1 runbook §Stratus).
2. **Deploy** — `catalyst deploy` ships `functions/api`, `functions/ingest-event`, the
   AppSail app, and the client. (First deploy installs `zcatalyst-sdk-node` for the functions.)
3. **Function env vars** — set `APPSAIL_BASE_URL` on **both** `api` and `ingest-event` to the
   deployed AppSail base (e.g. `https://<appsail>-<id>.development.catalystappsail.com`).
   For live LLM extraction set `EXTRACTOR=qwen`, `QUICKML_ENDPOINT`, `QUICKML_TOKEN` on AppSail.
4. **Bind the trigger** — wire the `fir-inbox` object-create event to the `ingest-event`
   function (Event Function, not the retired Event Listener). On the **first** firing, check
   the function logs for the printed raw event and confirm the bucket/key field names in
   `parseEvent()` match your Catalyst version.
5. **Client config** — set `apiBaseUrl` in [client/config.js](../client/config.js) (same-origin
   `/server/api` works) so `review.html` can reach the functions.
6. **Verify the gate:** upload a sample FIR (`data/fir_samples/<id>.png`, or `.txt` to skip
   OCR) to `fir-inbox` → a `pending` row appears in Review_Queue → open `review.html`, confirm
   fields/flags → **Approve** → Incidents/Entities/Incident_Edges gain rows and the queue row
   flips to `approved`.

> No live data leaves the project: Zia OCR and Data Store are in-tenant; Qwen/QuickML is the
> only optional external call and is off by default.

## 6. REST contract (functions/api)

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{status:"ok", phase:3}` |
| GET | `/review/pending` | — | `{rows:[{review_id, source_fir_url, extracted_json, field_confidences, status, created_at}]}` |
| POST | `/review/approve` | `{review_id, reviewer}` | `{ok, incident_id, counts:{Incidents,Entities,Incident_Edges}}` |
| POST | `/review/reject` | `{review_id, reviewer, reason?}` | `{ok}` |

AppSail (`/extract` `{text, source_fir_url?}`, `/geocode` `{place, district_code?}`,
`/promote` `{extraction, confidence?}`) is documented in
[app/routers/ingestion.py](../app/routers/ingestion.py).

## 7. Gotchas

- **Co-located function code:** Catalyst bundles each function folder on its own, so
  `ocr.js` lives **inside** `functions/ingest-event/` (a `require()` outside the folder
  won't deploy). `ingestion/ocr/` only documents the step.
- **Stratus event shape** isn't byte-stable across versions — `parseEvent()` tries the
  likely fields and logs the raw event once; confirm on first run.
- **`/tmp` is the only writable dir** in a function; the scan is downloaded there for OCR.
- **Empty values dropped on insert** (`clean()`), so typed (numeric/datetime) columns get
  null, not `""`.
- **ZCQL writes** use the table business keys; promote produces Text-keyed rows consistent
  with the Phase 2 FK strategy.
- **SDK pinned** to `zcatalyst-sdk-node ^3.4.0`; the Zia/Stratus/ZCQL/Datastore calls match
  that major. Confirm the Zia **OCR** model is enabled in the console.

## 8. When the exit gate is green
Commit, push, open the PR, tick G1–G6, then ask for the **Phase 4 brief** (Entity
Resolution & the canonical co-offender graph).
