"""Cohere rerank-multilingual-v3 reranker."""
from __future__ import annotations

import structlog
import cohere

from app.config import get_settings

log = structlog.get_logger(__name__)

_MODEL = "rerank-multilingual-v3.0"


def rerank(
    query: str,
    child_chunks: list[dict],
    top_k: int | None = None,
) -> tuple[list[dict], float]:
    """
    Rerank child chunks using Cohere multilingual.

    Returns (reranked_chunks, max_score).
    Each returned chunk has an added 'rerank_score' field.
    """
    settings = get_settings()
    if top_k is None:
        top_k = settings.rerank_top_k

    client = cohere.Client(api_key=settings.cohere_api_key)

    documents = [c["text"] for c in child_chunks]

    results = client.rerank(
        model=_MODEL,
        query=query,
        documents=documents,
        top_n=top_k,
    )

    reranked: list[dict] = []
    for r in results.results:
        chunk = child_chunks[r.index].copy()
        chunk["rerank_score"] = r.relevance_score
        reranked.append(chunk)

    max_score = max((r["rerank_score"] for r in reranked), default=0.0)
    log.debug("reranked", query_len=len(query), top_k=top_k, max_score=round(max_score, 3))
    return reranked, max_score
