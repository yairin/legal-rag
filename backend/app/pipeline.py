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
from app.generation.llm import stream_answer
from app.generation.prompts import (
    SYSTEM_PROMPT,
    build_rag_user_message,
)
from app.generation.router import route_model
from app.retrieval.embedder import embed_queries
from app.retrieval.parent_doc import get_parents
from app.retrieval.query_expansion import analyze_query
from app.retrieval.reranker import rerank
from app.retrieval.vectorstore import multi_hybrid_search

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
        yield {"type": "status", "message": "מחפש..."}
        embeddings = await embed_queries(effective_variants)

        # 3. Multi-variant hybrid retrieval
        child_chunks = multi_hybrid_search(
            queries=effective_variants,
            query_vectors=embeddings,
            top_k=settings.bm25_top_k,
        )

        parents: list[dict] = []
        web_results: list[WebResult] = []

        if child_chunks:
            # 4. Cohere rerank
            reranked_children, max_score = rerank(question, child_chunks)
            log.info("reranked", max_score=round(max_score, 3))

            # 5. Parent expansion
            parents = get_parents(reranked_children)

        if not parents:
            yield {"type": "delta", "text": "מצטער, לא מצאתי מידע על כך במקורות הזמינים."}
            yield {"type": "sources", "sources": []}
            yield {"type": "done"}
            return

        # 7. Build prompt
        system = SYSTEM_PROMPT
        user_msg = build_rag_user_message(question, parents)

        # 8. Sonnet only (Opus too slow)
        model = settings.sonnet_model
        log.info("model", model=model)

        # 9. Stream answer
        yield {"type": "status", "message": "מנסח תשובה..."}
        full_text = ""
        async for delta in stream_answer(system, user_msg, model, history):
            full_text += delta
            yield {"type": "delta", "text": delta}

        # 10. Citation verification
        _, verified_cites = process_citations(full_text, parents, [])

        # Build source cards
        source_cards = _build_source_cards(verified_cites, parents)

        yield {"type": "sources", "sources": [_card_to_dict(c) for c in source_cards]}
        yield {"type": "done"}

    except anthropic.RateLimitError:
        log.warning("pipeline_rate_limit")
        yield {"type": "error", "message": "השרת עמוס כרגע. המתן מספר שניות ונסה שוב."}
    except anthropic.BadRequestError as exc:
        msg = str(exc)
        if "credit balance" in msg or "too low" in msg:
            log.error("pipeline_no_credits")
            yield {"type": "error", "message": "השירות אינו זמין כרגע עקב בעיית חיוב. אנא פנה למנהל המערכת."}
        else:
            log.exception("pipeline_bad_request", error=msg)
            yield {"type": "error", "message": "אירעה שגיאה בעיבוד השאלה. נסה שוב מאוחר יותר."}
    except Exception as exc:
        log.exception("pipeline_error", error=str(exc))
        yield {"type": "error", "message": "אירעה שגיאה בעיבוד השאלה. נסה שוב מאוחר יותר."}


def _clean_pdf_title(source: str) -> str:
    """Extract topic name from filename like '03 - פרק 3 – תנאי שירות.pdf'"""
    import re
    name = source.removesuffix(".pdf")
    # Remove leading "NN - פרק N – " pattern
    name = re.sub(r"^\d+\s*[-–]\s*פרק\s*\d+\s*[-–]\s*", "", name)
    # Remove leading "NN - " pattern
    name = re.sub(r"^\d+\s*[-–]\s*", "", name)
    return name.strip() or source


def _build_source_cards(
    verified_cites,
    parents: list[dict],
) -> list[SourceCard]:
    seen: set[str] = set()
    cards: list[SourceCard] = []

    cite_map: dict[str, str] = {}
    for c in verified_cites:
        cite_map.setdefault(c.source_id, c.quote)

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
                    title=_clean_pdf_title(source),
                    filename=source,
                    page=page,
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
