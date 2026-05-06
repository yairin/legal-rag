"""
LLM router: classify question complexity and route to Opus 4 or Sonnet 4.6.

Heuristic rules (fast, no extra API call):
- Contains multi-part structure ("ו-", "או", multiple "?") → Opus
- Long question (> 120 chars) → Opus
- Contains complex legal terms → Opus
- Otherwise → Sonnet
"""
from __future__ import annotations

import re

_COMPLEX_TERMS = re.compile(
    r"ערעור|פסיקה|פרשנות|תקדים|חוקתי|בג[\"']צ|בית משפט עליון|"
    r"זכות יסוד|שיקול דעת|עקרון|אנלוגיה|לקוי|נכות|פיצויים|ירושה|"
    r"כשרות משפטית|כשרות להתדיינות|מינוי|אפוטרופוס"
)

_MULTI_PART = re.compile(r"\bו-|\bאו\b.*\?|^[^?]+\?[^?]+\?")


def route_model(question: str) -> str:
    """Returns the model ID to use for this question."""
    from app.config import get_settings
    settings = get_settings()

    if len(question) > 120:
        return settings.opus_model
    if _COMPLEX_TERMS.search(question):
        return settings.opus_model
    if _MULTI_PART.search(question):
        return settings.opus_model
    return settings.sonnet_model
