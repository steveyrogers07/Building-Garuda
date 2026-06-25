# GARUDA — Phase 7 Kickoff (paste into a fresh build chat)

> Fresh build session for **Phase 7** of GARUDA. Read fully, execute step by step, don't jump ahead.

## Context
**GARUDA** — AI crime-analytics for Karnataka SCRB, Datathon 2026, on Zoho Catalyst.
- Repo: https://github.com/steveyrogers07/Building-Garuda · Local: `…/Building-Garuda`
- Read: `docs/GARUDA_BLUEPRINT.md` (§ copilot — **hybrid RAG, not KB-RAG alone**), `docs/PHASE_2_RUNBOOK.md`, `docs/CATALYST_CREDITS_AND_DEPLOYMENT.md` (**Dev only, $0; QuickML LLM serving is opt-in/credit-costly — keep OFF by default**).
- Stack: Node functions · **Python/FastAPI on AppSail** · Data Store (ZCQL + full-text) · **QuickML (Qwen 2.5-14B)** · NoSQL (vectors).

## Dependency — mostly parallel NOW
Core (NL→ZCQL + retrieval) depends only on **Phase 2 data**. The semantic layer **reuses Phase 4 embeddings** if available (else build a local vector index). Can start now; enrich answers with P5/P6 outputs as they land.

## Convention
Pure-Python brain verified locally + deferred account-gated. **Rules/extractive default (no credits); Qwen via QuickML opt-in via env** (`EXTRACTOR=qwen` pattern from P3). Text business keys. Produce `docs/PHASE_7_RUNBOOK.md`.

## Goal
A plain-English copilot that answers over the data **with mandatory source-FIR citations** and guardrails — via **hybrid retrieval** (structured filters + semantic), never a black box.

## Exit Gate (✅ local · ⧖ live)
- [ ] **G1** `app/engines/copilot/`: NL query → **structured filters → ZCQL** over Incidents (district, crime_type, vehicle/phone, date range, time-of-day). ✅
- [ ] **G2** **Semantic retrieval** over `mo_text`/narratives via embeddings (reuse P4 vectors in NoSQL, or a local FAISS/sqlite-vec index); fuse + rerank with the structured hits. ✅
- [ ] **G3** Answer returns **source FIR IDs as citations**; **guardrail**: surfaces records, never asserts guilt; refuses out-of-scope. ✅
- [ ] **G4** Every query logged to `Audit_Log`. ✅(local) / ⧖(prod table)
- [ ] **G5** **Citation accuracy measured** on a battery of sample queries (target ≥0.9). ✅
- [ ] **G6** Deployed; `/copilot` live; Qwen generation via QuickML behind the opt-in flag. ⧖

## Prerequisites
`pip install sentence-transformers faiss-cpu rapidfuzz pandas` (+ optional `sqlite-vec`). Phase 2 outputs present. (Reuse P4 embeddings if merged.)

## Steps
1. **NL→ZCQL → `app/engines/copilot/nl2query.py`**: parse the query into structured filters (rules/regex + optional Qwen) → a safe parameterized ZCQL `SELECT` over Incidents/Entities.
2. **Semantic → `retriever.py`**: embed query, top-k over narrative embeddings; **fuse** with the structured result set + **rerank**.
3. **Generation → `answer.py`**: default = extractive/templated answer (no credits) summarizing the retrieved rows **with FIR citations**; opt-in Qwen (QuickML) for fluent prose (env-gated). Always attach `source_fir_url`/`incident_id` citations. Guardrail prompt: "surface records, never assert guilt."
4. **Audit:** write each query + filters + returned IDs to `Audit_Log`.
5. **Eval → `tests/test_copilot.py`**: sample queries (e.g., "chain-snatching, blue Pulsar, South Bengaluru, after 8pm") → assert correct filtered rows + citation accuracy.
6. **Account-gated:** `/copilot` endpoint; QuickML LLM serving (Qwen) wired behind the opt-in flag (spin up only for demo per the credits doc).

## Gotchas
Dev only ($0) — **keep QuickML serving OFF by default** (it's the #1 credit burner; opt-in for demo). KB-RAG alone won't scale to 10k+ records → **hybrid** is mandatory. Never fabricate links; every claim cites a FIR. Parameterize ZCQL (no injection).

## Out of scope
Network → P5 · forecasting → P6 · the chat UI → P8 (this phase is the `/copilot` API).

## When done
`feat/phase-7-copilot` → PR → `main`; write `docs/PHASE_7_RUNBOOK.md`.
