"""GARUDA entity-resolution engine (Phase 4)."""
from .resolver import (
    MERGE_THRESHOLD,
    REVIEW_THRESHOLD,
    person_decision,
    person_score,
    resolve_entities,
    resolve_persons,
    resolve_exact,
    to_review_record,
)

__all__ = [
    "MERGE_THRESHOLD",
    "REVIEW_THRESHOLD",
    "person_decision",
    "person_score",
    "resolve_entities",
    "resolve_persons",
    "resolve_exact",
    "to_review_record",
]
