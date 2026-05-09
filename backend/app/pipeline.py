"""
Main RAG pipeline orchestrator.

Flow:
1. Query expansion (multi-query + HyDE)
2. Embed all variants (Voyage, parallel)
3. Hybrid retrieval per variant → RRF fuse → top-30 children
4. Cohere rerank → top-6; track max_score
5. Parent-Document expansion
6. max_score < threshold → web fallback (kolzchut)
7. Router: Opus / Sonnet
8. Stream LLM answer
9. Verify citations (with retry)
10. Yield SSE events: {type: "delta"|"sources"|"done", ...}
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Optional

import anthropic
import structlog

from app.config import get_settings
from app.generation.citations import process_citations
from app.generation.llm import complete_answer, stream_answer
from app.generation.prompts import (
    SYSTEM_PROMPT,
    WEB_SYSTEM_PROMPT,
    build_rag_user_message,
    build_web_user_message,
)
from app.generation.router import route_model
from app.retrieval.embedder import embed_queries
from app.retrieval.parent_doc import get_parents
from app.retrieval.query_expansion import analyze_query
from app.retrieval.reranker import rerank
from app.retrieval.vectorstore import multi_hybrid_search
from app.web.kolzchut_search import WebResult, kolzchut_search

log = structlog.get_logger(__name__)


@dataclass
class SourceCard:
    source_id: str
    quote: str
    title: str
    url: Optional[str] = None
    filename: Optional[str] = None
    page: Optional[int] = None




async def run_pipeline(question: str, history: list[dict] | None = None) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields SSE-ready dicts:
      {"type": "delta", "text": "..."}          — streaming text chunk
      {"type": "sources", "sources": [...]}      — after full answer
      {"type": "done"}
      {"type": "error", "message": "..."}
    """
    settings = get_settings()

    try:
        # 1. Route + expand in one Haiku call
        history = history or []
        yield {"type": "status", "message": "מנתח שאלה..."}
        chitchat_reply, variants = await analyze_query(question, history)

        if chitchat_reply is not None:
            yield {"type": "delta", "text": chitchat_reply}
            yield {"type": "sources", "sources": []}
            yield {"type": "done"}
            return

        effective_variants = variants if variants else [question]
        log.info("pipeline_start", variants=len(effective_variants))

        # 2. Embed all variants
        yield {"type": "status", "message": "מחפש במסמכים..."}
        embeddings = await embed_queries(effective_variants)

        # 3. Multi-variant hybrid retrieval → top-30 children
        child_chunks = multi_hybrid_search(
            queries=effective_variants,
            query_vectors=embeddings,
            top_k=settings.bm25_top_k,
        )

        use_web = True
        parents: list[dict] = []
        web_results: list[WebResult] = []
        max_score = 0.0

        if child_chunks:
            # 4. Cohere rerank
            yield {"type": "status", "message": "בוחר קטעים רלוונטיים..."}
            reranked_children, max_score = rerank(question, child_chunks)
            log.info("reranked", max_score=round(max_score, 3))

            # 5. Parent expansion
            parents = get_parents(reranked_children)
            use_web = max_score < settings.confidence_threshold

        # 6. Always fetch web when PDF score is below threshold, or no PDF results
        if use_web:
            log.info("web_search", max_score=max_score)
            yield {"type": "status", "message": "מחפש במקורות מקוונים..."}
            web_results = await kolzchut_search(question)

        if not parents and not web_results:
            yield {"type": "delta", "text": "לא נמצאה תשובה במקורות הזמינים."}
            yield {"type": "sources", "sources": []}
            yield {"type": "done"}
            return

        # 7. Build prompt — combine PDF + web when both available
        if parents and web_results:
            system = SYSTEM_PROMPT
            user_msg = build_rag_user_message(question, parents) + \
                "\n\n" + build_web_user_message(question, web_results)
        elif web_results:
            system = WEB_SYSTEM_PROMPT
            user_msg = build_web_user_message(question, web_results)
        else:
            system = SYSTEM_PROMPT
            user_msg = build_rag_user_message(question, parents)

        # 8. Route model
        model = route_model(question)
        log.info("routed", model=model, use_web=use_web)

        # 9. Stream answer (collect for citation verification)
        yield {"type": "status", "message": "מנסח תשובה..."}
        full_text = ""
        async for delta in stream_answer(system, user_msg, model, history):
            full_text += delta
            yield {"type": "delta", "text": delta}

        # 10. Citation verification
        cleaned_text, verified_cites = process_citations(full_text, parents, web_results)

        # If no verified citations but we streamed content → retry once (non-streaming)
        if not verified_cites and (parents or web_results):
            log.info("citation_retry")
            retry_text, _ = await complete_answer(system, user_msg, model, history)
            cleaned_text, verified_cites = process_citations(retry_text, parents, web_results)
            # If retry produced verified cites, re-emit full text as a replacement
            if verified_cites:
                yield {"type": "replace", "text": cleaned_text}

        # Build source cards
        source_cards = _build_source_cards(verified_cites, parents, web_results)

        yield {"type": "sources", "sources": [_card_to_dict(c) for c in source_cards]}
        yield {"type": "done"}

    except anthropic.RateLimitError:
        log.warning("pipeline_rate_limit")
        yield {"type": "error", "message": "השרת עמוס כרגע. המתן מספר שניות ונסה שוב."}
    except Exception as exc:
        log.exception("pipeline_error", error=str(exc))
        yield {"type": "error", "message": "אירעה שגיאה בעיבוד השאלה. נסה שוב מאוחר יותר."}


def _build_source_cards(
    verified_cites,
    parents: list[dict],
    web_results: list[WebResult],
) -> list[SourceCard]:
    seen: set[str] = set()
    cards: list[SourceCard] = []

    cite_map: dict[str, str] = {}
    for c in verified_cites:
        cite_map.setdefault(c.source_id, c.quote)

    # From PDF parents
    for p in parents:
        meta = p.get("metadata", {})
        source = meta.get("source", p.get("parent_id", ""))
        page = meta.get("page")
        page_suffix = f":עמוד{page}" if page else ""
        source_id = f"{source}{page_suffix}"

        if source_id in cite_map and source_id not in seen:
            seen.add(source_id)
            cards.append(
                SourceCard(
                    source_id=source_id,
                    quote=cite_map[source_id],
                    title=source,
                    filename=source,
                    page=page,
                )
            )

    # From web
    for r in web_results:
        source_id = r.url
        if source_id in cite_map and source_id not in seen:
            seen.add(source_id)
            cards.append(
                SourceCard(
                    source_id=source_id,
                    quote=cite_map[source_id],
                    title=r.title,
                    url=r.url,
                )
            )

    return cards


def _card_to_dict(card: SourceCard) -> dict:
    return {
        "source_id": card.source_id,
        "quote": card.quote,
        "title": card.title,
        "url": card.url,
        "filename": card.filename,
        "page": card.page,
    }
