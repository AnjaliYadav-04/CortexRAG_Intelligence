"""FastAPI route handlers."""

from __future__ import annotations
import uuid
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.api.models import (
    ChatRequest, ChatResponse, SQLApprovalRequest,
    TokenRequest, TokenResponse, HealthResponse,
)
from app.config import settings
from app.core.graph import graph
from app.core.state import RAGState
from app.guardrails.input_pipeline import run_input_pipeline
from app.guardrails.output_pipeline import run_output_pipeline

router = APIRouter()
bearer = HTTPBearer()

# In-memory HITL approval store (swap for Redis/DB in production)
_pending_approvals: dict[str, RAGState] = {}


# ── Auth helper ───────────────────────────────────────────────────────────────

def _get_token_payload(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    from jose import jwt, JWTError
    try:
        return jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


# ── Token endpoint (demo — not production-grade) ─────────────────────────────

@router.post("/auth/token", response_model=TokenResponse, tags=["Auth"])
async def get_token(req: TokenRequest):
    """Issue a JWT for demo purposes. Replace with real auth in production."""
    from jose import jwt
    if req.password != "sre-secret":   # demo only
        raise HTTPException(status_code=401, detail="Invalid credentials")
    payload = {
        "sub": req.username,
        "exp": int(time.time()) + settings.JWT_EXPIRE_MINUTES * 60,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return TokenResponse(access_token=token)


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, tags=["RAG"])
async def chat(
    req: ChatRequest,
    payload: dict = Depends(_get_token_payload),
):
    user_id = payload.get("sub", "anonymous")

    # Run input guardrails (L1, L4b, L5, L2, L7a — L4a already done via JWT dep)
    from app.guardrails.input_pipeline import (
        l1_injection_check, l4b_rate_limit, l5_truncate,
        l2_llm_guard, l7a_content_moderation,
    )
    l4b_rate_limit(user_id)
    clean_query = l1_injection_check(req.query)
    clean_query = l5_truncate(clean_query)
    clean_query = l2_llm_guard(clean_query)
    clean_query = l7a_content_moderation(clean_query)

    # Build initial state
    state = RAGState(
        query=clean_query,
        user_id=user_id,
        session_id=req.session_id or str(uuid.uuid4()),
    )

    # Run LangGraph
    config = {"configurable": {"thread_id": state.session_id}}
    result: RAGState = await graph.ainvoke(state, config=config)

    # HITL: if SQL is pending approval, stash state and return prompt
    if result.requires_human_approval and result.sql_approved is None:
        _pending_approvals[state.session_id] = result
        return ChatResponse(
            answer="A SQL query has been generated and requires your approval before execution.",
            sql_pending_approval=True,
            generated_sql=result.generated_sql,
            intent=result.intent or "sql",
            metadata=result.metadata,
        )

    # Run output guardrails
    response = run_output_pipeline(
        result.final_answer or "",
        {
            "answer": result.final_answer or "",
            "sources": result.sources,
            "metadata": result.metadata,
            "intent": result.intent or "rag",
            "sql_pending_approval": False,
            "generated_sql": result.generated_sql,
        },
    )
    return response


# ── SQL Approval (HITL) endpoint ─────────────────────────────────────────────

@router.post("/sql/approve", response_model=ChatResponse, tags=["HITL"])
async def approve_sql(
    req: SQLApprovalRequest,
    payload: dict = Depends(_get_token_payload),
):
    """Human-in-the-loop SQL approval endpoint."""
    state = _pending_approvals.pop(req.session_id, None)
    if not state:
        raise HTTPException(status_code=404, detail="No pending SQL approval for this session.")

    state.sql_approved = req.approved

    if not req.approved:
        return ChatResponse(
            answer="SQL execution cancelled by user.",
            intent="sql",
            metadata=state.metadata,
        )

    # Resume graph from execute_sql
    config = {"configurable": {"thread_id": req.session_id}}
    result: RAGState = await graph.ainvoke(state, config=config)

    response = run_output_pipeline(
        result.final_answer or "",
        {
            "answer": result.final_answer or "",
            "sources": result.sources,
            "metadata": result.metadata,
            "intent": result.intent or "sql",
            "sql_pending_approval": False,
            "generated_sql": result.generated_sql,
        },
    )
    return response


# ── Health check ──────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["Ops"])
async def health():
    import asyncio, asyncpg, redis.asyncio as aioredis
    from qdrant_client import AsyncQdrantClient

    qdrant_ok = False
    try:
        client = AsyncQdrantClient(url=settings.QDRANT_URL)
        await client.get_collections()
        await client.close()
        qdrant_ok = True
    except Exception:
        pass

    pg_ok = False
    try:
        conn = await asyncpg.connect(settings.POSTGRES_DSN)
        await conn.close()
        pg_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok" if all([qdrant_ok, pg_ok, redis_ok]) else "degraded",
        qdrant=qdrant_ok,
        postgres=pg_ok,
        redis=redis_ok,
    )
