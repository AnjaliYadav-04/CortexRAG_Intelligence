"""LangGraph state schema for the Enterprise RAG pipeline."""

from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class RAGState(BaseModel):
    """Shared state passed through every node in the LangGraph state machine."""

    # ── Input ──────────────────────────────────────────────────────────────
    query: str
    user_id: str
    session_id: str

    # ── Routing ────────────────────────────────────────────────────────────
    intent: Optional[Literal["rag", "sql", "hybrid"]] = None

    # ── HyDE ───────────────────────────────────────────────────────────────
    hypothetical_answers: list[str] = Field(default_factory=list)
    hyde_embedding: Optional[list[float]] = None

    # ── Retrieval ──────────────────────────────────────────────────────────
    dense_hits: list[dict[str, Any]] = Field(default_factory=list)
    sparse_hits: list[dict[str, Any]] = Field(default_factory=list)
    rrf_hits: list[dict[str, Any]] = Field(default_factory=list)
    reranked_hits: list[dict[str, Any]] = Field(default_factory=list)

    # ── CRAG ───────────────────────────────────────────────────────────────
    crag_relevance_score: Optional[float] = None
    web_fallback_results: list[dict[str, Any]] = Field(default_factory=list)

    # ── Spotlighting ───────────────────────────────────────────────────────
    spotlighted_context: Optional[str] = None

    # ── Text2SQL ───────────────────────────────────────────────────────────
    generated_sql: Optional[str] = None
    sql_validated: bool = False
    sql_approved: Optional[bool] = None          # None = pending HITL
    sql_result_rows: list[dict[str, Any]] = Field(default_factory=list)
    sql_formatted: Optional[str] = None

    # ── LLM Answer ─────────────────────────────────────────────────────────
    llm_answer: Optional[str] = None
    self_rag_score: Optional[float] = None
    self_rag_retries: int = 0

    # ── Final ──────────────────────────────────────────────────────────────
    final_answer: Optional[str] = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ── Error / Control flow ───────────────────────────────────────────────
    error: Optional[str] = None
    requires_human_approval: bool = False

    class Config:
        arbitrary_types_allowed = True
