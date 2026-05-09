"""
Query analysis: single Haiku call that both routes (chitchat vs legal)
and expands the query (paraphrases + HyDE). Uses conversation history for context.
"""
from __future__ import annotations

import anthropic
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_SYSTEM = """You are a router and query expander for a Hebrew legal assistant about Israeli municipal labor law.

You receive the latest user message, optionally preceded by recent conversation history.

CASE 1 — CHITCHAT: greeting, pleasantry, small talk, thanks, question about the bot, short yes/no/ok reply, or anything NOT a legal question:
Reply warmly in Hebrew (1–2 sentences), optionally invite a legal question.
Format: CHITCHAT: <your Hebrew response>

CASE 2 — LEGAL: a question about rights, work conditions, salary, benefits, contracts, regulations, dismissal, or anything requiring legal knowledge:
Provide two Hebrew paraphrases and a short hypothetical Hebrew legal answer.
Format:
LEGAL
PARA1: <first Hebrew paraphrase>
PARA2: <second Hebrew paraphrase>
HYDE: <3–4 sentence hypothetical answer as if from a Hebrew legal document>

CASE 3 — CLARIFY: the question is too vague to answer even with the conversation history (missing critical details):
Ask for the specific missing information in Hebrew.
Format: CLARIFY: <specific clarification question in Hebrew>

Important:
- Use conversation history to resolve references like "על זה", "באותו נושא", "ומה לגבי..." — treat them as legal questions with full context.
- When in doubt between LEGAL and CLARIFY → choose LEGAL.
- When in doubt between CHITCHAT and LEGAL → choose LEGAL."""


def _build_messages(question: str, history: list[dict]) -> list[dict]:
    messages = []
    for turn in history[-6:]:
        role = turn.get("role", "user")
        text = turn.get("text", "")
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": question})
    return messages


async def analyze_query(question: str, history: list[dict] | None = None) -> tuple[str | None, list[str]]:
    """
    Single Haiku call that routes and expands in one shot.

    Returns:
      (chitchat_reply, variants)
      - If chitchat or clarify: (reply_text, [])
      - If legal:               (None, [original, para1, para2, hyde])
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages = _build_messages(question, history or [])

    try:
        response = await client.messages.create(
            model=settings.haiku_model,
            max_tokens=400,
            system=_SYSTEM,
            messages=messages,
        )
        text = response.content[0].text.strip()
    except Exception as exc:
        log.warning("analyze_query_failed", error=str(exc))
        return None, [question]

    upper = text.upper()

    if upper.startswith("CHITCHAT"):
        reply = text[text.index(":") + 1:].strip() if ":" in text else "שלום! אשמח לעזור."
        return reply, []

    if upper.startswith("CLARIFY"):
        reply = text[text.index(":") + 1:].strip() if ":" in text else "תוכל לפרט את השאלה?"
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


async def expand_query(question: str) -> list[str]:
    _, variants = await analyze_query(question)
    return variants if variants else [question]
