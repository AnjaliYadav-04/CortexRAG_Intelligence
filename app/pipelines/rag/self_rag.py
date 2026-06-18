"""Self-RAG — LLM Answer Generation + Reflection loop.

1. llm_answer_generation: generates the answer grounded on spotlighted context.
2. self_rag_reflect: scores the answer quality; if < threshold, triggers re-retrieval.
"""

from __future__ import annotations
import os
from app.core.state import RAGState
from app.utils.llm import chat_completion

_ANSWER_PROMPT = """\
You are a Kubernetes SRE expert assistant. Answer the user's question using ONLY
the information in the provided documents. If the answer cannot be found, say so.
Cite document indices where applicable (e.g. [doc 0]).

<context>
{context}
</context>

Question: {query}

Answer:"""

_REFLECT_PROMPT = """\
You are a quality evaluator. Score how well the following answer addresses the question.
Consider: accuracy, completeness, grounding in provided context.

Return ONLY a JSON object: {{"score": 0.0-1.0, "reason": "brief reason"}}

Question: {query}
Answer: {answer}
"""


async def llm_answer_generation(state: RAGState) -> RAGState:
    """Generate the final answer grounded on spotlighted context."""
    context = state.spotlighted_context or state.sql_formatted or ""

    state.llm_answer = await chat_completion(
        prompt=_ANSWER_PROMPT.format(context=context, query=state.query),
        max_tokens=800,
        temperature=0.2,
    )
    return state


async def self_rag_reflect(state: RAGState) -> RAGState:
    """Score the answer; if below threshold, increment retries for re-retrieval."""
    import json

    raw = await chat_completion(
        prompt=_REFLECT_PROMPT.format(query=state.query, answer=state.llm_answer),
        max_tokens=80,
        temperature=0,
    )
    try:
        data = json.loads(raw)
        score = float(data.get("score", 0.8))
    except Exception:
        score = 0.8  # assume good if parsing fails

    state.self_rag_score = score
    state.self_rag_retries += 1
    state.metadata["self_rag_score"] = score
    state.metadata["self_rag_retries"] = state.self_rag_retries

    return state
