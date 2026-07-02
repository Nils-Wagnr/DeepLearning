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
from claimguard.rag.verifier import ClaimVerifier, SUPPORT_LABELS

LABEL_ORDER = [
    "supported",
    "partially_supported",
    "not_supported",
    "contradicted",
    "insufficient_evidence",
]


def evaluate_benchmark(
    benchmark_path: str | Path,
    verifier_backend: str = "heuristic",
    strict_backend: bool = False,
) -> dict[str, Any]:
    """Evaluate verifier labels against a CSV benchmark."""

    rows = _read_rows(benchmark_path)
    classifier = ClaimClassifier()
    verifier = ClaimVerifier(backend=verifier_backend, strict_backend=strict_backend)
    predictions: list[dict[str, Any]] = []
    confusion: dict[str, Counter[str]] = defaultdict(Counter)

    for index, row in enumerate(rows, start=1):
        claim_text = row["claim"].strip()
        evidence_text = row["evidence"].strip()
        expected = row["expected_label"].strip()
        case_id = row.get("case_id", "").strip() or f"row_{index}"
        category = row.get("category", "").strip() or "general"
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
            "case_id": case_id,
            "category": category,
            "claim": claim_text,
            "evidence_text": evidence_text,
            "expected": expected,
            "predicted": result.status,
            "confidence": result.confidence,
            "correct": result.status == expected,
            "rationale": result.rationale,
            "evidence": [asdict(item) for item in result.evidence],
            "verifier": result.verifier,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "metadata": result.metadata,
            "notes": row.get("notes", "").strip(),
        }
        predictions.append(prediction)
        confusion[expected][result.status] += 1

    correct = sum(1 for item in predictions if item["correct"])
    total = len(predictions)
    labels = _ordered_labels(predictions)
    per_label = _per_label_metrics(predictions, labels)
    macro_f1_labels = [label for label in labels if per_label[label]["support"] > 0]
    macro_f1 = _mean(per_label[label]["f1"] for label in macro_f1_labels)
    macro_precision = _mean(per_label[label]["precision"] for label in macro_f1_labels)
    macro_recall = _mean(per_label[label]["recall"] for label in macro_f1_labels)
    micro = _micro_metrics(predictions, labels)

    return {
        "benchmark": str(benchmark_path),
        "verifier": verifier_backend,
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0.0,
        "confusion_matrix": {key: dict(value) for key, value in confusion.items()},
        "metrics": {
            "accuracy": round(correct / total, 3) if total else 0.0,
            "macro_precision": macro_precision,
            "macro_recall": macro_recall,
            "macro_f1": macro_f1,
            "micro_precision": micro["precision"],
            "micro_recall": micro["recall"],
            "micro_f1": micro["f1"],
            "labels_evaluated": macro_f1_labels,
            "per_label": per_label,
        },
        "qualitative_examples": _qualitative_examples(predictions),
        "caveats": _evaluation_caveats(total, macro_f1_labels),
        "predictions": predictions,
        "runtime": {
            "model_calls": sum(1 for item in predictions if item.get("latency_ms") is not None),
            "total_latency_ms": sum(item.get("latency_ms") or 0 for item in predictions),
            "mean_latency_ms": round(
                sum(item.get("latency_ms") or 0 for item in predictions)
                / max(1, sum(1 for item in predictions if item.get("latency_ms") is not None)),
                1,
            ),
        },
    }


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"claim", "evidence", "expected_label"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Benchmark is missing columns: {sorted(missing)}")
        rows = [row for row in reader if any((value or "").strip() for value in row.values())]
        for row_number, row in enumerate(rows, start=2):
            expected = row.get("expected_label", "").strip()
            if expected not in SUPPORT_LABELS:
                raise ValueError(
                    f"Benchmark row {row_number} has unsupported expected_label {expected!r}."
                )
        return rows


def _ordered_labels(predictions: list[dict[str, Any]]) -> list[str]:
    observed = {
        item["expected"]
        for item in predictions
    } | {
        item["predicted"]
        for item in predictions
    }
    ordered = [label for label in LABEL_ORDER if label in observed]
    ordered.extend(sorted(observed - set(ordered)))
    return ordered


def _per_label_metrics(predictions: list[dict[str, Any]], labels: list[str]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for label in labels:
        true_positive = sum(
            1 for item in predictions if item["expected"] == label and item["predicted"] == label
        )
        false_positive = sum(
            1 for item in predictions if item["expected"] != label and item["predicted"] == label
        )
        false_negative = sum(
            1 for item in predictions if item["expected"] == label and item["predicted"] != label
        )
        support = true_positive + false_negative
        predicted_count = true_positive + false_positive
        precision = _safe_divide(true_positive, predicted_count)
        recall = _safe_divide(true_positive, support)
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        metrics[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "predicted_count": predicted_count,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
        }
    return metrics


def _micro_metrics(predictions: list[dict[str, Any]], labels: list[str]) -> dict[str, float]:
    true_positive = sum(1 for item in predictions if item["expected"] == item["predicted"])
    false_positive = sum(1 for item in predictions if item["predicted"] in labels and not item["correct"])
    false_negative = sum(1 for item in predictions if item["expected"] in labels and not item["correct"])
    precision = _safe_divide(true_positive, true_positive + false_positive)
    recall = _safe_divide(true_positive, true_positive + false_negative)
    return {
        "precision": precision,
        "recall": recall,
        "f1": _safe_divide(2 * precision * recall, precision + recall),
    }


def _qualitative_examples(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [item for item in predictions if not item["correct"]]
    correct = [item for item in predictions if item["correct"]]
    low_confidence_correct = sorted(correct, key=lambda item: item["confidence"])[:3]
    high_confidence_correct = sorted(correct, key=lambda item: item["confidence"], reverse=True)[:3]

    by_label: dict[str, list[dict[str, Any]]] = {}
    for label in LABEL_ORDER:
        label_items = [item for item in predictions if item["expected"] == label]
        by_label[label] = [_compact_example(item) for item in label_items[:2]]

    return {
        "misclassifications": [_compact_example(item) for item in errors[:5]],
        "high_confidence_correct": [_compact_example(item) for item in high_confidence_correct],
        "low_confidence_correct": [_compact_example(item) for item in low_confidence_correct],
        "examples_by_expected_label": by_label,
    }


def _compact_example(item: dict[str, Any]) -> dict[str, Any]:
    evidence = item.get("evidence", [])
    top_evidence = evidence[0] if evidence else {}
    return {
        "case_id": item["case_id"],
        "category": item["category"],
        "claim": item["claim"],
        "expected": item["expected"],
        "predicted": item["predicted"],
        "confidence": item["confidence"],
        "correct": item["correct"],
        "rationale": item["rationale"],
        "top_evidence": {
            "text": top_evidence.get("text"),
            "score": top_evidence.get("score"),
            "source": top_evidence.get("source"),
            "retrieval_method": top_evidence.get("retrieval_method"),
        },
    }


def _evaluation_caveats(total: int, labels: list[str]) -> list[str]:
    caveats = [
        "This benchmark is small and synthetic; metrics are useful for regression testing, not publication-grade validation.",
        "Evidence snippets are short abstracts/passages, so results do not measure full-paper source grounding.",
        "Labels were designed around the current five-way verifier taxonomy and should be reviewed by a human before being treated as gold annotations.",
        "Offline lexical retrieval is deterministic; optional embedding backends may change retrieval scores and therefore some labels.",
    ]
    if total < 30:
        caveats.append("The benchmark has fewer than 30 examples, so per-label precision and recall are high-variance.")
    missing_labels = [label for label in LABEL_ORDER if label not in labels]
    if missing_labels:
        caveats.append(
            "Macro-F1 excludes labels with no expected examples: " + ", ".join(missing_labels) + "."
        )
    return caveats


def _safe_divide(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _mean(values: Any) -> float:
    materialized = list(values)
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 3)
