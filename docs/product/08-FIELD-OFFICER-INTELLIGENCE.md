# GARUDA — Field-Officer Intelligence: What Would Actually Help an IO

> **Companion to:** [07 — Intelligence Blueprint](07-INTELLIGENCE-BLUEPRINT.md) (the
> hackathon-judging capability catalogue) · [`docs/DATASET_REAL_SCHEMA.md`](../DATASET_REAL_SCHEMA.md)
> (the organizer's ER diagram — the ground truth for what's actually feasible).
>
> **Different question from 07.** 07 asks "what makes GARUDA look intelligent to judges."
> This document asks a narrower, harder question: **if a real Investigating Officer (IO) in
> Karnataka opened this tool tomorrow morning with a stack of open cases, what would actually
> save them time, keep them out of trouble, or help them close a case** — not a dashboard
> feature, an actual working-life feature. Every idea here is checked against two things: (a)
> a real pain point in Indian FIR investigation, and (b) a column that already exists in the
> organizer's schema (mostly **unused** by every other team, because nobody reads the ER
> diagram this closely).

---

## 0. What an IO's week actually looks like (the grounding)

Before the feature list, the pain points these features answer to. An Investigating Officer in
a busy Karnataka station is typically running **15–40 open cases at once**, across every stage
from "just registered" to "chargesheet filed, awaiting trial." Their real day-to-day friction:

1. **The clock is always running against them.** Under CrPC/BNSS, custody of an arrested accused
   lapses (default/statutory bail) if a chargesheet isn't filed within a fixed window — **60 days**
   for offences punishable up to 10 years, **90 days** for offences punishable with death/life/≥10
   years. Miss it, and a genuinely guilty accused walks on a technicality. **Nobody tracks this
   automatically today** — it lives in an IO's head or a paper diary.
2. **They juggle far more cases than any dashboard shows them.** A "my cases" view sorted by
   urgency (deadline, court date, backlog age) doesn't exist — they re-derive priority from memory
   or a physical register every morning.
3. **Evidence goes stale.** CCTV footage gets overwritten in 15–30 days if not seized. Witnesses
   move, forget, or turn hostile. The investigation window that matters is *days*, not months.
4. **They don't know what they don't know.** A new IO on a transferred case, or a station handling
   a crime type it rarely sees, has no easy way to ask "how did we solve the last five cases like
   this one" — the institutional memory is scattered across retired colleagues, not software.
5. **Paperwork compounds.** The case diary (statutory, contemporaneous log of every investigative
   step — CrPC §172/BNSS equivalent) is still handwritten in most stations. It's the single most
   time-consuming, least-loved part of the job, and it's also the record courts scrutinize hardest.
6. **They can't see the pattern from inside one FIR.** An IO working case #4 of a 10-incident
   series has no way to know it *is* series #4 unless someone tells them — GARUDA's network reveal
   already fixes this for the analyst; it needs to reach the IO at registration time, not months later.

Every feature below targets one of these six frictions directly, using data the schema already
carries but nobody is computing.

---

## 1. Statutory Deadline Tracker — the single highest-value feature (P0)

**What:** For every case with an arrested accused, compute and prominently surface: *days
remaining to file a chargesheet before default bail becomes available*, using
`ArrestSurrender.ArrestSurrenderDate` + the statutory window derived from `GravityOffence`
(Heinous → 90 days, Non-Heinous → 60 days — the real CrPC/BNSS split maps almost exactly onto
the schema's own severity field). Traffic-light urgency (green >30 days / amber 10–30 / red <10
/ black overdue) on every case card, the IO's case list, and a station/district rollup.

**Why it matters:** this is the single most concrete, high-stakes, *avoidable* failure mode in
Indian criminal investigation — a case falling apart not on the facts but on a missed clock. No
dashboard-style feature captures "police work" better than this one, and no other hackathon team
will have built it because it requires actually reading `ArrestSurrender` + `GravityOffence`
together, which the ER diagram doesn't spell out as a workflow — you have to know the law to see it.

**Data needed:** `ArrestSurrender.ArrestSurrenderDate` (**built** — the `Arrests` table, §9),
`Incidents.gravity` (**built**). Zero new NER/ML — pure date arithmetic.

**Feasibility:** High. This is a half-day build now that the `Arrests` table exists (§9 — done;
`tests/test_arrests_sections.py` gate A4 already proves all four urgency buckets are populated).

---

## 2. "My Cases" — a real worklist, not a table (P0)

**What:** Per-officer landing view (keyed off `officer_id`, which now exists on every incident):
open cases sorted by urgency = deadline proximity (§1) → court date proximity → case age →
gravity. Not a generic case list with filters — a **worklist an IO opens first thing every
morning** and works top-to-bottom. Each row: one-line status, next action due, days since last
diary entry (§4).

**Why it matters:** officers don't think in "filter by district/crime type" — they think in "what
do I have to do today." This is the difference between a database and a tool someone opens
voluntarily.

**Data needed:** `Incidents.officer_id` (**built**), case_category/gravity (**built**), court
dates (§9 dependency for full urgency scoring, but a v1 without court dates is still valuable).

**Feasibility:** High — mostly a UI/aggregation layer over data GARUDA already has.

---

## 3. Digital Case Diary (P0/P1)

**What:** A structured, timestamped, append-only log per case — "visited scene," "recorded
statement of witness X," "sent forensic sample to lab," "attempted arrest, accused absconding" —
each entry with a free-text note + an optional structured type (visit / statement / evidence /
arrest-attempt / court / other) + optional linked entity (the witness, the evidence item). This
*is* the case diary CrPC/BNSS already requires IOs to keep — GARUDA just makes it digital,
searchable, and impossible to lose.

**Why it matters:** it's not a "nice dashboard feature" — it's a **legal obligation** IOs already
spend hours on badly (loose paper, illegible handwriting, diaries that go missing when a case is
transferred). Digitizing it is pure time saved *and* better evidence for court, with zero
behavior change required (they're already writing this content — just onto paper).

**Data needed:** none from the source schema — this is a new, GARUDA-native `Case_Diary` table
(`incident_id, ts, author_officer_id, entry_type, note, linked_entity_id`). Append-only,
audited, exportable to PDF for the actual court-facing register.

**Feasibility:** High — a straightforward CRUD feature with real teeth because it's legally
grounded, not invented.

---

## 4. Crime-Type Investigation Checklists (P1)

**What:** A dynamic, crime-type-specific checklist attached to every case the moment it's
registered — e.g. for **chain snatching**: pull CCTV within 500 m/48 h, check pawn shops/gold
buyers in 72 h, cross-check known chain-snatching entities active in the area (the network
reveal, surfaced *as a checklist item*, not a separate screen); for **house burglary**: photograph
point of entry, canvass neighbours, check second-hand/pawn dealers, compare MO against the active
`MO_Clusters`/`Crime_Series` for the locality. Checking an item off writes a `Case_Diary` entry (§3)
automatically — the checklist *is* the diary's skeleton.

**Why it matters:** junior officers (constables, ASIs — the bulk of Karnataka's IOs by headcount
per `Rank`) often lack the mentoring an experienced PI would give on "what do you check first for
this crime type." A checklist encodes institutional SOP knowledge that currently lives only in
senior officers' heads, directly raising evidence quality on cases run by less experienced staff.

**Data needed:** static SOP-per-crime_type config (no ML) + wiring into existing engines (network
ego, series membership) as checklist *actions*, not separate screens.

**Feasibility:** High — a config table + a UI panel; the "smart" parts (near-repeat, MO cluster,
network reveal) already exist as engines, this just surfaces them as prompts at the moment they're
useful instead of requiring the IO to go look.

---

## 5. Case-Strength / Evidence-Gap Flag — never a guilt score (P1)

**What:** Per case, a transparent checklist of *evidence completeness*, not a guilt or conviction
score: does it have a party with `evidence_type=cctv`/`recovered` (not just `fir_named`)? Are all
`ActSectionAssociation` entries populated? Is there a chargesheet-eligible status without a
`Chargesheets` row yet (§1 overlap)? "This case has only witness testimony, no recovered property
or CCTV — evidentiary gap" is an actionable nudge a supervisor or IO can act on *before* the
chargesheet is filed, not a verdict on anyone's guilt.

**Why it matters:** weak chargesheets are a leading cause of acquittals having nothing to do with
whether the accused actually did it — poor evidence documentation. Flagging the *gap*, not the
person, keeps this squarely in "surfaces and explains, never accuses" territory (the platform's
own ethics law) while giving real prosecutorial value.

**Data needed:** `Incident_Edges.evidence_type` (**built**), `ActSectionAssociation` — multiple
sections per case (**built** as `Case_Sections`, §9), `Chargesheets` (**built**).

**Feasibility:** High — the multi-section model (§9) is in place; the full
evidence-per-section version is buildable now, not just the narrower v1.

---

## 6. Absconding-Accused / Non-Bailable-Warrant Board (P1)

**What:** A dedicated board of accused persons in open cases who have **not** yet been arrested
or surrendered (`Accused` rows with no matching `ArrestSurrender` entry) — Karnataka's real
"most wanted, locally" list, filterable by district/gravity/days-absconding, feeding directly into
the watchlist/BOLO auto-match (already planned as G1 in 07) so a fresh FIR anywhere in the state
that names or matches one of these people surfaces instantly.

**Why it matters:** today this list exists only informally (a station's "wanted" register, if it
exists at all, rarely cross-referenced against other stations). Statewide visibility on absconding
accused is exactly the kind of cross-jurisdiction value SCRB exists to provide and no individual
station can build alone.

**Data needed:** `Accused` (**built**) joined against `ArrestSurrender` (**built** as
`Arrests`, §9 — suspects with no arrest row are exactly this board).

**Feasibility:** High — §9's Arrests table exists; the join is straightforward.

---

## 7. Repeat-Victim / Vulnerable-Location Flag (P1, careful framing)

**What:** Flip the network reveal around: instead of only surfacing repeat *offenders*, surface
repeat **complainants/victims at the same address** — a shop burgled three times in a year, a
household with multiple domestic-incident FIRs. This is protective, not punitive: it tells a
station "this location/person needs a follow-up visit or a preventive patrol," not "watch this
person as a suspect."

**Why it matters:** policing that's purely offender-centric misses the victim-protection angle
entirely, and repeat-victimization is a well-established criminological signal (a location or
person victimized once is measurably more likely to be victimized again soon after) that no other
team is likely to think to compute, because the schema's `ComplainantDetails`/`Victim` tables read
as "who to mask for privacy," not "who to protect proactively."

**Data needed:** `ComplainantDetails`/`Victim` name+address matched across cases (entity
resolution, **already built** for persons generally) — this is a *reuse* of the existing
resolution engine with a different lens, not new infrastructure.

**Feasibility:** High — almost entirely reuses what's already built; the only new work is the
"victim view" of the dossier and framing it protectively in the UI copy.

---

## 8. Financial/Cyber Fraud Network Reveal (P1/P2)

**What:** The organizer schema has no bank-account/UPI/email tables any more than it has
phone/vehicle tables — exactly the gap `DATASET_REAL_SCHEMA.md` already flags for phone/vehicle
(*"lives inside BriefFacts free text… biggest dependency for the hero reveal"*). Extend the same
NER extractor that pulls phone/vehicle to also pull **bank account numbers, UPI IDs, and email
addresses** from `BriefFacts` for Cheating/Cybercrime/Criminal-breach-of-trust cases, and feed them
into the *same* co-offender network engine as new entity types. A "one UPI ID linked to 12
cheating FIRs across 6 districts" reveal is the *financial-fraud equivalent* of the chain-snatching
kingpin reveal — and economic offences are GARUDA's fastest-growing, least-served crime category
(already present as `Cheating`/`Cybercrime`/`Criminal breach of trust` in the crime-type list).

**Why it matters:** cyber/financial fraud rings are today's actual growth area in Indian crime,
and they're *harder* to see manually than a chain-snatching gang because the shared thread (a UPI
ID, not a face) is buried in text across dozens of unrelated-looking complaints at different
stations. This is the single highest-leverage extension of the existing network engine — same
code path, new entity type.

**Data needed:** narrative NER extension (extraction engine already exists, `rules.py`/`qwen.py`)
+ no schema changes (entities already support arbitrary `type`).

**Feasibility:** Medium — the network/entity infrastructure is 100% reused; the only new work is
extraction patterns for account/UPI/email formats (regex-heavy, tractable without a fancy model).

---

## 9. Fill the schema gaps that make §1/§5/§6 possible: Arrests + multi-section (P0 infra) — [BUILT]

**What:** Two organizer tables GARUDA didn't model until now, both load-bearing for the features above:
- **`Arrests`** (organizer: `ArrestSurrender`) — **[BUILT]** `arrest_id, incident_id, entity_id,
  event_type {arrest|surrender}, event_date, district_code, court_id, io_officer_id`. Powers §1
  (deadline clock starts at arrest date), §6 (absconding board), and real arrest-rate reporting.
- **`Case_Sections`** (organizer: `ActSectionAssociation`, one-to-many) — **[BUILT]** GARUDA no
  longer collapses a case to one `ipc_bns_code`; real cases invoke **multiple** sections. The
  `Case_Sections` table (`incident_id, act_code, section_code, section_order`; order 1 = the
  primary/most-serious section, which `ipc_bns_code` continues to hold) unlocks accurate legal
  classification and powers §5's evidence-per-section gap analysis. Companion sections are
  act-matched (a BNS-coded case cites BNS companions) with IT-Act sections on cyber/cheating
  cases; every IPC/BNS pair is covered by `data/reference/ipc_bns_map.csv`.
  Gates: `tests/test_arrests_sections.py`.

**Why it matters:** this is the same category of gap that this session's audit found with
`ChargesheetDetails`/`CaseCategory`/`GravityOffence`/`Employee` — documented as needed, never
built. Closing it isn't a "nice feature," it's completing the schema alignment the organizers will
actually check, and it's the prerequisite for the three most operationally valuable ideas above.

**Feasibility:** High — same pattern as this session's `Officers`/`Chargesheets` addition:
generator config + generate.py extension + canonical schema entry + a store.py reader. A half-day
each, and both should land *before* §1/§5/§6 since those depend on them.

**Schema-completeness pass (P2, [BUILT] the same day):** eight more organizer columns that don't
gate any of the above but round out the ER-diagram alignment so nothing an ER-literate judge
checks for is a bare text field: `Incidents.incident_to_date/info_received_ps_date` (CaseMaster),
`Arrests.is_accused/is_complainant_accused` (ArrestSurrender), `Case_Status` master (reference,
`Incidents.status` stays denormalized text), `Courts` master + `Incidents.court_id` (Court —
assigned once a case is trial-eligible; **this closes half of §10 below**), `Incident_Edges.is_police`
(Victim.VictimPolice), `Officers.kgid/dob/blood_group/appointment_date` (Employee), and
`Crime_Head_Sections` (CrimeHeadActSection, a reference map derived from crime_types + companion
sections). Gates: `tests/test_p2_fields.py`.

---

## 10. Court-Date & Hearing Tracker (P1 — half [BUILT])

**What:** `Courts` (master) + `Incidents.court_id`/`Arrests.court_id` are now modeled — a case
gets assigned a real court once it's trial-eligible (chargesheeted/pending-trial/closed/final
report). What's still missing is a **hearing calendar**: the schema (ours and the organizer's)
carries *which* court, not *when* the next hearing is. Once that exists (a lightweight `Hearings`
table, or a real-data field to ask the organizers about), surface upcoming hearings per IO/case
with lead time for evidence/witness prep, and flag cases with no scheduled hearing despite being
chargesheeted (a process-stall signal, closing the loop §B5 in the main blueprint already
gestures at).

**Why it matters:** IOs are frequently required to produce evidence or witnesses in court with
short notice; a missed or badly-prepared hearing can be as damaging to a case as a missed
chargesheet deadline. This closes the FIR→chargesheet→**trial** loop the platform doesn't reach
today (everything currently stops at "chargesheeted").

**Feasibility:** Medium — needs a `Hearings` concept that isn't fully specified in the ER diagram
as given; treat as a v2 item pending clarification on whether real hearing-date data exists.

---

## 11. Handover Brief on Transfer (P1, cheap given what's already built)

**What:** When a case's `officer_id` changes (a transfer), auto-generate a one-page brief for the
incoming IO: case summary, `A3`-style auto-context (already planned in 07), full `Case_Diary`
history (§3), open checklist items (§4), evidence gaps (§5), and days remaining on the deadline
clock (§1). One click, not a fresh read of the whole file.

**Why it matters:** high transfer rates in Indian police postings mean case continuity is a real,
recurring failure point — incoming IOs routinely restart investigative work that was already done,
or miss where the previous IO left off. This is nearly free once §1/§3/§4/§5 exist — it's a
composed *view* of data GARUDA will already be holding, not new intelligence.

**Feasibility:** High, but sequenced last — it's a composition of the four features above.

---

## 12. Kannada-first field mode (P1 — a reminder, not a new idea)

Every feature above is worthless to the constables and head constables who form the numeric
majority of `Employee.Rank` if it's English-only and desktop-only. This isn't a new capability —
07's J6 (PWA offline) and J8 (Kannada) already call for it — but it deserves restating here with
teeth: **the officer this document is about is disproportionately likely to be a beat constable
working in Kannada on a cracked-screen phone with patchy connectivity**, not an analyst at a
desktop. Any feature above that ships English-only/online-only reaches only the SP's office, not
the person actually running the case.

---

## 13. What to build next, in order (given this session's schema work)

`Officers`, `Chargesheets`, `case_category`, `gravity` and the District Command Card landed this
session — they are the exact prerequisites §1, §2, §6 and part of §5 needed. That makes the
next-highest-leverage sequence:

1. **§9 infra** (`Arrests` + `Case_Sections`) — **[BUILT]** — unlocks everything below it.
   Landed with the same pattern as `Officers`/`Chargesheets` (generator config + generate.py
   + canonical schema + column map + store readers + `tests/test_arrests_sections.py`).
2. **§1 Statutory Deadline Tracker** — the single most "this is real police work" feature
   possible, and now cheap given §9.
3. **§2 "My Cases" worklist** — makes the whole platform feel like a tool an IO opens daily,
   not a report a district commander glances at monthly.
4. **§6 Absconding-accused board** — statewide value from data no single station can assemble
   alone; directly strengthens G1 (BOLO) already on the roadmap.
5. **§3 Digital Case Diary** — highest raw time-savings per officer, and legally grounded rather
   than invented, but scope it after 1–2 since it's a bigger standalone build.
6. **§4 Investigation checklists** — cheap, mostly UI, and makes 1–3 feel like a coherent
   workflow rather than separate screens.
7. **§7 Repeat-victim flag** and **§8 financial-fraud network** — both near-total reuse of
   existing engines; good "fast follow" wins once the above ship.

Everything in this document is additive to 07's roadmap, not a replacement — it answers a
different question (*"would an IO actually use this"* vs *"does this look intelligent"*), and the
honest answer is that the best submissions do both at once.
