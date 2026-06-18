"""HyDE — Hypothetical Document Embeddings.

Generates 3 hypothetical answers to the query, embeds them, and averages
the embeddings to create a richer query vector for retrieval.
"""

from __future__ import annotations
import asyncio
from app.core.state import RAGState
from app.utils.llm import chat_completion
from app.utils.embeddings import get_embedding

_HYDE_PROMPT = """\
You are a Kubernetes SRE expert. Write a short, factual document excerpt (3-5 sentences)
that would perfectly answer the following question. Do NOT say "this document" or mention
that it's hypothetical — just write the content directly.

Question: {query}
"""


async def run_hyde(state: RAGState) -> RAGState:
    """Generate 3 hypothetical answers and compute their average embedding."""
    tasks = [
        chat_completion(
            prompt=_HYDE_PROMPT.format(query=state.query),
            max_tokens=200,
            temperature=0.7,
        )
        for _ in range(3)
    ]
    answers = await asyncio.gather(*tasks)
    state.hypothetical_answers = list(answers)

    # Embed all 3 hypothetical answers and average
    embed_tasks = [get_embedding(a) for a in answers]
    embeddings = await asyncio.gather(*embed_tasks)

    n = len(embeddings[0])
    avg = [sum(e[i] for e in embeddings) / len(embeddings) for i in range(n)]
    state.hyde_embedding = avg

    return state
