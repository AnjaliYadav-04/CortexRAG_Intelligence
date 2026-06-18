"""Spotlighting (L8) — wraps retrieved chunks in XML delimiters.

This technique prevents prompt injection by clearly delineating
untrusted document content from trusted system instructions.
"""

from __future__ import annotations
from app.core.state import RAGState


def _format_chunk(hit: dict, idx: int) -> str:
    payload = hit.get("payload", {})
    source = payload.get("source", f"doc_{idx}")
    text = payload.get("text", "")
    return (
        f"<document index=\"{idx}\" source=\"{source}\">\n"
        f"{text}\n"
        f"</document>"
    )


async def spotlighting(state: RAGState) -> RAGState:
    """Build XML-delimited context from reranked hits + web fallback."""
    parts: list[str] = []

    # Local retrieved chunks
    for i, hit in enumerate(state.reranked_hits):
        parts.append(_format_chunk(hit, i))
        state.sources.append({
            "index": i,
            "source": hit.get("payload", {}).get("source", ""),
            "score": hit.get("ce_score", hit.get("score", 0)),
        })

    # Web fallback chunks (appended after local)
    offset = len(state.reranked_hits)
    for i, result in enumerate(state.web_fallback_results):
        parts.append(
            f"<document index=\"{offset + i}\" source=\"{result.get('url', 'web')}\">\n"
            f"{result.get('content', '')}\n"
            f"</document>"
        )

    state.spotlighted_context = "\n\n".join(parts)
    return state
