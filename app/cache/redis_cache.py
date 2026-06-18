"""5-Tier Redis Cache (Upstash-compatible).

Tier         Key prefix          TTL
──────────── ─────────────────── ────
Embedding    emb:<sha256>        7 days
Intent       int:<sha256>        24 h
SQL Gen      sql:<sha256>        24 h
SQL Result   sqlr:<sha256>       15 min
RAG Answer   ans:<sha256>        1 h
"""

from __future__ import annotations
import hashlib
import json
import os
from typing import Any, Optional

import redis.asyncio as aioredis

_TTL = {
    "emb":  7 * 24 * 3600,      # 7 days
    "int":  24 * 3600,           # 24 h
    "sql":  24 * 3600,           # 24 h
    "sqlr": 15 * 60,             # 15 min
    "ans":  1 * 3600,            # 1 h
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _client() -> aioredis.Redis:
    return aioredis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
    )


async def cache_get(tier: str, key_text: str) -> Optional[Any]:
    """Return cached value or None."""
    redis = _client()
    try:
        raw = await redis.get(f"{tier}:{_sha(key_text)}")
        return json.loads(raw) if raw else None
    except Exception:
        return None
    finally:
        await redis.aclose()


async def cache_set(tier: str, key_text: str, value: Any) -> None:
    """Store value with tier-appropriate TTL."""
    redis = _client()
    try:
        ttl = _TTL.get(tier, 3600)
        await redis.setex(
            f"{tier}:{_sha(key_text)}",
            ttl,
            json.dumps(value, default=str),
        )
    except Exception:
        pass   # cache errors are non-fatal
    finally:
        await redis.aclose()


async def cache_delete(tier: str, key_text: str) -> None:
    redis = _client()
    try:
        await redis.delete(f"{tier}:{_sha(key_text)}")
    finally:
        await redis.aclose()
