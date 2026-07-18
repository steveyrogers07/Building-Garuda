"""GARUDA AppSail - ingestion endpoints (Phase 3).

POST /extract  : OCR text -> structured fields + per-field confidence + a Review_Queue record
POST /geocode  : place/address -> lat/long (gazetteer)
POST /promote  : approved extraction -> canonical Incidents/Entities/Incident_Edges rows

Default extractor is rule-based (no QuickML credits). Set EXTRACTOR=qwen to use Qwen.
The Node event function calls /extract during ingestion; the review UI calls /promote on
approve. Heavy logic stays here (AppSail); Node stays thin.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from engines.extraction.confidence import score_confidence
from engines.extraction.rules import extract_fir
from engines.geocode.geocoder import geocode
from engines import promote

router = APIRouter(tags=["ingestion"])


class ExtractIn(BaseModel):
    text: str
    source_fir_url: Optional[str] = None


@router.post("/extract")
def extract(body: ExtractIn):
    if os.environ.get("EXTRACTOR", "rules").lower() == "qwen":
        from engines.extraction.qwen import extract_fir_qwen
        rec, prov = extract_fir_qwen(body.text)
    else:
        rec, prov = extract_fir(body.text)

    if rec.get("lat") is None and rec.get("address_text"):
        lat, lng, _conf, _method = geocode(rec["address_text"], rec.get("district_code"))
        rec["lat"], rec["long"] = lat, lng
        prov["lat"] = prov["long"] = "geocoded" if lat is not None else "missing"
    if body.source_fir_url:
        rec["source_fir_url"] = body.source_fir_url

    conf = score_confidence(rec, prov)
    review = promote.to_review_record(rec, conf, body.source_fir_url)
    return {"extraction": rec, "field_confidences": conf, "review_record": review}


class GeocodeIn(BaseModel):
    place: str
    district_code: Optional[str] = None


@router.post("/geocode")
def geocode_endpoint(body: GeocodeIn):
    lat, lng, conf, method = geocode(body.place, body.district_code)
    return {"lat": lat, "long": lng, "confidence": conf, "method": method}


class PromoteIn(BaseModel):
    extraction: dict
    incident_id: Optional[str] = None
    confidence: Optional[float] = None


@router.post("/promote")
def promote_endpoint(body: PromoteIn):
    return promote.promote_to_canonical(body.extraction, body.incident_id, body.confidence)
