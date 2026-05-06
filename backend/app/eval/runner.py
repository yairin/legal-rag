"""
RAGAS evaluation runner.

Usage:
    python -m app.eval.runner [--gold-set data/eval/gold_set.json] [--fail-fast]

Exits with code 1 if any metric falls below threshold (CI gate).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click
import structlog
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from app.eval.ragas_metrics import EvalResult, THRESHOLDS
from app.pipeline import run_pipeline

log = structlog.get_logger(__name__)


async def _run_one(question: str) -> dict:
    """Run pipeline for one question, collect answer + contexts."""
    answer_parts: list[str] = []
    sources: list[dict] = []

    async for event in run_pipeline(question):
        if event["type"] == "delta":
            answer_parts.append(event["text"])
        elif event["type"] == "sources":
            sources = event.get("sources", [])

    answer = "".join(answer_parts)
    contexts = [s.get("quote", "") for s in sources if s.get("quote")]
    return {"answer": answer, "contexts": contexts}


async def _collect_results(gold_items: list[dict]) -> list[dict]:
    results = []
    for item in gold_items:
        q = item["question"]
        log.info("eval_question", question=q[:60])
        result = await _run_one(q)
        results.append({
            "question": q,
            "answer": result["answer"],
            "contexts": result["contexts"],
            "ground_truth": item.get("ground_truth", ""),
        })
    return results


@click.command()
@click.option("--gold-set", default="data/eval/gold_set.json")
@click.option("--fail-fast", is_flag=True, default=False)
def main(gold_set: str, fail_fast: bool) -> None:
    gold_path = Path(gold_set)
    if not gold_path.exists():
        click.echo(f"Gold set not found: {gold_path}", err=True)
        sys.exit(1)

    data = json.loads(gold_path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    if not questions:
        click.echo("Gold set is empty.", err=True)
        sys.exit(1)

    click.echo(f"Running eval on {len(questions)} questions…")
    results = asyncio.run(_collect_results(questions))

    dataset = Dataset.from_list(results)

    scores = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
    )

    eval_result = EvalResult(
        faithfulness=float(scores["faithfulness"]),
        answer_relevancy=float(scores["answer_relevancy"]),
        context_recall=float(scores["context_recall"]),
        context_precision=float(scores["context_precision"]),
    )

    click.echo(eval_result.report())

    if not eval_result.passes():
        sys.exit(1)


if __name__ == "__main__":
    main()
