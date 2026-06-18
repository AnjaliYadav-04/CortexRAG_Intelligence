"""Async embedding wrapper (text-embedding-3-small) with Redis caching."""

from __future__ import annotations
from openai import AsyncOpenAI
from app.config import settings
from app.cache.redis_cache import cache_get, cache_set

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def get_embedding(text: str) -> list[float]:
    """Embed text using text-embedding-3-small with 7-day Redis cache."""
    cached = await cache_get("emb", text)
    if cached:
        return cached

    response = await _get_client().embeddings.create(
        model=settings.EMBED_MODEL,
        input=text,
    )
    vector = response.data[0].embedding

    await cache_set("emb", text, vector)
    return vector


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts."""
    # Check cache first for each
    results: list[list[float] | None] = [None] * len(texts)
    to_embed: list[tuple[int, str]] = []

    for i, text in enumerate(texts):
        cached = await cache_get("emb", text)
        if cached:
            results[i] = cached
        else:
            to_embed.append((i, text))

    if to_embed:
        response = await _get_client().embeddings.create(
            model=settings.EMBED_MODEL,
            input=[t for _, t in to_embed],
        )
        for (i, text), emb_obj in zip(to_embed, response.data):
            results[i] = emb_obj.embedding
            await cache_set("emb", text, emb_obj.embedding)

    return [r for r in results if r is not None]
