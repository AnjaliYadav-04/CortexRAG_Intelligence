"""Intent Router — classifies queries as rag | sql | hybrid."""

from __future__ import annotations
import re
from app.core.state import RAGState
from app.utils.llm import chat_completion

# SQL intent keywords (fast-path heuristic)
_SQL_PATTERNS = re.compile(
    r"\b(how many|count|list all|show me the|select|avg|sum|"
    r"pods? (are|is|were)|nodes? (are|is|were)|deployments?|"
    r"namespaces?|replica|restart count)\b",
    re.IGNORECASE,
)

_ROUTER_PROMPT = """\
You are an intent classifier for a Kubernetes SRE assistant.
Classify the user query into exactly one of: rag | sql | hybrid

- rag   → conceptual / doc-lookup questions (what is, how does, explain, troubleshoot)
- sql   → structured data queries (counts, lists, metrics from the ops database)
- hybrid → needs both context AND data (e.g. "why are pod restarts high and what to do?")

Respond with ONLY the label, no explanation.

Query: {query}
"""


async def route_intent(state: RAGState) -> RAGState:
    """Determine query intent and update state."""
    query = state.query

    # Fast-path heuristic for obvious SQL queries
    if _SQL_PATTERNS.search(query):
        state.intent = "sql"
        return state

    label = await chat_completion(
        prompt=_ROUTER_PROMPT.format(query=query),
        max_tokens=10,
        temperature=0,
    )
    label = label.strip().lower()
    if label not in ("rag", "sql", "hybrid"):
        label = "rag"  # safe default

    state.intent = label  # type: ignore[assignment]
    return state


def intent_condition(state: RAGState) -> str:
    """LangGraph conditional edge — returns the next node name."""
    if state.intent == "sql":
        return "generate_sql"
    if state.intent == "hybrid":
        return "hyde"   # runs RAG first, then merges SQL
    return "hyde"
