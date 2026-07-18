"""GARUDA - entity resolution (Phase 4). Merges alias/variant mentions of the same
person/vehicle/phone into one canonical_id, with a confidence and a review flag for
borderline pairs (never a silent merge).

Pipeline (per `type`, never all-pairs):
    normalize + transliterate  ->  phonetic blocking  ->  weighted pairwise match
    ->  connected-components clustering  ->  canonical_id + match_confidence

Persons use a transparent weighted scorer (Jaro-Winkler on name parts anchored on the
last name, + phonetic agreement, + gender/age agreement). Vehicles and phones resolve by
exact match on their normalized value (a registration plate / number is a strong key).

Pure-Python, runs locally on the Phase-2 CSVs (no Catalyst, no credits). rapidfuzz is
used when present; difflib is the fallback.
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime

from . import normalize as N

try:
    from rapidfuzz.distance import JaroWinkler

    def _jw(a: str, b: str) -> float:
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        return JaroWinkler.similarity(a, b)
except Exception:  # noqa: BLE001
    import difflib

    def _jw(a: str, b: str) -> float:
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a, b).ratio()


# --- decision thresholds (tuned against ground_truth.json; see tests/test_resolution.py)
# Precision-first. Jaro-Winkler over the WHOLE name over-merges: its prefix weighting
# scores any two people who share a first name >= 0.9 ("Jagat Bora" vs "Jagat Kari"). The
# planted alias variants all PRESERVE the surname, so a merge requires an exact surname
# match and then strong first-name agreement; loose cross-surname similarity is never a
# merge. The ambiguous initialised form ('R. Kumar') only ever goes to review.
FIRST_MERGE = 0.90          # first-name Jaro-Winkler >= this (same surname) -> merge
FIRST_META_FLOOR = 0.70     # min first-name JW to accept a same-Metaphone merge (ph->f)
FIRST_REVIEW = 0.82         # same surname, weaker first name -> review
SINGLE_MERGE = 0.94         # single-token names: full Jaro-Winkler >= this -> merge
AGE_GAP_SPLIT = 12          # same name but ages this far apart -> namesakes, not a merge
MAX_BLOCK = 800             # skip pathological mega-blocks (keeps blocking tractable)
EXACT_CONF = 0.99           # confidence for an exact vehicle/phone merge

# kept for back-compat / external reference
MERGE_THRESHOLD = FIRST_MERGE
REVIEW_THRESHOLD = FIRST_REVIEW


# --------------------------------------------------------------------------- #
# union-find
# --------------------------------------------------------------------------- #
class _DSU:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:       # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


# --------------------------------------------------------------------------- #
# person scoring
# --------------------------------------------------------------------------- #
def _person_record(row):
    norm = N.normalize_name(row.get("value", ""))
    first, last = N.name_parts(norm)
    age = row.get("age")
    try:
        age = int(age) if age not in (None, "", "nan") else None
    except (TypeError, ValueError):
        age = None
    return {
        "id": row["entity_id"],
        "full": norm,
        "first": first,
        "last": last,
        "gender": (row.get("gender") or "").strip().upper() or None,
        "age": age,
    }


def _is_initial_pair(x, y) -> bool:
    """One first name is an initial of the other: 'r' vs 'ravi'."""
    if not x or not y:
        return False
    if min(len(x), len(y)) != 1 or len(x) == len(y):
        return False
    return x[0] == y[0]


def person_decision(a, b):
    """Return (action, score) where action in {'merge','review','no'}. Precision-first.

    The planted alias variants of one name all reduce to a HIGH full-name similarity
    after normalization/transliteration (stray-token, trailing-a, phonetic swap, Kannada)
    - except the *initialised* form ('R. Kumar'), handled as a structural rule on an
    identical surname. Same-Metaphone first name on an identical surname covers ph->f."""
    # gender is inherited by aliases, so a mismatch is a hard block
    if a["gender"] and b["gender"] and a["gender"] != b["gender"]:
        return "no", 0.0

    fa, fb, la, lb = a["first"], b["first"], a["last"], b["last"]
    full = _jw(a["full"], b["full"])

    # two records with the same name but very different ages are namesakes, not one person
    # (aliases carry no age, so this only ever fires base-vs-base).
    age_split = (
        a["age"] is not None and b["age"] is not None and abs(a["age"] - b["age"]) >= AGE_GAP_SPLIT
    )

    # single-token names (no surname to anchor on): fall back to the whole string
    if not la or not lb:
        if full >= SINGLE_MERGE:
            return ("review", full) if age_split else ("merge", full)
        return ("review", full) if full >= 0.90 else ("no", full)

    # surnames must agree for a person merge (preserved across every planted variant)
    if la != lb:
        return "no", full

    jf = _jw(fa, fb)
    if not age_split:
        if jf >= FIRST_MERGE:                          # trailing-a, v/w, sh/s, stray token
            return "merge", max(full, jf)
        if fa and fb and N.metaphone(fa) == N.metaphone(fb) and jf >= FIRST_META_FLOOR:
            return "merge", max(jf, 0.88)              # ph->f

    # an initialised first name ('R. Kumar') is compatible with many distinct
    # 'R*** Kumar' - ambiguous, so flag for review, never auto-merge (chaining blob).
    if _is_initial_pair(fa, fb):
        return "review", max(full, 0.85)
    if jf >= FIRST_REVIEW:
        return "review", jf
    return "no", jf


def person_score(a, b) -> float:
    """Convenience: the similarity component of person_decision (back-compat)."""
    return person_decision(a, b)[1]


def _person_blocks(recs):
    """Multi-pass blocking: an entity joins a block for each of its phonetic keys
    (last-name NYSIIS + Metaphone, first-name NYSIIS). Two entities sharing any block
    become a candidate pair - robust to a variant that perturbs one name part."""
    blocks = defaultdict(list)
    for r in recs:
        keys = set()
        if r["last"]:
            keys.add("L:" + N.phonetic(r["last"]))
            keys.add("M:" + N.metaphone(r["last"]))
        if r["first"]:
            keys.add("F:" + N.phonetic(r["first"]))
        if not keys and r["full"]:
            keys.add("W:" + r["full"][:4])
        for k in keys:
            blocks[k].append(r["id"])
    return blocks


def _candidate_pairs(blocks):
    seen = set()
    for ids in blocks.values():
        if len(ids) > MAX_BLOCK:
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                seen.add((a, b) if a < b else (b, a))
    return seen


def resolve_persons(rows):
    """rows: list of entity dicts (type==person). Returns (assignments, review_pairs)."""
    recs = [_person_record(r) for r in rows]
    by_id = {r["id"]: r for r in recs}
    blocks = _person_blocks(recs)

    dsu = _DSU()
    for r in recs:
        dsu.find(r["id"])                   # ensure singletons exist
    best_edge = defaultdict(float)          # entity_id -> best merge-edge score
    review_pairs = []

    for a, b in _candidate_pairs(blocks):
        action, s = person_decision(by_id[a], by_id[b])
        if action == "merge":
            dsu.union(a, b)
            best_edge[a] = max(best_edge[a], s)
            best_edge[b] = max(best_edge[b], s)
        elif action == "review":
            review_pairs.append((a, b, round(s, 3)))

    # initials post-pass: an initialised first name ('R. Kumar') is merged into a
    # full-name cluster ONLY when (surname, first-initial, gender) maps to a single
    # cluster - then it is unambiguous (the true parent always shares that key, so a
    # unique candidate *is* the parent). Ambiguous ones stay flagged for review.
    full_key = defaultdict(set)
    initials = []
    for r in recs:
        if not (r["last"] and r["first"] and r["gender"]):
            continue
        if len(r["first"]) == 1:
            initials.append(r)
        else:
            full_key[(r["last"], r["first"][0], r["gender"])].add(dsu.find(r["id"]))
    for r in initials:
        cands = full_key.get((r["last"], r["first"][0], r["gender"]))
        if cands and len(cands) == 1:
            dsu.union(r["id"], next(iter(cands)))
            best_edge[r["id"]] = max(best_edge[r["id"]], 0.85)

    # drop review pairs that the post-pass ended up merging
    review_pairs = [(a, b, s) for (a, b, s) in review_pairs if dsu.find(a) != dsu.find(b)]
    return _finalize(rows, dsu, best_edge), review_pairs


# --------------------------------------------------------------------------- #
# exact-match resolution (vehicles, phones)
# --------------------------------------------------------------------------- #
def resolve_exact(rows, normalizer):
    """Merge entities sharing an identical normalized value (plate / phone number)."""
    dsu = _DSU()
    groups = defaultdict(list)
    for r in rows:
        dsu.find(r["entity_id"])
        groups[normalizer(r.get("value", ""))].append(r["entity_id"])
    best_edge = defaultdict(float)
    for key, ids in groups.items():
        if not key:
            continue
        for other in ids[1:]:
            dsu.union(ids[0], other)
        if len(ids) > 1:
            for i in ids:
                best_edge[i] = EXACT_CONF
    return _finalize(rows, dsu, best_edge), []


# --------------------------------------------------------------------------- #
# clustering -> canonical_id + match_confidence
# --------------------------------------------------------------------------- #
def _finalize(rows, dsu, best_edge):
    members = defaultdict(list)
    for r in rows:
        members[dsu.find(r["entity_id"])].append(r["entity_id"])

    # representative per cluster: prefer a row with age (a base canonical record),
    # then the smallest entity_id for determinism.
    info = {r["entity_id"]: r for r in rows}

    assignments = {}
    for root, ids in members.items():
        rep = min(
            ids,
            key=lambda e: (
                0 if (str(info[e].get("age") or "").strip()) else 1,  # base record first
                e,                                                    # then deterministic
            ),
        )
        for eid in ids:
            conf = 1.0 if eid == rep or len(ids) == 1 else round(best_edge.get(eid, MERGE_THRESHOLD), 3)
            assignments[eid] = {"canonical_id": rep, "match_confidence": conf}
    return assignments


# --------------------------------------------------------------------------- #
# top-level dispatch + review records
# --------------------------------------------------------------------------- #
def resolve_entities(rows):
    """Resolve a mixed list of entity dicts (keys: entity_id, type, value, age, gender).
    Returns {assignments, review_pairs, stats} where assignments maps every entity_id ->
    {canonical_id, match_confidence}."""
    by_type = defaultdict(list)
    for r in rows:
        by_type[(r.get("type") or "").lower()].append(r)

    assignments = {}
    review_pairs = []

    if by_type.get("person"):
        a, rp = resolve_persons(by_type["person"])
        assignments.update(a)
        review_pairs += [("person", *p) for p in rp]
    if by_type.get("vehicle"):
        a, _ = resolve_exact(by_type["vehicle"], N.normalize_vehicle)
        assignments.update(a)
    if by_type.get("phone"):
        a, _ = resolve_exact(by_type["phone"], N.normalize_phone)
        assignments.update(a)

    # any other types: identity (canonical_id == entity_id)
    for r in rows:
        assignments.setdefault(r["entity_id"], {"canonical_id": r["entity_id"], "match_confidence": 1.0})

    n_clusters = len({v["canonical_id"] for v in assignments.values()})
    stats = {
        "entities": len(assignments),
        "canonical_clusters": n_clusters,
        "merged": len(assignments) - n_clusters,
        "review_pairs": len(review_pairs),
    }
    return {"assignments": assignments, "review_pairs": review_pairs, "stats": stats}


def to_review_record(etype, a_id, b_id, score, review_id=None):
    """A Review_Queue-shaped row for a borderline merge (reuses the Phase-3 pattern:
    always 'pending', a human decides). extracted_json carries the candidate pair."""
    return {
        "review_id": review_id or ("RES-" + uuid.uuid4().hex[:10]),
        "source_fir_url": "",
        "extracted_json": json.dumps(
            {"kind": "entity_merge", "type": etype, "a": a_id, "b": b_id}, ensure_ascii=False
        ),
        "field_confidences": json.dumps({"match_confidence": score}),
        "status": "pending",
        "reviewer": "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
