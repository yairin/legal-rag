"""
"כל זכות" web fallback:
1. Tavily search restricted to kolzchut.org.il
2. Scrape full page text with trafilatura
3. Mini-rerank snippets with Cohere to return best passages
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import cohere
import httpx
import structlog
import trafilatura

from app.config import get_settings

log = structlog.get_logger(__name__)

_RERANK_MODEL = "rerank-multilingual-v3.0"
_TAVILY_API = "https://api.tavily.com/search"
_MAX_SCRAPED_CHARS = 6000


@dataclass
class WebResult:
    url: str
    title: str
    snippet: str
    full_text: str
    rerank_score: float = 0.0


async def _tavily_search(query: str, max_results: int = 5) -> list[dict]:
    settings = get_settings()
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "include_domains": ["kolzchut.org.il"],
        "max_results": max_results,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_TAVILY_API, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data.get("results", [])


def _scrape(url: str) -> str:
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, include_links=False, include_images=False)
        return (text or "")[:_MAX_SCRAPED_CHARS]
    except Exception as exc:
        log.warning("scrape_failed", url=url, error=str(exc))
        return ""


def _mini_rerank(query: str, results: list[WebResult], top_k: int = 3) -> list[WebResult]:
    settings = get_settings()
    client = cohere.Client(api_key=settings.cohere_api_key)

    docs = [r.full_text or r.snippet for r in results]
    if not docs:
        return []

    reranked = client.rerank(
        model=_RERANK_MODEL,
        query=query,
        documents=docs,
        top_n=top_k,
    )

    output: list[WebResult] = []
    for r in reranked.results:
        item = results[r.index]
        item.rerank_score = r.relevance_score
        output.append(item)

    return output


async def kolzchut_search(query: str, top_k: int = 3) -> list[WebResult]:
    """
    Search kolzchut.org.il, scrape, and rerank.
    Returns top_k WebResult objects.
    """
    try:
        tavily_results = await _tavily_search(query)
        if not tavily_results:
            return []

        # Scrape pages in parallel (thread pool, trafilatura is sync)
        loop = asyncio.get_event_loop()
        scraped_texts = await asyncio.gather(
            *[
                loop.run_in_executor(None, _scrape, r.get("url", ""))
                for r in tavily_results
            ]
        )

        results = [
            WebResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("content", ""),
                full_text=text or r.get("content", ""),
            )
            for r, text in zip(tavily_results, scraped_texts)
        ]

        reranked = _mini_rerank(query, results, top_k=top_k)
        log.info("kolzchut_search_done", results=len(reranked))
        return reranked

    except Exception as exc:
        log.error("kolzchut_search_failed", error=str(exc))
        return []
