"""
PDF loader: Azure Document Intelligence Layout (primary) + PyMuPDF (fallback).
Returns a list of {page: int, text: str} dicts preserving Hebrew/RTL reading order.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


@dataclass
class PageText:
    page: int
    text: str


def load_pdf(pdf_path: str | Path, *, use_azure: bool = True) -> list[PageText]:
    """Load a PDF and return per-page text, preferring Azure DI Layout."""
    from app.config import get_settings
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    settings = get_settings()
    has_azure = bool(settings.azure_di_endpoint and settings.azure_di_key)

    if use_azure and has_azure:
        try:
            return _load_azure(path)
        except Exception as exc:
            log.warning("azure_di_failed", path=str(path), error=str(exc))

    return _load_pymupdf(path)


def _load_azure(path: Path) -> list[PageText]:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential
    from app.config import get_settings

    settings = get_settings()
    client = DocumentIntelligenceClient(
        endpoint=settings.azure_di_endpoint,
        credential=AzureKeyCredential(settings.azure_di_key),
    )

    with open(path, "rb") as fh:
        poller = client.begin_analyze_document(
            "prebuilt-layout",
            body=fh,
            content_type="application/octet-stream",
        )

    result = poller.result()
    pages: list[PageText] = []

    for page in result.pages:
        page_num = page.page_number
        lines = [line.content for line in (page.lines or [])]
        text = "\n".join(lines).strip()
        if text:
            pages.append(PageText(page=page_num, text=text))

    log.info("azure_di_loaded", path=path.name, pages=len(pages))
    return pages


def _load_pymupdf(path: Path) -> list[PageText]:
    """
    Word-level RTL extraction: sort words right-to-left within each line,
    blocks top-to-bottom. Fixes Hebrew PDFs stored in visual (LTR) order.
    """
    import fitz  # pymupdf
    from itertools import groupby

    doc = fitz.open(str(path))
    pages: list[PageText] = []

    for i, page in enumerate(doc, start=1):
        # words: (x0, y0, x1, y1, word, block_no, line_no, word_no)
        words = page.get_text("words")
        if not words:
            continue

        # Find top y0 per block for top-to-bottom block ordering
        block_top: dict[int, float] = {}
        for w in words:
            bn = w[5]
            block_top[bn] = min(block_top.get(bn, w[1]), w[1])

        # Sort: block top-to-bottom, line top-to-bottom, word right-to-left
        words_sorted = sorted(
            words,
            key=lambda w: (block_top[w[5]], w[6], -w[0]),
        )

        line_texts: list[str] = []
        prev_block = None
        for (bn, ln), grp in groupby(words_sorted, key=lambda w: (w[5], w[6])):
            if prev_block is not None and bn != prev_block:
                line_texts.append("")  # blank line between blocks
            prev_block = bn
            line_text = " ".join(w[4] for w in grp)
            if line_text.strip():
                line_texts.append(line_text)

        text = "\n".join(line_texts).strip()
        if text:
            pages.append(PageText(page=i, text=text))

    doc.close()
    log.info("pymupdf_rtl_loaded", path=path.name, pages=len(pages))
    return pages
