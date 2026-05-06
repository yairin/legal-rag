"""
Rate limiting + daily token budget + Cloudflare Turnstile verification.
"""
from __future__ import annotations

import asyncio
import time
from threading import Lock

import httpx
import structlog
from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

log = structlog.get_logger(__name__)

# Per-IP rate limiter
limiter = Limiter(key_func=get_remote_address)

# Daily token budget (simple in-memory; replace with Redis for multi-instance)
_token_lock = Lock()
_token_state: dict = {"date": "", "used": 0}

_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _today() -> str:
    import datetime
    return datetime.date.today().isoformat()


def consume_tokens(count: int, budget: int) -> None:
    with _token_lock:
        today = _today()
        if _token_state["date"] != today:
            _token_state["date"] = today
            _token_state["used"] = 0
        _token_state["used"] += count
        if _token_state["used"] > budget:
            raise HTTPException(status_code=429, detail="תקרת השימוש היומית הגיעה לסיומה. נסה מחר.")


def get_daily_usage() -> dict:
    with _token_lock:
        return {"date": _token_state["date"], "used": _token_state["used"]}


async def verify_turnstile(token: str, remote_ip: str) -> bool:
    """Verify Cloudflare Turnstile token. Returns True if valid."""
    from app.config import get_settings
    secret = get_settings().turnstile_secret

    if not secret:
        return True  # Skip in dev

    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.post(
                _TURNSTILE_VERIFY_URL,
                data={"secret": secret, "response": token, "remoteip": remote_ip},
            )
            data = resp.json()
            return data.get("success", False)
        except Exception as exc:
            log.warning("turnstile_verify_failed", error=str(exc))
            return False
