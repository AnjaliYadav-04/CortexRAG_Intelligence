"""API request and response Pydantic models."""

from __future__ import annotations
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    session_id: str = Field(default="default", description="Conversation session ID")


class SQLApprovalRequest(BaseModel):
    session_id: str
    approved: bool
    reason: str | None = None


class TokenRequest(BaseModel):
    username: str
    password: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    metadata: dict = {}
    intent: str = "rag"
    sql_pending_approval: bool = False
    generated_sql: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HealthResponse(BaseModel):
    status: str
    qdrant: bool
    postgres: bool
    redis: bool
