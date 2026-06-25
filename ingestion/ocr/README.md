# OCR step

FIR scans are converted to text by **Catalyst Zia OCR**
(`zia().extractOpticalCharacters`). The deployable wrapper lives **with the function
that uses it**, because Catalyst bundles each function folder independently (a
`require()` reaching outside the function dir would not deploy):

- [`functions/ingest-event/ocr.js`](../../functions/ingest-event/ocr.js) — Zia OCR wrapper, `ocrFile(app, path) -> text`
- [`functions/ingest-event/index.js`](../../functions/ingest-event/index.js) — Stratus event → OCR → AppSail `/extract` → `Review_Queue`

The local pipeline test (`tests/test_ingestion_pipeline.py`) **bypasses OCR** by
reading the ground-truth `.txt` rendered alongside each synthetic FIR `.png`
(`data/fir_samples/`), so extraction accuracy is measured independently of OCR
quality. Live Zia OCR is exercised only after the Catalyst wiring step (Phase 3
runbook → "Catalyst wiring", deferred).
