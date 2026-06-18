"""CRAG — Corrective RAG.

Grades retrieved context relevance. If score < threshold, falls back
to Tavily web search to supplement or replace the retrieved context.
"""

from __future__ import annotations
import os
from app.core.state import RAGState
from app.utils.llm import chat_completion

_THRESHOLD = float(os.getenv("CRAG_RELEVANCE_THRESHOLD", "0.7"))

_GRADER_PROMPT = """\
You are a relevance grader for a Kubernetes SRE assistant.
Given the user question and a retrieved document excerpt, score how relevant
the document is to answering the question.

Return ONLY a JSON object: {{"score": 0.0-1.0, "reason": "brief reason"}}

Question: {query}
Document: {document}
"""


async def crag_grader(state: RAGState) -> RAGState:
    """Grade top hit relevance. Trigger web fallback if below threshold."""
    if not state.reranked_hits:
        state.crag_relevance_score = 0.0
        await _web_fallback(state)
        return state

    top_doc = state.reranked_hits[0]["payload"].get("text", "")
    import json

    raw = await chat_completion(
        prompt=_GRADER_PROMPT.format(query=state.query, document=top_doc[:1000]),
        max_tokens=80,
        temperature=0,
    )
    try:
        data = json.loads(raw)
        score = float(data.get("score", 0.5))
    except Exception:
        score = 0.5

    state.crag_relevance_score = score

    if score < _THRESHOLD:
        await _web_fallback(state)

    return state


async def _web_fallback(state: RAGState) -> None:
    """Tavily web search as fallback when local context is insufficient."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))
        results = client.search(query=state.query, max_results=3)
        state.web_fallback_results = results.get("results", [])
    except Exception as exc:
        state.web_fallback_results = []
        state.metadata["crag_fallback_error"] = str(exc)
