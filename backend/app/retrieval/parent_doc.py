"""
Parent-Document Retrieval: given child chunk IDs, fetch the full parent sections.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

_PARENTS_STORE_PATH = Path("data/parents_store.json")


@lru_cache(maxsize=1)
def _load_parents() -> dict[str, dict]:
    if not _PARENTS_STORE_PATH.exists():
        raise FileNotFoundError(f"Parents store not found: {_PARENTS_STORE_PATH}")
    with open(_PARENTS_STORE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def get_parents(child_chunks: list[dict]) -> list[dict]:
    """
    Given a list of child chunk payloads, return deduplicated parent dicts.
    Each returned dict: {parent_id, text, metadata}.
    """
    store = _load_parents()
    seen: set[str] = set()
    parents: list[dict] = []

    for chunk in child_chunks:
        pid = chunk.get("parent_id")
        if pid and pid not in seen:
            seen.add(pid)
            parent = store.get(pid)
            if parent:
                parents.append({"parent_id": pid, **parent})
            else:
                log.warning("parent_not_found", parent_id=pid)

    return parents
