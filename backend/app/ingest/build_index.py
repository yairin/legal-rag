"""
CLI: ingest all PDFs in data/pdfs/ → chunk → contextualize → embed → Qdrant + BM25.

Usage:
    python -m app.ingest.build_index [--pdf-dir data/pdfs] [--skip-context]
"""
from __future__ import annotations

import asyncio
import json
import pickle
from pathlib import Path

import click
import structlog
from tqdm import tqdm

from app.config import get_settings
from app.ingest.chunker import Chunk, Parent, chunk_document
from app.ingest.contextualize import add_context
from app.ingest.pdf_loader import load_pdf
from app.retrieval.embedder import embed_batch
from app.retrieval.vectorstore import upsert_chunks, init_collection

log = structlog.get_logger(__name__)

PARENTS_STORE = Path("data/parents_store.json")
BM25_CORPUS = Path("data/bm25_corpus.pkl")


def _save_parents(parents: list[Parent]) -> None:
    existing: dict = {}
    if PARENTS_STORE.exists():
        existing = json.loads(PARENTS_STORE.read_text(encoding="utf-8"))
    for p in parents:
        existing[p.parent_id] = {"text": p.text, "metadata": p.metadata}
    PARENTS_STORE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _save_bm25_corpus(children: list[Chunk]) -> None:
    existing: list[dict] = []
    if BM25_CORPUS.exists():
        with open(BM25_CORPUS, "rb") as fh:
            existing = pickle.load(fh)
    for c in children:
        existing.append({"chunk_id": c.chunk_id, "text": c.text, "metadata": c.metadata})
    with open(BM25_CORPUS, "wb") as fh:
        pickle.dump(existing, fh)


@click.command()
@click.option("--pdf-dir", default="data/pdfs", help="Directory with PDFs to ingest")
@click.option("--skip-context", is_flag=True, default=False, help="Skip Haiku contextualisation")
@click.option("--no-azure", is_flag=True, default=False, help="Force PyMuPDF (no Azure DI)")
@click.option("--fresh", is_flag=True, default=False, help="Delete existing index and start fresh")
def main(pdf_dir: str, skip_context: bool, no_azure: bool, fresh: bool) -> None:
    settings = get_settings()
    pdf_path = Path(pdf_dir)
    pdfs = sorted(pdf_path.glob("*.pdf"))
    if not pdfs:
        click.echo(f"No PDFs found in {pdf_dir}")
        return

    if fresh:
        for f in [PARENTS_STORE, BM25_CORPUS]:
            if f.exists():
                f.unlink()
                click.echo(f"Deleted {f}")

    click.echo(f"Found {len(pdfs)} PDFs. Initialising Qdrant collection…")
    init_collection(fresh=fresh)

    all_parents: list[Parent] = []
    all_children: list[Chunk] = []

    for pdf in tqdm(pdfs, desc="Loading PDFs"):
        pages = load_pdf(pdf, use_azure=not no_azure)
        parents, children = chunk_document(pages, source_name=pdf.name)
        all_parents.extend(parents)
        all_children.extend(children)

    click.echo(f"Total: {len(all_parents)} parents, {len(all_children)} children")

    if not skip_context:
        click.echo("Adding contextual prefixes (Haiku + prompt caching)…")
        all_children = add_context(all_parents, all_children)

    click.echo("Embedding children with Voyage…")
    texts = [c.text for c in all_children]
    embeddings = asyncio.run(embed_batch(texts))

    click.echo("Upserting to Qdrant…")
    upsert_chunks(all_children, embeddings)

    click.echo("Saving parents store + BM25 corpus…")
    PARENTS_STORE.parent.mkdir(parents=True, exist_ok=True)
    _save_parents(all_parents)
    _save_bm25_corpus(all_children)

    click.echo("Done!")


if __name__ == "__main__":
    main()
