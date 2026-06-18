"""Output Security Pipeline (response side).

L7b  Output Moderation + PII Redaction  — post-generation safety
L9   Pydantic Schema Validation         — LLM retry on schema fail
"""

from __future__ import annotations
import re
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException


# ── PII patterns (output side — belt-and-suspenders) ─────────────────────────

_PII_OUT = {
    "email":  re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.I),
    "ip":     re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "secret": re.compile(r"(?i)(password|api[_-]?key|token|secret)\s*[:=]\s*\S+"),
}


def l7b_output_moderation(text: str) -> str:
    """Redact PII and secrets from LLM output."""
    for label, pattern in _PII_OUT.items():
        text = pattern.sub(f"[{label.upper()}_REDACTED]", text)
    return text


# ── L9: Pydantic schema validation ───────────────────────────────────────────

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    metadata: dict = {}
    intent: str = "rag"
    sql_pending_approval: bool = False
    generated_sql: str | None = None


def l9_validate_response(raw: dict) -> ChatResponse:
    """Validate response schema; raise 500 if invalid (triggers LLM retry upstream)."""
    try:
        return ChatResponse(**raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Response schema validation failed: {exc}",
        )


def run_output_pipeline(answer: str, response_dict: dict) -> ChatResponse:
    """Run L7b + L9 on the outgoing response."""
    clean_answer = l7b_output_moderation(answer)
    response_dict["answer"] = clean_answer
    return l9_validate_response(response_dict)
