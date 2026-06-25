# ingestion/ — From messy reality to structured records (Track A/B · Phases 2–3)

The pipeline that turns scanned/photographed FIRs (and Excel dumps) into clean, structured, review-gated rows. Orchestrated by **Catalyst Circuits**, triggered by **Signals** on a Stratus upload.

## Subfolders
- `ocr/` — Zia OCR step (handles English + Kannada).
- `extraction/` — schema-constrained structured extraction (Qwen via QuickML) + NER → canonical JSON fields.
- `adapter/` — **the most important folder for dataset-readiness.** A configurable loader: `source file → column-map (config) → validate → canonical schema → bulk insert`. When the real KSP dataset arrives, **you only edit the column-map here** — nothing downstream changes. See [../docs/GARUDA_DATA_READINESS.md](../docs/GARUDA_DATA_READINESS.md).
- `circuits/` — Circuit definitions wiring the steps together (OCR → extract → geocode → validate → store).

## Flow
`raw-fir` (Stratus) → Signal → Event fn → OCR → extract → geocode → `Review_Queue` → human approve → `Incidents` + `Incident_Edges`.
