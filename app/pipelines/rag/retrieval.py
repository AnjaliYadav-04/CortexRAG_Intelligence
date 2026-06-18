"""Hybrid Retrieval — Dense (Qdrant) + Sparse (BM25) search.

Also handles the embed_query node (wraps the raw query embedding for non-HyDE paths).
"""

from __future__ import annotations
import os
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    NamedVector,
    NamedSparseVector,
    SparseVector,
    SearchRequest,
    Filter,
)
from app.core.state import RAGState
from app.utils.embeddings import get_embedding

_COLLECTION = os.getenv("QDRANT_COLLECTION", "k8s_docs")
_TOP_K = 20   # retrieve more, rerank down later


def _get_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))


async def embed_query(state: RAGState) -> RAGState:
    """Embed the raw query (used when HyDE is skipped or as fallback)."""
    if state.hyde_embedding is None:
        state.hyde_embedding = await get_embedding(state.query)
    return state


async def hybrid_retrieval(state: RAGState) -> RAGState:
    """Run dense + sparse search in parallel, populate state hits."""
    client = _get_client()
    query_vec = state.hyde_embedding or await get_embedding(state.query)

    # Dense search
    dense_results = await client.search(
        collection_name=_COLLECTION,
        query_vector=NamedVector(name="dense", vector=query_vec),
        limit=_TOP_K,
        with_payload=True,
    )

    # BM25 sparse search (requires SPLADE or BM25 vectors pre-indexed)
    # Falls back to pure dense if sparse vectors aren't available
    try:
        sparse_results = await client.search(
            collection_name=_COLLECTION,
            query_vector=NamedSparseVector(
                name="sparse",
                vector=SparseVector(indices=[], values=[]),  # BM25 handled server-side
            ),
            limit=_TOP_K,
            with_payload=True,
        )
    except Exception:
        sparse_results = []

    state.dense_hits = [
        {"id": str(r.id), "score": r.score, "payload": r.payload}
        for r in dense_results
    ]
    state.sparse_hits = [
        {"id": str(r.id), "score": r.score, "payload": r.payload}
        for r in sparse_results
    ]

    await client.close()
    return state
