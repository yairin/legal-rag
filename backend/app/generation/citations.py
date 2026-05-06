"""
Citation verification: extract <cite> tags from LLM output and verify
each quoted text is a substring of at least one parent document.
Unverified citations are removed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)

_CITE_RE = re.compile(
    r'<cite\s+source="([^"]+)">([^<]+)</cite>',
    re.DOTALL,
)


@dataclass
class Citation:
    source_id: str
    quote: str
    verified: bool = False


def _normalize(text: str) -> str:
    """Normalize whitespace for substring matching."""
    return re.sub(r"\s+", " ", text).strip()


def extract_citations(llm_output: str) -> list[Citation]:
    citations = []
    for m in _CITE_RE.finditer(llm_output):
        source_id = m.group(1).strip()
        quote = _normalize(m.group(2))
        citations.append(Citation(source_id=source_id, quote=quote))
    return citations


def verify_citations(
    citations: list[Citation],
    parents: list[dict],
    web_results: list | None = None,
) -> list[Citation]:
    """
    Mark each citation as verified if the quote appears (as substring)
    in any parent document or web result.
    """
    # Build corpus of all source texts
    corpus: list[tuple[str, str]] = []
    for p in parents:
        meta = p.get("metadata", {})
        source = meta.get("source", p.get("parent_id", ""))
        page = meta.get("page", "")
        source_id = f"{source}:עמוד{page}" if page else source
        corpus.append((source_id, _normalize(p.get("text", ""))))

    if web_results:
        for r in web_results:
            corpus.append((r.url, _normalize(r.full_text or r.snippet)))

    for citation in citations:
        for source_id, text in corpus:
            if citation.quote and citation.quote in text:
                citation.verified = True
                break

    unverified = [c for c in citations if not c.verified]
    if unverified:
        log.warning("unverified_citations", count=len(unverified))

    return citations


def strip_unverified(llm_output: str, citations: list[Citation]) -> str:
    """Remove <cite> tags whose quote is not verified, keeping the text."""
    result = llm_output

    for citation in citations:
        tag_pattern = re.compile(
            r'<cite\s+source="' + re.escape(citation.source_id) + r'">'
            + re.escape(citation.quote)
            + r'</cite>',
            re.DOTALL,
        )
        if citation.verified:
            pass  # keep as-is
        else:
            # Replace the whole <cite>…</cite> with just the text
            result = tag_pattern.sub(citation.quote, result)

    return result


def process_citations(
    llm_output: str,
    parents: list[dict],
    web_results: list | None = None,
) -> tuple[str, list[Citation]]:
    """
    Full pipeline: extract → verify → strip unverified.
    Returns (cleaned_output, verified_citations).
    """
    citations = extract_citations(llm_output)
    citations = verify_citations(citations, parents, web_results)
    cleaned = strip_unverified(llm_output, citations)
    verified = [c for c in citations if c.verified]
    return cleaned, verified
