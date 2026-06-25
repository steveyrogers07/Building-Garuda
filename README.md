# GARUDA — AI Crime Intelligence Platform

> **Karnataka State Crime Records Bureau · Datathon 2026**
> A unified analytics platform that turns scattered FIRs into actionable intelligence —
> automated ingestion, entity resolution, co-offender networks, crime-series linkage and
> emerging-trend alerts — engineered to deploy on **Zoho Catalyst**.

**Author:** [@steveyrogers07](https://github.com/steveyrogers07) · built with **Claude** (Anthropic) as an AI pair‑programmer.

---

## What it does

GARUDA ingests scanned FIRs, extracts structured records (OCR + rule/LLM extraction),
resolves fragmented mentions into canonical people / vehicles / phones, and runs the core
analytics that make crime data actionable:

- **Co‑offender network** — siloed FIRs become one visible criminal network; surfaces the
  **kingpin** (centrality), the **gang** (community detection) and **cross‑district rings**
  (a shared burner phone or number‑plate reused across jurisdictions).
- **Crime‑series linkage** — the same offenders striking again, via MO + space‑time
  near‑repeat (Knox‑style).
- **Emerging‑trend anomalies** — robust per‑area × crime spike detection → alerts.

Everything is built and verified against a **synthetic Karnataka dataset** (50k+ incidents
with a planted gang / series / spikes as ground truth), so the real KSP data slots in later
**without engine changes**.

## Build status (phased)

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation & scaffold (Catalyst Functions / Client / AppSail) | ✅ done |
| 2 | Canonical data layer + synthetic generator + adapter | ✅ done |
| 3 | Ingestion & extraction (OCR → extract → confidence → review) | ✅ done |
| 4 | Entity resolution + MO fingerprinting (`canonical_id`, `mo_cluster_id`) | ✅ done |
| 5 | Core analytics: co‑offender network + crime‑series + anomaly ★ | ✅ done |
| 6–10 | Predictive AI · Copilot (RAG) · Frontend · Automation · Deploy | ⏳ planned |

The repo is organised as one `feat/phase-N-*` branch per phase — build/verify each, then
merge into `main`.

## Run it locally ($0, no Catalyst account)

```bash
# 1) generate the synthetic dataset
python data/generate.py

# 2) Phase-5 analytics — the hero reveal (network + series + anomalies)
python tests/test_network.py     # gate test vs planted ground truth
python app/run_phase5.py         # full run -> writes artifacts + prints the reveal
```

Phase‑5 artifacts are written to `GARUDA_HOME` (default `~/OneDrive/Desktop/garuda`).

## Architecture

- **Python / FastAPI on AppSail** — the ML brain (`app/engines`, `app/routers`).
- **Node Functions** — thin ingestion glue (Stratus → OCR → extract → review).
- **Web Client Hosting** — the frontend (Phase 8).
- **Data Store (ZCQL)** — canonical tables; **NoSQL / Cache** for hot analytics.

Engines run locally on CSVs at **$0** and switch to the Catalyst Data Store via
`GARUDA_BACKEND=zcql` for deployment — no engine changes.

## Tech

Zoho Catalyst (Functions · AppSail · Data Store · Stratus · Zia OCR · QuickML · Signals ·
Cache · API Gateway · Job Scheduling) · Python (FastAPI, networkx, scikit‑learn,
statsmodels) · Node.

## Docs

See [`docs/`](docs/) — the blueprint, the 10‑phase plan, and per‑phase runbooks.

---

© [@steveyrogers07](https://github.com/steveyrogers07). Built with Claude.
