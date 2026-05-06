"""
Anthropic streaming LLM calls.
Yields text deltas; caller collects full text for citation verification.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Optional

import anthropic
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_MAX_OUTPUT_TOKENS = 2048
_MAX_ATTEMPTS = 5


def _retry_wait(attempt: int) -> float:
    """30s, 60s, 60s, 60s, 60s — rate limit window is 1 minute."""
    return min(30.0 * (attempt + 1), 60.0)


async def stream_answer(
    system_prompt: str,
    user_message: str,
    model: str,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields text delta strings.
    Retries up to 5 times on 429 rate-limit errors.
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with client.messages.stream(
                model=model,
                max_tokens=_MAX_OUTPUT_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
            return
        except anthropic.RateLimitError:
            if attempt == _MAX_ATTEMPTS - 1:
                raise
            wait = _retry_wait(attempt)
            log.warning("llm_rate_limit", attempt=attempt + 1, wait=wait, model=model)
            await asyncio.sleep(wait)


async def complete_answer(
    system_prompt: str,
    user_message: str,
    model: str,
) -> tuple[str, int]:
    """
    Non-streaming call. Returns (full_text, total_tokens).
    Used during citation retry. Retries on 429.
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=_MAX_OUTPUT_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text
            total_tokens = response.usage.input_tokens + response.usage.output_tokens
            return text, total_tokens
        except anthropic.RateLimitError:
            if attempt == _MAX_ATTEMPTS - 1:
                raise
            wait = _retry_wait(attempt)
            log.warning("llm_rate_limit", attempt=attempt + 1, wait=wait, model=model)
            await asyncio.sleep(wait)
