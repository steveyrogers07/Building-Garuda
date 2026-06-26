"""GARUDA copilot — semantic retrieval over FIR narratives (Phase 7).

$0 default: a TF-IDF (word + char n-gram) vector index over `mo_text`/BriefFacts
with cosine scoring — brute force is instant at 10k+ rows, no torch/FAISS. Set
COPILOT_EMBEDDER=sbert to swap in sentence-transformers (multilingual, pulls
torch) once you want true paraphrase matching; the API is identical. Used to
rerank the structured (ZCQL) candidate set — hybrid retrieval, not KB-RAG alone.
"""
from __future__ import annotations

import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


class NarrativeIndex:
    def __init__(self, ids, texts):
        self.ids = list(ids)
        self.pos = {i: k for k, i in enumerate(self.ids)}
        self._sbert = None
        if os.environ.get("COPILOT_EMBEDDER", "tfidf").lower() == "sbert":
            self._build_sbert(texts)        # opt-in, credit/torch heavy
        else:
            self.vec = TfidfVectorizer(max_features=40000, ngram_range=(1, 2),
                                       sublinear_tf=True, stop_words="english")
            self.mat = self.vec.fit_transform(texts)

    def _build_sbert(self, texts):           # pragma: no cover - opt-in path
        from sentence_transformers import SentenceTransformer
        self._sbert = SentenceTransformer(
            os.environ.get("COPILOT_SBERT_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"))
        self.mat = self._sbert.encode(list(texts), normalize_embeddings=True)

    def _sims(self, query):
        if self._sbert is not None:          # pragma: no cover
            qv = self._sbert.encode([query], normalize_embeddings=True)
            return (self.mat @ qv[0])
        return linear_kernel(self.vec.transform([query]), self.mat).ravel()

    def rank(self, query, candidate_ids=None, top_k=10):
        """Top-k (id, score). Restricted to candidate_ids (the structured hits)
        when given — that's the hybrid fuse + rerank step."""
        sims = self._sims(query)
        if candidate_ids is not None:
            idx = [self.pos[i] for i in candidate_ids if i in self.pos]
            scored = sorted(((self.ids[k], float(sims[k])) for k in idx),
                            key=lambda t: -t[1])
        else:
            order = np.argsort(sims)[::-1][:max(top_k * 3, 30)]
            scored = [(self.ids[k], float(sims[k])) for k in order]
        ranked = scored[:top_k]
        nonzero = [(i, s) for i, s in ranked if s > 0]
        return nonzero or ranked      # fall back to filter order if all-zero similarity
