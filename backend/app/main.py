"""
FastAPI application:
  POST /api/chat        — SSE streaming RAG answer
  GET  /api/samples     — pre-vetted sample questions
  GET  /healthz         — health check
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Ensure Hebrew characters print correctly on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import structlog
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.pipeline import run_pipeline
from app.rate_limit import consume_tokens, get_daily_usage, limiter, verify_turnstile

# ── Logging ──────────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer() if get_settings().environment == "development"
        else structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Legal RAG API", version="1.0.0", docs_url=None, redoc_url=None)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda req, exc: HTTPException(
    status_code=429, detail="יותר מדי בקשות. המתן רגע ונסה שוב."
))
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_SAMPLES_PATH = Path(__file__).parent.parent / "data" / "samples.json"

# ── Schemas ───────────────────────────────────────────────────────────────────
class HistoryMessage(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    history: list[HistoryMessage] = Field(default_factory=list)
    turnstile_token: Optional[str] = Field(None)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "usage": get_daily_usage()}


@app.get("/api/samples")
async def get_samples():
    if not _SAMPLES_PATH.exists():
        return {"samples": []}
    data = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
    return {"samples": data.get("samples", [])}


@app.post("/api/chat")
async def chat(request: Request, body: ChatRequest = Body(...)):
    settings = get_settings()

    # Turnstile verification
    if settings.turnstile_secret and body.turnstile_token:
        remote_ip = request.client.host if request.client else ""
        valid = await verify_turnstile(body.turnstile_token, remote_ip)
        if not valid:
            raise HTTPException(status_code=403, detail="אימות כשל. נסה שוב.")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="השאלה ריקה.")

    log.info("chat_request", question_len=len(question))

    history = [{"role": m.role, "text": m.text} for m in body.history[-10:]]

    async def event_generator():
        token_count = 0
        try:
            async for event in run_pipeline(question, history):
                if event["type"] == "delta":
                    token_count += len(event["text"].split())
                yield {
                    "event": event["type"],
                    "data": json.dumps(event, ensure_ascii=False),
                }
        except Exception as exc:
            log.exception("stream_error", error=str(exc))
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": "שגיאת שרת."}, ensure_ascii=False),
            }
        finally:
            try:
                consume_tokens(token_count * 2, settings.daily_token_budget)
            except HTTPException:
                pass

    return EventSourceResponse(event_generator())
