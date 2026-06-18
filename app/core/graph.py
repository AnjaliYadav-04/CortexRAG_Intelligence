"""LangGraph State Machine — Enterprise Advanced RAG.

Nodes
─────
route_intent → [hyde | generate_sql]
hyde → embed_query → hybrid_retrieval → rrf → cross_encoder_rerank
    → crag_grader → spotlighting → llm_answer → self_rag_reflect → finalize

generate_sql → validate_sql → interrupt (HITL) → execute_sql
            → format_results → llm_answer → finalize
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.state import RAGState
from app.core.intent_router import route_intent, intent_condition
from app.pipelines.rag.hyde import run_hyde
from app.pipelines.rag.retrieval import embed_query, hybrid_retrieval
from app.pipelines.rag.rerank import rrf_fusion, cross_encoder_rerank
from app.pipelines.rag.crag import crag_grader
from app.pipelines.rag.spotlighting import spotlighting
from app.pipelines.rag.self_rag import llm_answer_generation, self_rag_reflect
from app.pipelines.sql.generator import generate_sql
from app.pipelines.sql.validator import validate_sql
from app.pipelines.sql.executor import execute_sql, format_results
from app.utils.finalize import finalize


# ── Self-RAG loop condition ──────────────────────────────────────────────────

def self_rag_condition(state: RAGState) -> str:
    score = state.self_rag_score or 0.0
    retries = state.self_rag_retries
    from app.config import settings
    if score < settings.SELF_RAG_SCORE_THRESHOLD and retries < settings.SELF_RAG_MAX_RETRIES:
        return "hyde"           # loop back — re-retrieve with updated query
    return "finalize"


# ── HITL condition ───────────────────────────────────────────────────────────

def hitl_condition(state: RAGState) -> str:
    """After interrupt(), check if user approved the SQL."""
    if state.sql_approved is True:
        return "execute_sql"
    if state.sql_approved is False:
        return "finalize"       # user rejected — return graceful message
    return "__interrupt__"      # still pending


# ── Build graph ──────────────────────────────────────────────────────────────

def build_graph(checkpointer=None) -> StateGraph:
    g = StateGraph(RAGState)

    # ── Nodes ────────────────────────────────────────────────────────────────
    g.add_node("route_intent", route_intent)

    # RAG branch
    g.add_node("hyde", run_hyde)
    g.add_node("embed_query", embed_query)
    g.add_node("hybrid_retrieval", hybrid_retrieval)
    g.add_node("rrf", rrf_fusion)
    g.add_node("cross_encoder_rerank", cross_encoder_rerank)
    g.add_node("crag_grader", crag_grader)
    g.add_node("spotlighting", spotlighting)

    # SQL branch
    g.add_node("generate_sql", generate_sql)
    g.add_node("validate_sql", validate_sql)
    g.add_node("execute_sql", execute_sql)
    g.add_node("format_results", format_results)

    # Shared
    g.add_node("llm_answer", llm_answer_generation)
    g.add_node("self_rag_reflect", self_rag_reflect)
    g.add_node("finalize", finalize)

    # ── Edges ─────────────────────────────────────────────────────────────────
    g.set_entry_point("route_intent")

    # Intent routing
    g.add_conditional_edges("route_intent", intent_condition, {
        "hyde": "hyde",
        "generate_sql": "generate_sql",
    })

    # RAG pipeline
    g.add_edge("hyde", "embed_query")
    g.add_edge("embed_query", "hybrid_retrieval")
    g.add_edge("hybrid_retrieval", "rrf")
    g.add_edge("rrf", "cross_encoder_rerank")
    g.add_edge("cross_encoder_rerank", "crag_grader")
    g.add_edge("crag_grader", "spotlighting")
    g.add_edge("spotlighting", "llm_answer")

    # SQL pipeline
    g.add_edge("generate_sql", "validate_sql")
    # interrupt() — HITL pending approval
    g.add_conditional_edges("validate_sql", hitl_condition, {
        "execute_sql": "execute_sql",
        "finalize": "finalize",
        "__interrupt__": END,       # graph pauses; resumes on approval webhook
    })
    g.add_edge("execute_sql", "format_results")
    g.add_edge("format_results", "llm_answer")

    # Self-RAG loop
    g.add_edge("llm_answer", "self_rag_reflect")
    g.add_conditional_edges("self_rag_reflect", self_rag_condition, {
        "hyde": "hyde",
        "finalize": "finalize",
    })

    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=["execute_sql"])


# Singleton (no checkpointing in dev — swap for PostgresSaver in production)
graph = build_graph()
