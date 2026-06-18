"""Async GPT-4o wrapper with retry logic and cache integration."""

from __future__ import annotations
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import AsyncOpenAI
from app.config import settings
from app.cache.redis_cache import cache_get, cache_set

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def chat_completion(
    prompt: str,
    *,
    system: str = "You are a helpful Kubernetes SRE expert.",
    max_tokens: int = 1000,
    temperature: float = 0.2,
    use_cache: bool = True,
) -> str:
    """Call GPT-4o with optional Redis caching."""
    cache_key = f"{system}|{prompt}|{temperature}"

    if use_cache:
        cached = await cache_get("ans", cache_key)
        if cached:
            return cached

    response = await _get_client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = response.choices[0].message.content or ""

    if use_cache:
        await cache_set("ans", cache_key, text)

    return text


async def chat_completion_json(prompt: str, **kwargs) -> dict:
    """Like chat_completion but parses JSON response."""
    raw = await chat_completion(prompt, **kwargs)
    raw = raw.strip().lstrip("```json").rstrip("```").strip()
    return json.loads(raw)
