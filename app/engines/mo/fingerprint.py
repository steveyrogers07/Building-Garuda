"""GARUDA - MO fingerprinting & clustering (Phase 4).

Per incident: an embedding of mo_text + interpretable structured MO features (time bucket,
crime type, weapon/vehicle/entry/target). Cluster with HDBSCAN -> mo_cluster_id, and
describe each cluster with a signature (top terms + dominant structured features) so an
analyst sees "night / two-wheeler / gold chain", not just a number.

Defaults are local & free:
  - text embedding : TF-IDF + TruncatedSVD (LSA). Opt-in sentence-transformers via
                     MO_EMBEDDER=sbert (multilingual model if mo_text contains Kannada).
  - clustering     : sklearn's HDBSCAN (bundled since scikit-learn 1.3 - no compiler).
Vectors are precomputed and can be persisted (save_vectors / load_vectors) so re-runs and
the Phase-7 copilot reuse them instead of re-embedding every call.

Heavy deps (scikit-learn) are imported lazily inside fit_mo so importing this module - and
the AppSail health probe - never fails in a minimal environment.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .features import HOUR_BUCKETS, structured_features

# how strongly the structured block counts relative to the (unit-normalized) text block
STRUCT_WEIGHT = 0.6
SVD_COMPONENTS = 64
MIN_CLUSTER_SIZE = 8
NOISE_LABEL = ""          # mo_cluster_id for HDBSCAN noise (-1)


# --------------------------------------------------------------------------- #
# text embedding
# --------------------------------------------------------------------------- #
def _has_kannada(texts):
    import re
    rx = re.compile(r"[ಀ-೿]")
    return any(rx.search(t or "") for t in texts)


def embed_text(texts):
    """Return (matrix, vocab_terms_or_None). Default TF-IDF+SVD; MO_EMBEDDER=sbert switches
    to sentence-transformers (falls back to TF-IDF if the lib/model is unavailable)."""
    backend = os.environ.get("MO_EMBEDDER", "tfidf").lower()
    if backend == "sbert":
        try:
            from sentence_transformers import SentenceTransformer
            name = ("paraphrase-multilingual-MiniLM-L12-v2" if _has_kannada(texts)
                    else "all-MiniLM-L6-v2")
            model = SentenceTransformer(name)
            vecs = np.asarray(model.encode(list(texts), normalize_embeddings=True))
            return vecs, None
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger("garuda").warning("sbert unavailable (%s); using TF-IDF", exc)

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize

    tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                            min_df=3, max_features=4000)
    X = tfidf.fit_transform(texts)
    n_comp = min(SVD_COMPONENTS, X.shape[1] - 1, max(2, X.shape[0] - 1))
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    vecs = normalize(svd.fit_transform(X))
    # keep the fitted tfidf so signatures can name the top terms per cluster
    embed_text.last_tfidf = tfidf
    embed_text.last_tfidf_matrix = X
    return vecs, tfidf.get_feature_names_out()


# --------------------------------------------------------------------------- #
# structured block
# --------------------------------------------------------------------------- #
def _structured_matrix(feats_list):
    crime_types = sorted({f["crime_type"] for f in feats_list})
    ct_index = {c: i for i, c in enumerate(crime_types)}
    hb_index = {h: i for i, h in enumerate(HOUR_BUCKETS)}
    flags = ["weapon", "vehicle", "entry", "target_jewellery", "target_mobile",
             "target_cash", "target_vehicle"]
    cols = len(crime_types) + len(HOUR_BUCKETS) + len(flags)
    M = np.zeros((len(feats_list), cols), dtype=float)
    for i, f in enumerate(feats_list):
        M[i, ct_index[f["crime_type"]]] = 1.0
        hb = f["hour_bucket"]
        if hb in hb_index:
            M[i, len(crime_types) + hb_index[hb]] = 1.0
        base = len(crime_types) + len(HOUR_BUCKETS)
        for j, fl in enumerate(flags):
            M[i, base + j] = float(f[fl])
    # L2-normalize rows so the block is comparable to the unit text block
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return M / norms


# --------------------------------------------------------------------------- #
# fit
# --------------------------------------------------------------------------- #
def build_vectors(incidents):
    """incidents: list of dicts (incident_id, mo_text, crime_type, occurred_at).
    Returns (ids, vectors, feats_list, terms)."""
    ids = [str(r["incident_id"]) for r in incidents]
    texts = [r.get("mo_text") or "" for r in incidents]
    feats_list = [structured_features(r) for r in incidents]

    text_vecs, terms = embed_text(texts)
    struct = _structured_matrix(feats_list)
    vectors = np.hstack([text_vecs, STRUCT_WEIGHT * struct])
    return ids, vectors, feats_list, terms


def fit_mo(incidents, min_cluster_size=MIN_CLUSTER_SIZE, prefix="MO"):
    """Cluster incidents by MO. Returns {assignments, clusters, ids, vectors}.

    assignments: incident_id -> mo_cluster_id ('' for noise).
    clusters:    list of MO_Clusters rows (cluster_id, crime_type, size, label,
                 centroid_features JSON, exemplar_incident_id)."""
    from sklearn.cluster import HDBSCAN

    ids, vectors, feats_list, terms = build_vectors(incidents)
    labels = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=None,
                     metric="euclidean", copy=True).fit_predict(vectors)

    assignments = {}
    for i, lab in zip(ids, labels):
        assignments[i] = NOISE_LABEL if lab == -1 else f"{prefix}{int(lab):04d}"

    clusters = _signatures(ids, vectors, labels, feats_list, terms, prefix)
    return {"assignments": assignments, "clusters": clusters, "ids": ids, "vectors": vectors}


# --------------------------------------------------------------------------- #
# signatures
# --------------------------------------------------------------------------- #
def _top_terms(member_rows, terms, k=6):
    """Top TF-IDF terms averaged over a cluster's members (TF-IDF backend only)."""
    X = getattr(embed_text, "last_tfidf_matrix", None)
    if X is None or terms is None or not member_rows:
        return []
    mean = np.asarray(X[member_rows].mean(axis=0)).ravel()
    top = mean.argsort()[::-1][:k]
    return [terms[t] for t in top if mean[t] > 0]


def _signatures(ids, vectors, labels, feats_list, terms, prefix):
    from collections import Counter, defaultdict

    members = defaultdict(list)
    for row, lab in enumerate(labels):
        if lab != -1:
            members[lab].append(row)

    clusters = []
    for lab, rows in sorted(members.items()):
        crimes = Counter(feats_list[r]["crime_type"] for r in rows)
        hours = Counter(feats_list[r]["hour_bucket"] for r in rows)
        dom_crime = crimes.most_common(1)[0][0]
        dom_hour = hours.most_common(1)[0][0]
        flag_rate = {
            fl: round(sum(feats_list[r][fl] for r in rows) / len(rows), 2)
            for fl in ["weapon", "vehicle", "entry", "target_jewellery",
                       "target_mobile", "target_cash"]
        }
        top_terms = _top_terms(rows, terms)
        # exemplar = member nearest the cluster centroid
        centroid = vectors[rows].mean(axis=0)
        exemplar_row = rows[int(np.argmin(np.linalg.norm(vectors[rows] - centroid, axis=1)))]
        label = f"{dom_crime} | {dom_hour}" + (f" | {top_terms[0]}" if top_terms else "")
        clusters.append({
            "cluster_id": f"{prefix}{int(lab):04d}",
            "crime_type": dom_crime,
            "size": len(rows),
            "label": label,
            "centroid_features": json.dumps({
                "dominant_crime": dom_crime,
                "dominant_hour": dom_hour,
                "crime_mix": dict(crimes),
                "flag_rate": flag_rate,
                "top_terms": top_terms,
            }, ensure_ascii=False),
            "exemplar_incident_id": ids[exemplar_row],
        })
    return clusters


# --------------------------------------------------------------------------- #
# vector persistence (precompute once; reuse on re-runs / copilot)
# --------------------------------------------------------------------------- #
def save_vectors(path, ids, vectors):
    """Persist MO vectors locally (prod stores them in Data Store / NoSQL)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, ids=np.array(ids, dtype=object), vectors=vectors)


def load_vectors(path):
    data = np.load(path, allow_pickle=True)
    return list(data["ids"]), data["vectors"]
