"""
CLI: generate candidate FAQ questions from indexed chunks using Claude Haiku,
then run each against the live pipeline to verify they produce good answers.
Verified questions are saved to data/samples.json.

Usage:
    python -m app.samples.generate_faq [--max-questions 20] [--out data/samples.json]
"""
from __future__ import annotations

import asyncio
import json
import pickle
import random
from pathlib import Path

import anthropic
import click
import structlog
from tqdm import tqdm

from app.config import get_settings

log = structlog.get_logger(__name__)

BM25_CORPUS = Path("data/bm25_corpus.pkl")

_FAQ_PROMPT = """\
בהתבסס על הקטע הבא ממסמך משפטי ישראלי, כתוב שאלה אחת שאדם אזרח ישראלי עשוי לשאול.
הכתוב שאלה בעברית, קצרה וממוקדת.
ענה רק בשאלה עצמה, ללא הסבר.

קטע:
{chunk}

שאלה:"""


async def _generate_question(client: anthropic.AsyncAnthropic, chunk: str, model: str) -> str:
    resp = await client.messages.create(
        model=model,
        max_tokens=100,
        messages=[{"role": "user", "content": _FAQ_PROMPT.format(chunk=chunk[:800])}],
    )
    return resp.content[0].text.strip()


async def _test_question(question: str) -> bool:
    """Run question through pipeline and check it returns a non-empty answer."""
    from app.pipeline import run_pipeline

    collected = ""
    has_sources = False
    async for event in run_pipeline(question):
        if event["type"] == "delta":
            collected += event["text"]
        elif event["type"] == "sources":
            has_sources = bool(event.get("sources"))

    return (
        len(collected) > 50
        and "לא נמצאה תשובה" not in collected
        and has_sources
    )


@click.command()
@click.option("--max-questions", default=20, help="Max sample questions to generate")
@click.option("--out", default="data/samples.json", help="Output path")
@click.option("--sample-chunks", default=50, help="Number of chunks to sample")
def main(max_questions: int, out: str, sample_chunks: int) -> None:
    if not BM25_CORPUS.exists():
        click.echo("BM25 corpus not found. Run build_index first.")
        return

    with open(BM25_CORPUS, "rb") as fh:
        corpus: list[dict] = pickle.load(fh)

    sampled = random.sample(corpus, min(sample_chunks, len(corpus)))
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run():
        questions: list[str] = []
        for doc in tqdm(sampled, desc="Generating questions"):
            try:
                q = await _generate_question(client, doc["text"], settings.haiku_model)
                if q:
                    questions.append(q)
            except Exception as exc:
                log.warning("generation_failed", error=str(exc))

        click.echo(f"Generated {len(questions)} candidate questions. Testing…")

        verified: list[str] = []
        for q in tqdm(questions, desc="Testing questions"):
            try:
                ok = await _test_question(q)
                if ok:
                    verified.append(q)
                if len(verified) >= max_questions:
                    break
            except Exception as exc:
                log.warning("test_failed", question=q, error=str(exc))

        return verified

    verified = asyncio.run(run())
    click.echo(f"Verified {len(verified)} sample questions.")

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"samples": verified}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    click.echo(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
