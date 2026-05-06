"""
Contextual Retrieval (Anthropic pattern):
For each child chunk, Claude Haiku generates a short Hebrew context string
that is prepended to the child text before embedding.

Uses prompt caching on the parent document to keep costs low.
"""
from __future__ import annotations

import asyncio
from typing import Sequence

import anthropic
import structlog

from app.config import get_settings
from app.ingest.chunker import Chunk, Parent

log = structlog.get_logger(__name__)

_SYSTEM = (
    "אתה עוזר משפטי. תפקידך לכתוב קטע הקשר קצר בעברית (2-4 משפטים) "
    "שמתאר במה עוסק הקטע הבא בתוך המסמך המשפטי הרחב יותר. "
    "הקטע ישמש לאחזור מידע — כתוב רק את ההקשר, ללא הסבר נוסף."
)

_USER_TMPL = """\
<document>
{parent_text}
</document>

<chunk>
{child_text}
</chunk>

כתוב קטע הקשר קצר בעברית לקטע זה בתוך המסמך:"""


async def _contextualize_one(
    client: anthropic.AsyncAnthropic,
    parent: Parent,
    child: Chunk,
    model: str,
    semaphore: asyncio.Semaphore,
) -> str:
    async with semaphore:
        for attempt in range(4):
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=200,
                    system=_SYSTEM,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"<document>\n{parent.text}\n</document>\n\n",
                                    "cache_control": {"type": "ephemeral"},
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        f"<chunk>\n{child.text}\n</chunk>\n\n"
                                        "כתוב קטע הקשר קצר בעברית לקטע זה בתוך המסמך:"
                                    ),
                                },
                            ],
                        }
                    ],
                )
                return response.content[0].text.strip()
            except anthropic.RateLimitError:
                wait = 2 ** (attempt + 2)  # 4s, 8s, 16s, 32s
                log.warning("rate_limit_backoff", attempt=attempt + 1, wait=wait)
                await asyncio.sleep(wait)
            except Exception as exc:
                log.warning("contextualize_failed", child_id=child.chunk_id, error=str(exc))
                return ""
        log.warning("contextualize_gave_up", child_id=child.chunk_id)
        return ""


async def add_context_async(
    parents: list[Parent],
    children: list[Chunk],
    concurrency: int = 3,  # stay under 50 req/min rate limit
) -> list[Chunk]:
    """
    Returns a new list of Chunk objects where each chunk's text is prefixed
    with the Haiku-generated context. Mutates the chunk in place.
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    semaphore = asyncio.Semaphore(concurrency)

    parent_map: dict[str, Parent] = {p.parent_id: p for p in parents}

    tasks = [
        _contextualize_one(
            client,
            parent_map[child.parent_id],
            child,
            settings.haiku_model,
            semaphore,
        )
        for child in children
    ]

    contexts = await asyncio.gather(*tasks)
    for child, ctx in zip(children, contexts):
        if ctx:
            child.text = f"{ctx}\n\n{child.text}"

    log.info("contextualized", total=len(children))
    return children


def add_context(parents: list[Parent], children: list[Chunk]) -> list[Chunk]:
    """Sync wrapper around add_context_async."""
    return asyncio.run(add_context_async(parents, children))
