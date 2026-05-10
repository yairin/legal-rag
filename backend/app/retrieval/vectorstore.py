"""
Qdrant vector store: dense + BM25 hybrid retrieval with RRF fusion.
"""
from __future__ import annotations

import pickle
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Optional

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.ingest.chunker import Chunk

log = structlog.get_logger(__name__)

_VECTOR_DIM = 1024  # voyage-3-large
BM25_CORPUS_PATH = Path("data/bm25_corpus.pkl")

# RRF constant
_K = 60


_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        s = get_settings()
        # Extract hostname from URL for explicit REST connection
        host = s.qdrant_url.replace("https://", "").replace("http://", "").rstrip("/")
        _client = QdrantClient(
            host=host,
            port=443,
            https=True,
            api_key=s.qdrant_api_key,
            timeout=60,
            prefer_grpc=False,
        )
    return _client


def init_collection(fresh: bool = False) -> None:
    client = _get_client()
    settings = get_settings()
    col = settings.collection_name

    existing = [c.name for c in client.get_collections().collections]
    if col in existing:
        if fresh:
            client.delete_collection(col)
            log.info("collection_deleted", name=col)
        else:
            log.info("collection_exists", name=col)
            return

    client.create_collection(
        collection_name=col,
        vectors_config=VectorParams(size=_VECTOR_DIM, distance=Distance.COSINE),
    )
    log.info("collection_created", name=col)


def upsert_chunks(children: list[Chunk], embeddings: list[list[float]]) -> None:
    client = _get_client()
    settings = get_settings()

    points = [
        PointStruct(
            id=str(child.chunk_id),
            vector=emb,
            payload={
                "chunk_id": child.chunk_id,
                "parent_id": child.parent_id,
                "text": child.text,
                **child.metadata,
            },
        )
        for child, emb in zip(children, embeddings)
    ]

    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(
            collection_name=settings.collection_name,
            points=points[i : i + batch_size],
        )

    log.info("upserted", count=len(points))


def _dense_search(query_vector: list[float], top_k: int) -> list[tuple[str, float]]:
    """Returns list of (chunk_id, score)."""
    client = _get_client()
    settings = get_settings()

    results = client.query_points(
        collection_name=settings.collection_name,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    ).points
    return [(r.payload["chunk_id"], r.score) for r in results]


_HE_SUFFIXES = ("ים", "ות", "יות", "יים", "ני", "נית", "תי", "תית", "ות", "י", "ה", "ו", "ן", "ת", "ך")


def _he_tokenize(text: str) -> list[str]:
    """
    Tokenize Hebrew text and add stemmed variants.
    For each token, also emit a version with common suffixes stripped,
    so 'מצילי' also matches queries for 'מציל'.
    """
    tokens = text.split()
    expanded: list[str] = []
    for tok in tokens:
        expanded.append(tok)
        for suf in _HE_SUFFIXES:
            if tok.endswith(suf) and len(tok) - len(suf) >= 2:
                expanded.append(tok[: -len(suf)])
                break
    return expanded


@lru_cache(maxsize=1)
def _load_bm25() -> tuple[BM25Okapi, list[dict]]:
    if not BM25_CORPUS_PATH.exists():
        raise FileNotFoundError(f"BM25 corpus not found: {BM25_CORPUS_PATH}")
    with open(BM25_CORPUS_PATH, "rb") as fh:
        corpus: list[dict] = pickle.load(fh)
    tokenized = [_he_tokenize(doc["text"]) for doc in corpus]
    return BM25Okapi(tokenized), corpus


def _bm25_search(query: str, top_k: int) -> list[tuple[str, float]]:
    bm25, corpus = _load_bm25()
    scores = bm25.get_scores(_he_tokenize(query))
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [(corpus[i]["chunk_id"], float(scores[i])) for i in top_indices]


def _rrf_fuse(
    ranked_lists: list[list[tuple[str, float]]],
    k: int = _K,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion across multiple ranked lists."""
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def hybrid_search(
    query: str,
    query_vector: list[float],
    top_k: int,
) -> list[dict]:
    """
    Dense + BM25 hybrid, fused with RRF.
    Returns top_k dicts with chunk payload.
    """
    dense_results = _dense_search(query_vector, top_k)
    bm25_results = _bm25_search(query, top_k)

    fused = _rrf_fuse([dense_results, bm25_results])[:top_k]

    # Fetch full payloads for the fused IDs
    fused_ids = [fid for fid, _ in fused]
    client = _get_client()
    settings = get_settings()

    points = client.retrieve(
        collection_name=settings.collection_name,
        ids=fused_ids,
        with_payload=True,
    )
    payload_map = {str(p.id): p.payload for p in points}

    results = []
    for chunk_id, rrf_score in fused:
        payload = payload_map.get(chunk_id)
        if payload:
            results.append({**payload, "rrf_score": rrf_score})

    return results


def multi_hybrid_search(
    queries: list[str],
    query_vectors: list[list[float]],
    top_k: int,
) -> list[dict]:
    """
    Run hybrid search for multiple query variants, then RRF fuse all results.
    Returns top_k unique chunks.
    """
    all_ranked: list[list[tuple[str, float]]] = []

    for query, qvec in zip(queries, query_vectors):
        dense = _dense_search(qvec, top_k)
        bm25 = _bm25_search(query, top_k)
        all_ranked.extend([dense, bm25])

    fused = _rrf_fuse(all_ranked)[:top_k]
    fused_ids = [fid for fid, _ in fused]

    client = _get_client()
    settings = get_settings()
    points = client.retrieve(
        collection_name=settings.collection_name,
        ids=fused_ids,
        with_payload=True,
    )
    payload_map = {str(p.id): p.payload for p in points}

    results = []
    for chunk_id, rrf_score in fused:
        payload = payload_map.get(chunk_id)
        if payload:
            results.append({**payload, "rrf_score": rrf_score})

    return results
