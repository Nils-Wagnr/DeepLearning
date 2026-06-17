"""Benchmark evaluation for ClaimGuard."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from claimguard.claims.classifier import ClaimClassifier
from claimguard.models import Reference
from claimguard.rag.retriever import EvidenceRetriever, build_evidence_passages
from claimguard.rag.verifier import ClaimVerifier


def evaluate_benchmark(benchmark_path: str | Path) -> dict[str, Any]:
    """Evaluate verifier labels against a CSV benchmark."""

    rows = _read_rows(benchmark_path)
    classifier = ClaimClassifier()
    verifier = ClaimVerifier()
    predictions: list[dict[str, Any]] = []
    confusion: dict[str, Counter[str]] = defaultdict(Counter)

    for index, row in enumerate(rows, start=1):
        claim_text = row["claim"].strip()
        evidence_text = row["evidence"].strip()
        expected = row["expected_label"].strip()
        reference = Reference(
            raw_text=f"[1] Benchmark evidence. {evidence_text}",
            index="1",
            title="Benchmark evidence",
            year=None,
        )
        claim = classifier.classify_sentence(f"{claim_text} [1]", index)
        retriever = EvidenceRetriever(build_evidence_passages(f"[1] {evidence_text}", [reference]))
        result = verifier.verify_claim(claim, [reference], retriever)
        prediction = {
            "row": index,
            "claim": claim_text,
            "expected": expected,
            "predicted": result.status,
            "confidence": result.confidence,
            "correct": result.status == expected,
            "rationale": result.rationale,
            "evidence": [asdict(item) for item in result.evidence],
        }
        predictions.append(prediction)
        confusion[expected][result.status] += 1

    correct = sum(1 for item in predictions if item["correct"])
    total = len(predictions)
    return {
        "benchmark": str(benchmark_path),
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0.0,
        "confusion_matrix": {key: dict(value) for key, value in confusion.items()},
        "predictions": predictions,
    }


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"claim", "evidence", "expected_label"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Benchmark is missing columns: {sorted(missing)}")
        return list(reader)

