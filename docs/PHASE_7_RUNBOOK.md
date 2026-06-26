# GARUDA — Phase 7 (Intelligence Copilot / Hybrid RAG) Runbook

> Goal: plain-English Q&A over the FIR data with **mandatory source-FIR citations**
> and guardrails, via **hybrid retrieval** (structured ZCQL filters + semantic
> rerank) — never a black box, never an assertion of guilt.

Same split as P2–P6: the **build-side brain is done & locally verified** (branch
`feat/phase-7-copilot`); the **account-gated** `/copilot` deploy + Qwen/QuickML serving is
deferred. Everything local runs at **$0** — TF-IDF retrieval (scikit-learn), **no torch,
no credits**.

---

## 0. What's built (locally verified)

| Area | Files | Status |
|---|---|---|
| NL → structured query | [app/engines/copilot/nl2query.py](../app/engines/copilot/nl2query.py) | district / crime_type / vehicle / phone / date-range / time-of-day → filters + parameterized ZCQL |
| Semantic retrieval | [app/engines/copilot/retriever.py](../app/engines/copilot/retriever.py) | TF-IDF (word+char) cosine over narratives; `COPILOT_EMBEDDER=sbert` opt-in |
| Hybrid answer + guardrails | [app/engines/copilot/answer.py](../app/engines/copilot/answer.py) | fuse + rerank → extractive answer with **FIR citations**; refuse guilt / out-of-scope |
| Data access | [app/shared/store.py](../app/shared/store.py) | `fetch_incidents_copilot` + `write_audit_log` (CSV ↔ ZCQL) |
| AppSail endpoint | [app/routers/analytics.py](../app/routers/analytics.py) | `POST /copilot` (cached index; audits every query) |
| Local runner | [app/run_phase7.py](../app/run_phase7.py) | demo battery → cited answers + Audit_Log to `GARUDA_HOME` |
| Eval | [tests/test_copilot.py](../tests/test_copilot.py) | citation accuracy + guardrail + audit checks |

**Verified locally** (`python tests/test_copilot.py`, 10,130 incidents indexed):

- **Citation accuracy 39/39 = 100%** (target ≥0.9): every cited FIR genuinely satisfies the
  query's structured constraints (district + crime-type + date/time window).
- Sample: *"two-wheeler theft in BNU in March 2025"* → 72 hits (recovers the planted spike),
  top-10 cited; *"house burglary in Mysuru in May 2024"* → the planted series surfaces.
- **Guardrails:** *"is the accused guilty…"* → refused (`guilt_determination`);
  *"what is the weather today"* → refused (`out_of_scope`).
- **Audit:** every query (incl. refusals) appended to `Audit_Log` with filters + returned IDs.

---

## 1. Exit gates

| Gate | What | Status |
|---|---|---|
| **G1** | NL → structured filters → ZCQL/row selection over Incidents | ✅ local |
| **G2** | semantic retrieval over narratives; fuse + rerank with structured hits | ✅ local |
| **G3** | answers cite source FIR IDs; guardrail (no guilt) + refuse out-of-scope | ✅ local |
| **G4** | every query logged to `Audit_Log` | ✅ local / ⧖ prod table |
| **G5** | citation accuracy measured ≥0.9 | ✅ local (100%) |
| **G6** | deployed; `/copilot` live; Qwen via QuickML behind opt-in flag | ⧖ account-gated |

---

## 2. Method (and why)

- **Hybrid, not KB-RAG alone.** KB-RAG over 10k+ narratives drifts; structured filters
  (district/crime/date/time) give precision, semantic rerank gives recall over the
  free-text part. The structured set is the candidate pool; TF-IDF cosine reranks it.
- **$0 default.** TF-IDF (word + char n-grams) cosine is instant at 10k rows — no FAISS, no
  torch. `COPILOT_EMBEDDER=sbert` swaps in multilingual sentence-transformers (Kannada
  paraphrase) when wanted; `EXTRACTOR=qwen` / QuickML adds fluent prose — both **opt-in**.
- **Citations are mandatory.** Every claim carries `incident_id` + `fir_no` + `source_fir_url`;
  the answer is extractive over retrieved rows, so it can't fabricate links.
- **Guardrails.** Refuse guilt-determination phrasing; refuse unfiltered low-relevance
  (out-of-scope); always attach "surfaces records, does not determine guilt."
- **Longest-match crime typing.** "two-wheeler theft" must beat the substring "theft" — the
  matcher tries the longest canonical label first (the one bug found + fixed in eval).
- **Parameterized ZCQL.** `to_zcql` escapes values (no injection) for the prod path.

---

## 3. Run it locally ($0, no Catalyst)

```bash
python data/generate.py && python data/build_reference.py
python tests/test_copilot.py                 # gate test (citation accuracy + guardrails)
python app/run_phase7.py                      # demo battery
python app/run_phase7.py "robbery in Mysuru after 8pm"   # ad-hoc query
```

`Audit_Log` is appended to `GARUDA_HOME/audit_log.csv` (default `~/OneDrive/Desktop/garuda`).

## 4. REST contract (AppSail)

`POST /copilot` `{ "query": "...", "actor": "...", "role": "...", "top_k": 10 }` →
```json
{ "answer": "...", "citations": [{"incident_id","fir_no","district_code","crime_type",
  "occurred_at","source_fir_url","snippet","score"}], "filters": {...}, "zcql": "SELECT ...",
  "count": N, "refused": false, "guardrail": "..." }
```
Refusals return `{"refused": true, "reason": "guilt_determination|out_of_scope|no_match", ...}`.

## 5. Account-gated (G6 — when the project is live)

- `GARUDA_BACKEND=zcql` → structured filters run as real ZCQL over Incidents; `Audit_Log`
  rows `INSERT`ed. Semantic vectors can move to NoSQL (reuse Phase-4 embeddings).
- Set `EXTRACTOR=qwen` + spin up **QuickML (Qwen 2.5-14B)** *only for the demo* (top credit
  burner) for NL parsing + fluent answers; citations stay mandatory regardless.

## 6. Gotchas

- Keep QuickML serving **OFF by default** ($0); it's opt-in for the demo.
- On the **real** dataset, vehicles/phones live in `BriefFacts` free text (see
  `docs/DATASET_REAL_SCHEMA.md`) — the vehicle/phone filters match the narrative, and the
  semantic index runs over `BriefFacts`; keep the Phase-3 NER strong (and bilingual).
- TF-IDF is lexical; for synonym/paraphrase robustness flip on the SBERT embedder.

## 7. Next

Phase 8 (Frontend): the chat UI renders `/copilot` answers + citations; the map renders
`Predictive_Risk` (P6) and the force graph renders `/network` (P5).
