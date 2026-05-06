"""
Embeddings via Cohere embed-multilingual-v3.0 (1024 dims, Hebrew support).
Free tier: 100 req/min — no credit card required.
Voyage is kept as optional fallback if VOYAGE_API_KEY is set and paid.
"""
from __future__ import annotations

import asyncio
import structlog
import cohere

from app.config import get_settings

log = structlog.get_logger(__name__)

_COHERE_MODEL = "embed-multilingual-v3.0"
_BATCH_SIZE = 96  # Cohere max per request


def _get_cohere() -> cohere.Client:
    return cohere.Client(api_key=get_settings().cohere_api_key)


def _cohere_input_type(input_type: str) -> str:
    return "search_query" if input_type == "query" else "search_document"


def _embed_sync_with_retry(texts: list[str], input_type: str) -> list[list[float]]:
    import time
    client = _get_cohere()
    for attempt in range(6):
        try:
            response = client.embed(
                texts=texts,
                model=_COHERE_MODEL,
                input_type=_cohere_input_type(input_type),
                embedding_types=["float"],
            )
            return list(response.embeddings.float_)
        except cohere.errors.too_many_requests_error.TooManyRequestsError:
            wait = 12 * (attempt + 1)  # 12, 24, 36, 48, 60, 72s
            log.warning("cohere_rate_limit", attempt=attempt + 1, wait=wait)
            time.sleep(wait)
        except Exception as exc:
            raise RuntimeError(f"Cohere embed failed: {exc}") from exc
    raise RuntimeError("Cohere rate limit exceeded after retries")


async def embed_batch(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed a list of texts in batches. Returns list of embedding vectors."""
    loop = asyncio.get_event_loop()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        embeddings = await loop.run_in_executor(
            None, lambda b=batch: _embed_sync_with_retry(b, input_type)
        )
        all_embeddings.extend(embeddings)
        if i + _BATCH_SIZE < len(texts):
            await asyncio.sleep(2)  # 2s between batches

    log.debug("embedded", count=len(texts), model=_COHERE_MODEL)
    return all_embeddings


async def embed_query(text: str) -> list[float]:
    results = await embed_batch([text], input_type="query")
    return results[0]


async def embed_queries(texts: list[str]) -> list[list[float]]:
    return await embed_batch(texts, input_type="query")
