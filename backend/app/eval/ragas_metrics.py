"""
RAGAS metrics configuration for Hebrew legal RAG evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass

# Minimum thresholds — block deploy if any metric falls below
THRESHOLDS = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.80,
    "context_recall": 0.80,
    "context_precision": 0.75,
}


@dataclass
class EvalResult:
    faithfulness: float
    answer_relevancy: float
    context_recall: float
    context_precision: float

    def passes(self) -> bool:
        return (
            self.faithfulness >= THRESHOLDS["faithfulness"]
            and self.answer_relevancy >= THRESHOLDS["answer_relevancy"]
            and self.context_recall >= THRESHOLDS["context_recall"]
            and self.context_precision >= THRESHOLDS["context_precision"]
        )

    def report(self) -> str:
        lines = ["RAGAS Evaluation Report", "=" * 40]
        for metric, threshold in THRESHOLDS.items():
            value = getattr(self, metric)
            status = "✓" if value >= threshold else "✗ FAIL"
            lines.append(f"{metric:25s} {value:.3f}  (threshold: {threshold:.2f}) {status}")
        lines.append("=" * 40)
        lines.append("PASS" if self.passes() else "FAIL — deploy blocked")
        return "\n".join(lines)
