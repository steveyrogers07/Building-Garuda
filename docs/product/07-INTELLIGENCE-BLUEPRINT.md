# GARUDA — Intelligence Capability Blueprint

> The definitive catalogue of everything GARUDA should *do* to be a genuine
> police-grade intelligence platform — not a crime dashboard. Every capability is
> tied to (a) a real Karnataka police workflow, (b) the organizer's actual FIR
> schema (`docs/DATASET_REAL_SCHEMA.md`), and (c) what is buildable on **Zoho
> Catalyst at $0**. Use this as the backlog to build upon iteration by iteration.
>
> **Companion to** the 7 product specs in this folder. This is the "make it
> stand out and be intelligent enough for police" master list.

---

## 0. The one idea that separates a winner from a dashboard

Every other team will show **counts** — "here are 10,000 FIRs on a map, filtered by
district and crime type." That is a *report*. Police do not need a prettier report;
they have those.

**GARUDA's thesis: the system does the analyst's connective thinking automatically.**
When an officer looks at *anything* — a case, a name, a phone, a place — the system
immediately surfaces **everything it is connected to and what that means**: the past
cases that rhyme with it, the people behind it and their shared history, the officers
who cracked similar cases, the pattern it belongs to, and the most probable next move.

That is the difference between a database you *query* and an analyst you *consult*.
The rest of this document is how you get there.

**Design law for the whole system:** *no dead ends, and nothing is just a number.*
Every entity is a clickable object; every object carries its context, its
connections, and its "so what." Everything is explainable and cited. The system
**surfaces and predicts — it never asserts guilt.**

---

## 1. Your 17 ideas — honest triage against Catalyst + $0

These are strong instincts. But GARUDA is judged on **Zoho Catalyst** with a **basic
(≈$0) plan**, so several of your ideas as-worded (Neo4j, Pinecone, Redis/Celery, n8n,
Mapbox paid tier) would either cost money, need external infra the judges can't see
running, or duplicate a Catalyst-native service. The trick that wins: **deliver the
*capability* every idea points at, using the Catalyst-native equivalent.** Judges
reward "you used the platform deeply and correctly," not "you bolted on 6 external
SaaS."

| # | Your idea | Verdict | GARUDA / Catalyst way to deliver the same capability |
|---|---|---|---|
| 1 | Async task queues (Redis/Celery) | **Adapt** | **Catalyst Job Scheduling + Event Functions** (already Phase 9). Heavy FIR batches, PDF/brief generation, bulk alerts run as scheduled/triggered jobs — same "don't make the user wait," native. |
| 2 | Graph DB (Neo4j) | **Adapt** | The **network engine (networkx) + NoSQL adjacency cache** already gives co-offender graphs, centrality, communities, link-prediction. A separate Neo4j is cost + ops the judges can't see. Keep the graph *in-engine*, persist adjacency to **NoSQL**. (Note it in the "future scale" slide — you know when it's warranted.) |
| 3 | On-prem / edge LLM (privacy) | **Adopt (already the design)** | This is exactly why the copilot defaults to **local TF-IDF + rules ($0, no data leaves)** and only optionally calls **QuickML/Qwen** *inside Catalyst*. Frame it loudly: "police data never touches an external API." Huge trust point. |
| 4 | Workflow automation (n8n/Make) | **Adapt** | **Signals + Event Functions + Job Scheduling** are the internal workflow engine (spike → alert → notify → task). Native, auditable, no external webhook surface. |
| 5 | Vector DB (Pinecone/Milvus) | **Adapt** | Semantic search is already there via **TF-IDF now, embeddings-in-NoSQL at scale**. "guy on red bike snatching chains" → semantic match is a *headline demo*. Pinecone = external cost; NoSQL vectors = native. |
| 6 | Immutable audit logs | **Adopt (built, Phase 9)** | Append-only `Audit_Log`, every privileged read/query logged with actor+role+ts. Make it a **visible screen** (see §I). |
| 7 | Rate limiting / DDoS | **Adopt** | **API Gateway throttling** — native, one config. Mention for the citizen-facing portal (§G8). |
| 8 | Strict RBAC w/ JWT scopes | **Adopt (built + deepen)** | Catalyst **Authentication** + jurisdiction scopes; deepen into the **clearance-tier model** in §F. This is a must-win area. |
| 9 | Automated PII scrubbing pipeline | **Adopt (built + deepen)** | Field-level masking middleware (Phase 9), extend to a real **classification + redaction pipeline** (§I2) incl. IPC 228A/POCSO. |
| 10 | PWA + offline service worker | **Adopt (high value)** | Field officers hit dead zones. A **PWA that caches dossiers/BOLO and background-syncs incident logging** is a genuine police need and a great demo. Catalyst Web Client Hosting serves it. (§J6) |
| 11 | Companion browser extension | **Defer / optional** | Cool for detectives (highlight a name → run against GARUDA) but a side-quest for a hackathon; note as roadmap. |
| 12 | WASM client-side face/plate blur | **Adopt (narrow, brilliant)** | Blur faces/plates in the browser **before upload** → privacy + bandwidth. Strong ethics story for the ingestion demo. (§H4) |
| 13 | WebGL map clustering (deck.gl) | **Adopt** | The map must not die at 10k points. **deck.gl/MapLibre WebGL clustering** on deploy; the current SVG symbol map is the $0 stand-in. (§J4) |
| 14 | Cursor-based pagination | **Adopt** | Every list (cases, audit, search) uses cursor paging — smooth infinite scroll over 10⁵ rows. Backend detail, real polish. |
| 15 | Optimistic UI updates | **Adopt** | Save/assign/acknowledge reflect instantly, reconcile on response. Makes it feel like a tool, not a form. |
| 16 | E2E-encrypted citizen tip portal | **Adopt (standout)** | Client-side public-key encryption of tips; only authorized KSP officers decrypt. A **civic-trust feature no other team will have.** (§G8) |
| 17 | Skeleton loaders | **Adopt (done)** | Already in the design system. Perceived-performance basics. |

**Net:** ~13 of 17 land directly, delivered the Catalyst-native way. The 4 deferred are
noted so you *sound* like you know enterprise architecture (you do) without burning the
hackathon on infra the judges can't run.

---

## 2. Capability map (what to build, by area)

Legend: **[BUILT]** exists in the repo · **[DEEPEN]** partial, extend · **[NEW]** to add.
Priority: **P0** = hackathon-defining · **P1** = strong differentiator · **P2** = polish/roadmap.

The rest of this document is the detail behind each area A–K.

---

## A. Contextual Intelligence — "search shows you everything related" (P0, the hero)

The single most important capability. When an officer opens *anything*, GARUDA runs the
connective analysis a good crime analyst would spend a day on — instantly.

### A1. "Cases like this one" — similar-case retrieval **[DEEPEN → NEW]**
On any FIR, a panel of the 10 most similar past cases, each with **why** and a confidence:
- **Same MO** (weapon, entry, target, time-of-day) via the MO fingerprint.
- **Semantic narrative match** ("chain snatched, fled on two-wheeler") via the vector index — catches what keyword search misses.
- **Same section(s)** (`ActSectionAssociation`) / same crime sub-head.
- **Space-time near-repeat** (same locality, window). Click any → its file.
> *Why police care:* the fastest lead is "who did this exact thing before, near here."

### A2. "How the people here connect to the past" — entity back-history **[DEEPEN]**
For every person/vehicle/phone on the case, inline: prior appearances, prior roles
(witness in 2023, accused in 2024), known associates, and whether any associate ties to
THIS case's location/MO. Surface it **on the case file**, not just the dossier.

### A3. Auto-generated case context brief **[NEW — the "it thinks" moment]**
The instant a case opens, a 4-line copilot-written narrative from structured facts +
links: *"This chain-snatching (BNU, 21:40) shares vehicle KA68MC3164 with 9 other FIRs
across 4 districts; lead accused appears in all; pattern matches the cross-district ring
flagged 2024-06; two associates have prior snatching FIRs in RMN."* — every clause cited.

### A4. Connection explorer / path-finding **[DEEPEN]**
"How is A connected to B / to this address / to this phone?" → shortest path(s) through
the network, each hop's evidence (shared FIR, shared vehicle, call record). You have the
graph; add path queries.

### A5. "Related everything," ranked **[NEW]**
A universal *Related* rail on every object — cases, people, vehicles, phones, places,
series, alerts — ranked by connection strength with the reason. The web you pull on.

---

## B. District & Jurisdiction Intelligence (P0/P1)

Past choropleths into **command intelligence per jurisdiction**, using the real hierarchy
(`State → District → Unit/Station`, `Employee`, `CaseStatus`, `ChargesheetDetails`).

### B1. District Command Card **[BUILT]** — the SP's cockpit, one per district
(`app/engines/district.py`, `GET /district/{code}/command`, `client-react` District Command page):
- Load, open vs disposed, **backlog aging** (open cases past a threshold relative to the
  dataset's own timeline, not wall-clock) — done.
- **Clearance rate** (from `Chargesheets.cs_type` A/B/C, sourced from the organizer's
  `ChargesheetDetails`) — the metric that actually rates a district. It sat unused in the
  schema; nobody else was computing it — done.
- Top crime mix + an **officer leaderboard** (case load + own clearance rate, from the new
  `Officers` table / organizer `Employee`) — done. Active series/rings touching the district and
  true conviction (vs. chargesheet-filed) still open — needs `ArrestSurrender`/court-outcome
  data (see [08 — Field-Officer Intelligence §9](08-FIELD-OFFICER-INTELLIGENCE.md)).

### B2. District comparison & ranking **[BUILT — partial]** — `GET /district/rank` returns all 31
ranked by clearance rate, surfaced statewide in the District Command page. Response lag
(`InfoReceivedPSDate − IncidentFromDate`), repeat-offender density and socioeconomic overlay
still open. The DGP's real question: *who's improving, who's slipping, why.*

### B3. Cross-jurisdiction coordination view **[NEW]** — when a ring spans BNU/RMN/TMK/KLR:
which SPs/stations are involved, which officers worked linked cases, one-click **notify
involved jurisdictions**. The operational payoff of the network reveal.

### B4. Beat/station heat & resource-vs-load **[NEW]** — load per station vs officers assigned
(`Employee.UnitID`) → where is under-resourced relative to crime. Feeds patrol tasking.

### B5. Response-time & process analytics **[NEW]** — registration lag, time-to-chargesheet,
where cases stall. Process intelligence, not just crime intelligence.

---

## C. Person / Entity 360 + Predictive (P0/P1)

### C1. Full criminal-history timeline **[DEEPEN]** — every appearance by role, arrests
(`ArrestSurrender`), chargesheets, court outcomes. The career arc, not just a count.
### C2. Associates network, strength × recency **[BUILT → DEEPEN]** — co-offenders weighted by
recency; flag associates on a watchlist or in an active ring; predict hidden ties (Adamic-Adar).
### C3. Recidivism / escalation signal **[NEW, careful]** — transparent **components with
drivers**, never a single opaque "threat score" on a person. Ethics = credibility.
### C4. "What we don't know" gaps **[NEW]** — dossier flags missing links ("phone in 3 FIRs, no
owner resolved") to direct investigation instead of faking completeness.
### C5. Vehicle & phone dossiers **[BUILT]** — the reused burner phone across 4 districts is your
money demo.

---

## D. Copilot as an Intelligence Analyst (P0)

From "search with citations" to **"ask anything an analyst could, and it reasons over the
connections."** Cited, guardrailed, $0 by default (rules + retrieval), optional Qwen-in-Catalyst.

### D1. Person/entity history Q&A **[DEEPEN]** — "Everything on Aayush Zachariah" → dossier as
cited prose. "Has this phone appeared with other accused?" → yes, listed, cited.
### D2. Investigative reasoning & next-steps **[NEW — the standout]** — "What next on this case?"
→ proposes **leads, not verdicts**: recover CCTV from the 3 linked localities; check associate's
alibi; pull the shared phone's CDR. Responsibly "predict what police should head into."
### D3. "Who worked cases like this" **[NEW]** — from `created_by`/`Employee`/chargesheet outcomes,
surface officers/teams with a track record on similar patterns → staff the case with proven hands.
(4,199 officers already in the data — buildable now.)
### D4. Comparative/aggregate Q&A + NL→chart **[DEEPEN]** — "compare two-wheeler theft BNU vs MYS" →
answer + auto-chart + citations.
### D5. Predictive questions (places & times, never people) **[DEEPEN]** — "where is snatching likely
next week?" → forecast + SHAP + fairness caveat.
### D6. Guardrails & refusals, made visible **[BUILT]** — refuses guilt/out-of-scope; every answer
carries the "surfaces records, not guilt" line + citations + audit entry.

---

## E. Investigation & Case Management (P1) — teams, workflow, the daily tool

### E1. Officer & team intelligence **[NEW]** — officer profile: cases handled, crime types they
clear most, clearance rate, current load. **"Assign the officer with the best track record on this
MO."** Team view = everyone who touched a linked case.
### E2. Case workspace / investigation board **[NEW]** — assignee, status transitions, notes, tasks,
evidence checklist, linked-case pins. Optimistic UI on every action (idea #15).
### E3. Case-linking → "form an operation" **[DEEPEN]** — above a strength threshold, suggest a joint
operation/series case with involved stations pre-filled. Insight → action.
### E4. Handover & continuity **[NEW]** — transfer with full audit; new officer inherits the
auto-context brief so nothing is lost.
### E5. Court & prosecution tracking **[NEW]** — chargesheet due-dates, court dates, outcomes,
conviction analytics. Closes the FIR → verdict loop.

---

## F. Security Clearance / Access Tiers (P0) — not overkill; a credibility requirement

Model as **clearance tier × jurisdiction scope × purpose**, enforced server-side, shown live
(the role switcher that redacts PII in front of judges is already a highlight).

### F1. Clearance tiers **[BUILT → DEEPEN]**
| Tier | Role | Sees | Cannot |
|---|---|---|---|
| L1 | Constable / station staff | own-station cases, BOLO hits | other jurisdictions; victim PII outside station |
| L2 | SHO / IO | station + assigned cases, full in-jurisdiction parties | out-of-jurisdiction PII |
| L3 | Cyber Cell / specialized unit | their crime class statewide | unrelated-class PII |
| L4 | SP / District | full district incl. dossiers, tasking | other districts' PII (aggregate only) |
| L5 | ADGP / DGP / SCRB-admin | statewide, all dossiers, model cards | — (**fully audited**) |
| — | Analyst | statewide **patterns**, PII-masked | victim identities (sees "A. M.") |
| — | Ethics / Oversight | audit, fairness, model cards | case PII entirely |

### F2. Statutory hard-mask overrides tier **[BUILT]** — IPC **228A** / **POCSO** victim identity
withheld from all but the assigned case officer + admin, specially audited.
### F3. Purpose-bound access + **break-glass** **[NEW]** — sensitive reads state a logged purpose;
emergency access requires justification + flags the audit + notifies a supervisor. How real
intel systems work.
### F4. Field-level redaction pipeline **[DEEPEN]** — classify every field High/Med/Low PII, redact
per tier before data leaves the brain (idea #9).
### F5. Session/device posture **[P2]** — re-auth for PII on mobile; shorter sessions for high tiers.

---

## G. Proactive & Operational Loop (P1)

- **G1 Watchlists / BOLO with auto-match** **[NEW]** — plate/phone/person; new FIRs auto-matched;
  hit → alert with context; legal-basis + expiry; audited.
- **G2 Alert workflow** **[DEEPEN]** — `open → acknowledged → assigned → resolved`, jurisdiction-routed, audited.
- **G3 Patrol tasking from forecast** **[DEEPEN]** — top-risk cells → suggested allocation (PAI shown), **human approves**, places-not-people.
- **G4 Near-repeat early warning** **[NEW]** — after a burglary, flag the elevated neighbouring area/window for preventive patrol.
- **G5 Scheduled intelligence briefs** **[BUILT]** — nightly recompute + weekly DGP PDF (SmartBrowz→Stratus→Mail).
- **G6 Real-time notifications** **[DEEPEN]** — Signal → Push/Mail to the right officer.
- **G7 Duplicate / Zero-FIR detection** **[NEW]** — flag likely duplicates & cross-jurisdiction Zero-FIRs (`CrimeNo` category digit) for routing.
- **G8 Citizen E2E-encrypted tip portal** **[NEW, civic standout]** — client-side encrypted tips (idea #16); only authorized officers decrypt; matchable to open cases; API-Gateway rate-limited (idea #7).

---

## H. Ingestion, Extraction & Data Quality (P1)

- **H1** FIR OCR → extract → **human review queue** **[BUILT]** (Eng + Kannada).
- **H2** `BriefFacts` NER — **the crown jewel** **[DEEPEN]**: the real schema has **no structured
  phone/vehicle**; they live in narrative. The extractor that pulls plates/phones/weapons/MO from
  `BriefFacts` (incl. Kannada) **feeds the entire network**. The real-data lifeline — invest here.
- **H3** Confidence-gated auto-vs-review **[BUILT]** — nothing canonical without approval.
- **H4** Client-side face/plate blur before upload (WASM) **[NEW]** — privacy + bandwidth (idea #12).
- **H5** Data-quality dashboard **[NEW]** — completeness/confidence by field & district.
- **H6** Real-data adapter **[BUILT]** — column-map to KSP schema, swap with no engine change.
- **H7** Dedup & entity-resolution review **[DEEPEN]** — borderline merges to a human, lineage preserved.

---

## I. Governance, Ethics & Audit (P0) — the trust moat

- **I1** Immutable audit log, **as a visible screen** **[BUILT → DEEPEN]** (idea #6).
- **I2** PII classification + redaction pipeline **[DEEPEN]** (idea #9; see §F4).
- **I3** Model cards + fairness dashboard **[DEEPEN]** — purpose/data/metrics/limits; ward over-prediction surfaced.
- **I4** "Explain this" everywhere **[BUILT]** — SHAP, link-reasons, citations. Unexplainable ⇒ doesn't ship.
- **I5** No protected attributes as features **[BUILT]** — caste/religion/gender never used; stated in model card.
- **I6** Presumption of innocence in the UI **[BUILT]** — accused = "as recorded, pending trial."
- **I7** Retention & lineage **[NEW]** — Stratus scan retention; `source_fir_url` lineage on every row.

---

## J. Frontend & UX — a real, developed app with KSP branding (P0)

> *"A good-ass developed app, not filmy AI-generated shit — well-thought UI/UX with KSP logo &
> branding."* The dark SOC console is the right base; here's how it becomes unmistakably an
> official product.

- **J1 KSP official branding & identity** **[NEW]** — the **Karnataka State Police crest** in
  sidebar + login + PDF header (official crest, correct clear-space/proportions, no recolor);
  wordmark "Karnataka State Police · SCRB"; "GARUDA" (the eagle) as the platform name; a
  government-grade **login/landing** (crest, system name, clearance notice, secure sign-in,
  classification banner); consistent authority-blue + amber system, Fira type, real iconography.
- **J2 Engineered IA** **[DEEPEN]** — grouped nav, **workspace tabs** (built), **Ctrl-K palette**
  (built), breadcrumbs, deep links; ≤2 clicks to anything. Feels like an IDE for investigations.
- **J3 Density done right** **[BUILT]** — KPI cards, tabular tables, side-by-side detail; group with
  whitespace/rules, not boxes-in-boxes.
- **J4 Map that scales** **[DEEPEN]** — MapLibre + deck.gl WebGL clustering, layer toggles, time-slider
  playback (idea #13); no API key. SVG symbol map is the $0 stand-in.
- **J5 Real data-viz** **[DEEPEN]** — force-graph (built), timelines, small-multiples, sparklines;
  legend/tooltip/table-fallback; color never the only signal.
- **J6 PWA + offline field mode** **[NEW]** — installable, caches dossiers/BOLO, logs incidents offline
  + background-sync (idea #10).
- **J7 Perceived performance** **[BUILT/DEEPEN]** — skeletons (idea #17), optimistic updates (#15),
  cursor pagination (#14), sub-second cached reads.
- **J8 Accessibility & bilingual** **[DEEPEN]** — WCAG AA, keyboard-complete, Kannada UI + content.
- **J9 Designed states** **[BUILT]** — loading/empty/error/**403 "switch clearance to compare"/404/offline**. No blank screens.
- **J10 Guided demo mode** **[NEW]** — a spotlighted walk of the hero loop for judges.

---

## K. Infrastructure & Non-Functionals — the Catalyst-native way (P1)

| Need (your list) | Catalyst-native delivery |
|---|---|
| Background jobs / queues (#1) | **Job Scheduling** pool + **Event Functions** (async, triggered) |
| Workflow automation (#4) | **Signals + Event Functions** (spike→alert→notify→task) |
| Rate limiting / DDoS (#7) | **API Gateway** throttling + auth |
| RBAC / JWT scopes (#8) | **Authentication** + jurisdiction scopes + clearance tiers (§F) |
| Hot cache / no waiting | **Cache** — top rings/risk/stats sub-300ms (abstraction built) |
| Object storage | **Stratus** — scans, PDFs, model artifacts, encrypted tips |
| Vectors / graph adjacency (#2, #5) | **NoSQL** — embeddings + subgraph cache |
| Local/private LLM (#3) | **QuickML (Qwen) inside Catalyst**, opt-in; rules+TF-IDF default |
| CI/CD | **Pipelines** push→deploy; gate on the engine test suite |
| Observability | structured logs + request metrics + **model-drift** checks on scheduled runs |
| Idempotency / retries | dedupe by `source_fir_url`; INSERT-OR-REPLACE on business keys; circuit retries |
| Cursor pagination (#14) | ZCQL keyset paging on every list |

---

## 3. What to build for the hackathon — prioritized

You cannot build all ~60 features before the deadline. Win with a **tight, deep vertical
slice** that demonstrates *intelligence + responsibility + a real product*, then name the
rest as a credible roadmap (this document *is* that roadmap — show it to judges).

### Tier 0 — the winning demo (build/finish these)
1. **A1 similar-cases + A3 auto-context brief** on the case file — the "it thinks" moment.
2. **A2/A5 related-everything rails** + **A4 connection path** (you have the graph).
3. **B1 District Command Card** with **clearance & conviction rate** (unused schema gold) — **[BUILT]**.
4. **D2 copilot next-step reasoning** + **D3 "who worked cases like this."**
5. **F1–F3 clearance tiers + break-glass**, shown live via the role switcher.
6. **J1 KSP branding + login/landing** — makes it look official, not "AI-generated." — **[BUILT]**.
7. **G1 watchlist/BOLO auto-match** — insight → operational action.

### Tier 1 — strong differentiators (if time)
Officer/team intelligence (E1), duplicate/Zero-FIR (G7), data-quality dashboard (H5),
near-repeat early warning (G4), visible audit + model-card screens (I1/I3), NL→chart (D4).

### Tier 2 — roadmap (say it, don't build it now)
PWA offline (J6), WASM blur (H4), citizen encrypted tips (G8), browser extension (#11),
Neo4j/Pinecone at true scale, court/prosecution tracking (E5), map WebGL clustering on deploy (J4).

---

## 4. The five "wow" moments to engineer for the pitch

1. **From one plate to a gang, in 3 clicks** — search `KA68MC3164` → dossier (10 FIRs, 4
   districts, whole crew) → the auto-context brief writes the story → the network graph. *(loop exists)*
2. **The system tells the officer what to do next** — copilot proposes leads (D2), cited, framed as suggestions.
3. **Clearance in action** — flip Constable → SP → Analyst → Ethics and watch identities
   redact and jurisdictions gate, live. Then a **228A** case stays masked even for the SP.
4. **District performance nobody else shows** — clearance & conviction rates + backlog aging,
   ranked across districts, from data everyone else ignored.
5. **Responsible by design** — every AI output explained (SHAP/reasons/citations), fairness
   audit visible, "never asserts guilt," fully audited. The trust moat, stated out loud.

> Build Tier 0 deep, keep the guardrails visible, put the KSP crest on it, and walk the five
> moments. That is a winning Datathon submission — an intelligence platform a police force
> could actually, responsibly, use.

