"""
Legal-aware chunker: splits PDF pages into parent (section/chapter) chunks,
then further into child (~300 token) chunks.

Parent = a coherent legal section (detected by Hebrew section headers or page breaks).
Child  = ~300-token sliding window within a parent, with 50-token overlap.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

import tiktoken

# Hebrew legal section patterns: "סעיף X", "פרק X", numbered headings
_SECTION_RE = re.compile(
    r"^(?:סעיף|פרק|חלק|נספח|תוספת|ס'|ח')\s+[\dא-ת״\'\"]+",
    re.MULTILINE,
)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")
CHILD_TARGET = 300
CHILD_OVERLAP = 50


@dataclass
class Chunk:
    chunk_id: str
    parent_id: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Parent:
    parent_id: str
    text: str
    metadata: dict = field(default_factory=dict)


def _token_len(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def _split_into_tokens(text: str, target: int, overlap: int) -> list[str]:
    tokens = _TOKENIZER.encode(text)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + target, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(_TOKENIZER.decode(chunk_tokens))
        if end == len(tokens):
            break
        start += target - overlap
    return chunks


def _split_parents(full_text: str, source_name: str, start_page: int) -> list[tuple[str, int]]:
    """
    Returns list of (section_text, approx_page) tuples.
    Uses Hebrew section headers as natural boundaries; falls back to page-level splits.
    """
    # Try splitting on section headers
    matches = list(_SECTION_RE.finditer(full_text))
    if len(matches) >= 2:
        sections: list[tuple[str, int]] = []
        positions = [m.start() for m in matches] + [len(full_text)]
        for i in range(len(matches)):
            section_text = full_text[positions[i] : positions[i + 1]].strip()
            if section_text:
                sections.append((section_text, start_page))
        return sections

    # Fallback: treat entire text as one parent
    return [(full_text.strip(), start_page)]


def chunk_document(
    pages: list,  # list[PageText]
    source_name: str,
    doc_id: Optional[str] = None,
) -> tuple[list[Parent], list[Chunk]]:
    """
    Given a list of PageText objects (from pdf_loader), return (parents, children).
    """
    doc_id = doc_id or str(uuid.uuid4())

    # Merge all pages into a single text, track approximate page for each section
    full_text = "\n".join(p.text for p in pages)
    start_page = pages[0].page if pages else 1

    raw_sections = _split_parents(full_text, source_name, start_page)

    parents: list[Parent] = []
    children: list[Chunk] = []

    for section_text, approx_page in raw_sections:
        parent_id = str(uuid.uuid4())
        parent = Parent(
            parent_id=parent_id,
            text=section_text,
            metadata={
                "doc_id": doc_id,
                "source": source_name,
                "page": approx_page,
            },
        )
        parents.append(parent)

        # Split parent into children
        child_texts = _split_into_tokens(section_text, CHILD_TARGET, CHILD_OVERLAP)
        for idx, child_text in enumerate(child_texts):
            child_id = str(uuid.uuid4())
            children.append(
                Chunk(
                    chunk_id=child_id,
                    parent_id=parent_id,
                    text=child_text,
                    metadata={
                        "doc_id": doc_id,
                        "source": source_name,
                        "page": approx_page,
                        "child_index": idx,
                    },
                )
            )

    return parents, children
