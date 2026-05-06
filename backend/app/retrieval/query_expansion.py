"""
Query analysis: single Haiku call that both routes (chitchat vs legal)
and expands the query (paraphrases + HyDE). Saves one round-trip vs doing
routing and expansion as separate calls.
"""
from __future__ import annotations

import anthropic
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_SYSTEM = """You are a router and query expander for a Hebrew legal assistant.

CASE 1 — If the message is chitchat (greeting, pleasantry, small talk, thanks,
question about the bot, short yes/no/ok reply, or anything that is NOT a legal question):
Reply in warm Hebrew (1–2 sentences), optionally invite a legal question.
Format your entire response as:
CHITCHAT: <your Hebrew response>

CASE 2 — If the message is a legal question (about rights, work, housing, contracts,
benefits, regulations, or anything requiring legal knowledge):
Provide two Hebrew paraphrases and a short hypothetical Hebrew legal answer.
Format your entire response as:
LEGAL
PARA1: <first Hebrew paraphrase>
PARA2: <second Hebrew paraphrase>
HYDE: <3–4 sentence hypothetical answer as if from a Hebrew legal document>

When in doubt → LEGAL."""


async def analyze_query(question: str) -> tuple[str | None, list[str]]:
    """
    Single Haiku call that routes and expands in one shot.

    Returns:
      (chitchat_reply, variants)
      - If chitchat: (reply_text, [])
      - If legal:    (None, [original, para1, para2, hyde])
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model=settings.haiku_model,
            max_tokens=400,
            system=_SYSTEM,
            messages=[{"role": "user", "content": question}],
        )
        text = response.content[0].text.strip()
    except Exception as exc:
        log.warning("analyze_query_failed", error=str(exc))
        return None, [question]

    if text.upper().startswith("CHITCHAT"):
        reply = text[text.index(":") + 1:].strip() if ":" in text else "שלום! אשמח לעזור."
        return reply, []

    # Parse LEGAL block
    variants = [question]
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("PARA1:"):
            v = line[6:].strip()
            if v:
                variants.append(v)
        elif line.upper().startswith("PARA2:"):
            v = line[6:].strip()
            if v:
                variants.append(v)
        elif line.upper().startswith("HYDE:"):
            v = line[5:].strip()
            if v:
                variants.append(v)

    log.debug("query_analyzed", variants=len(variants))
    return None, variants


# Keep expand_query as a thin wrapper for any code that still calls it directly
async def expand_query(question: str) -> list[str]:
    _, variants = await analyze_query(question)
    return variants if variants else [question]
