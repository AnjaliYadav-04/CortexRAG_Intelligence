"""Finalize node — attaches metadata and prepares the final response."""

from __future__ import annotations
import time
from app.core.state import RAGState


async def finalize(state: RAGState) -> RAGState:
    """Attach metadata and set final_answer from whichever pipeline ran."""
    state.final_answer = state.llm_answer or state.error or "No answer generated."

    state.metadata.update({
        "intent": state.intent,
        "crag_score": state.crag_relevance_score,
        "self_rag_score": state.self_rag_score,
        "self_rag_retries": state.self_rag_retries,
        "web_fallback_used": bool(state.web_fallback_results),
        "sql_used": bool(state.generated_sql),
        "source_count": len(state.sources),
        "timestamp": time.time(),
    })
    return state
