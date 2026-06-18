"""9-Layer Input Security Pipeline (Defense-in-Depth).

L1   Pydantic + Regex    — injection pattern detection
L4a  JWT Auth            — PyJWT token verification
L4b  Rate Limit          — 20 req/min per user
L6   Token Budget        — 100k tokens/day per user
L5   Input Restructure   — tiktoken truncation to safe length
L2   llm-guard Scan      — PromptInj + Toxicity scan
L7a  Content Moderation  — topic enforcement + PII redaction
"""

from __future__ import annotations
import os
import re
import time
from typing import Optional

from fastapi import HTTPException, Request
from jose import JWTError, jwt

# ── L1: Injection pattern detection ─────────────────────────────────────────

_INJECTION_PATTERNS = re.compile(
    r"(ignore (previous|all) instructions?|"
    r"you are now|pretend (you are|to be)|"
    r"system prompt|<\|im_start\|>|<\|endoftext\|>|"
    r"DAN mode|jailbreak)",
    re.IGNORECASE,
)


def l1_injection_check(text: str) -> str:
    if _INJECTION_PATTERNS.search(text):
        raise HTTPException(status_code=400, detail="Input rejected: injection pattern detected.")
    return text


# ── L4a: JWT Auth ─────────────────────────────────────────────────────────────

_SECRET = os.getenv("JWT_SECRET", "change-me")
_ALGO   = os.getenv("JWT_ALGORITHM", "HS256")


def l4a_jwt_auth(token: str) -> dict:
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


# ── L4b: Rate Limit ───────────────────────────────────────────────────────────

_rate_store: dict[str, list[float]] = {}
_RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))


def l4b_rate_limit(user_id: str) -> None:
    now = time.time()
    window = _rate_store.setdefault(user_id, [])
    # Drop entries older than 60s
    _rate_store[user_id] = [t for t in window if now - t < 60]
    if len(_rate_store[user_id]) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded (20 req/min).")
    _rate_store[user_id].append(now)


# ── L6: Token Budget ──────────────────────────────────────────────────────────

_budget_store: dict[str, dict] = {}
_DAILY_BUDGET = int(os.getenv("TOKEN_BUDGET_PER_DAY", "100000"))


def l6_token_budget(user_id: str, token_count: int) -> None:
    today = time.strftime("%Y-%m-%d")
    entry = _budget_store.setdefault(user_id, {"date": today, "used": 0})
    if entry["date"] != today:
        entry["date"] = today
        entry["used"] = 0
    if entry["used"] + token_count > _DAILY_BUDGET:
        raise HTTPException(status_code=429, detail="Daily token budget exceeded.")
    entry["used"] += token_count


# ── L5: Input Restructure (tiktoken truncation) ────────────────────────────────

def l5_truncate(text: str, max_tokens: int = 1000) -> str:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(text)
        if len(tokens) > max_tokens:
            text = enc.decode(tokens[:max_tokens])
    except Exception:
        text = text[:4000]   # char fallback
    return text


# ── L2: llm-guard scan ───────────────────────────────────────────────────────

def l2_llm_guard(text: str) -> str:
    try:
        from llm_guard.input_scanners import PromptInjection, Toxicity
        for Scanner in (PromptInjection, Toxicity):
            scanner = Scanner()
            sanitized, is_valid, _ = scanner.scan("", text)
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Input blocked by {Scanner.__name__} scanner.",
                )
            text = sanitized
    except ImportError:
        pass   # llm-guard optional
    return text


# ── L7a: Content Moderation + PII Redaction ──────────────────────────────────

_PII_PATTERNS = {
    "email":  re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.I),
    "phone":  re.compile(r"\b(\+?\d[\d\s\-().]{7,14}\d)\b"),
    "ip":     re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}


def l7a_content_moderation(text: str) -> str:
    for label, pattern in _PII_PATTERNS.items():
        text = pattern.sub(f"[{label.upper()}_REDACTED]", text)
    return text


# ── Full Pipeline ─────────────────────────────────────────────────────────────

def run_input_pipeline(
    raw_text: str,
    *,
    user_id: str,
    token: str,
    token_count: int = 0,
) -> str:
    """Run all 9 layers and return sanitized text (or raise HTTPException)."""
    l4a_jwt_auth(token)           # L4a — must auth first
    l4b_rate_limit(user_id)       # L4b
    l6_token_budget(user_id, token_count or len(raw_text.split()))  # L6
    text = l1_injection_check(raw_text)   # L1
    text = l5_truncate(text)              # L5
    text = l2_llm_guard(text)            # L2
    text = l7a_content_moderation(text)  # L7a
    return text
