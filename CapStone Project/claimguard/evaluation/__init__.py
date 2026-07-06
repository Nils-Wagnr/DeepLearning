"""Evaluation utilities."""

from claimguard.evaluation.evaluator import evaluate_benchmark
from claimguard.evaluation.bibliographic_evaluator import evaluate_bibliographic_validation
from claimguard.evaluation.tool_comparison import compare_tools
from claimguard.evaluation.claim_evaluator import evaluate_claim_detection
from claimguard.evaluation.reference_evaluator import evaluate_reference_parsing

__all__ = [
    "evaluate_benchmark",
    "evaluate_bibliographic_validation",
    "compare_tools",
    "evaluate_claim_detection",
    "evaluate_reference_parsing",
]
