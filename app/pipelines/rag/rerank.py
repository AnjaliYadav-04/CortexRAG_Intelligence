"""Reciprocal Rank Fusion (RRF) and Cross-Encoder Reranking."""

from __future__ import annotations
from collections import defaultdict
from app.core.state import RAGState

_RRF_K = 60
_RERANK_TOP_N = 5


# ── RRF ─────────────────────────────────────────────────────────────────────

async def rrf_fusion(state: RAGState) -> RAGState:
    """Merge dense + sparse hit lists using Reciprocal Rank Fusion (k=60)."""
    scores: dict[str, float] = defaultdict(float)
    payloads: dict[str, dict] = {}

    for rank, hit in enumerate(state.dense_hits):
        scores[hit["id"]] += 1.0 / (_RRF_K + rank + 1)
        payloads[hit["id"]] = hit["payload"]

    for rank, hit in enumerate(state.sparse_hits):
        scores[hit["id"]] += 1.0 / (_RRF_K + rank + 1)
        payloads.setdefault(hit["id"], hit["payload"])

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    state.rrf_hits = [
        {"id": doc_id, "score": score, "payload": payloads[doc_id]}
        for doc_id, score in ranked
    ]
    return state


# ── Cross-Encoder Rerank ─────────────────────────────────────────────────────

async def cross_encoder_rerank(state: RAGState) -> RAGState:
    """Re-rank top RRF hits with a cross-encoder model (BGE / Voyage AI).

    Falls back to RRF order if sentence-transformers isn't available.
    """
    hits = state.rrf_hits[:20]   # only rerank top 20 for speed

    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder("BAAI/bge-reranker-base")

        pairs = [(state.query, h["payload"].get("text", "")) for h in hits]
        ce_scores = model.predict(pairs)

        scored = sorted(
            zip(hits, ce_scores), key=lambda x: x[1], reverse=True
        )
        state.reranked_hits = [
            {**hit, "ce_score": float(score)}
            for hit, score in scored[:_RERANK_TOP_N]
        ]
    except Exception:
        # Graceful fallback — use RRF order
        state.reranked_hits = hits[:_RERANK_TOP_N]

    return state
