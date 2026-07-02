"""Evaluation for Module 1 claim types and citation-needed flags."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from claimguard.claims.classifier import ClaimClassifier


def evaluate_claim_detection(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    classifier = ClaimClassifier()
    predictions: list[dict[str, Any]] = []
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for index, row in enumerate(rows):
        result = classifier.classify_sentence(
            row["sentence"],
            index,
            section=row.get("section", "unknown") or "unknown",
        )
        expected_type = row["expected_claim_type"]
        expected_missing = row["expected_missing_citation"].lower() == "true"
        confusion[expected_type][result.claim_type] += 1
        predictions.append(
            {
                "case_id": row["case_id"],
                "sentence": row["sentence"],
                "expected_claim_type": expected_type,
                "predicted_claim_type": result.claim_type,
                "expected_missing_citation": expected_missing,
                "predicted_missing_citation": result.missing_citation,
                "type_correct": expected_type == result.claim_type,
                "flag_correct": expected_missing == result.missing_citation,
            }
        )
    tp = sum(item["expected_missing_citation"] and item["predicted_missing_citation"] for item in predictions)
    fp = sum(not item["expected_missing_citation"] and item["predicted_missing_citation"] for item in predictions)
    fn = sum(item["expected_missing_citation"] and not item["predicted_missing_citation"] for item in predictions)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    total = len(predictions)
    labels = sorted(
        {item["expected_claim_type"] for item in predictions}
        | {item["predicted_claim_type"] for item in predictions}
    )
    per_label: dict[str, dict[str, float | int]] = {}
    for label in labels:
        tp_label = sum(
            item["expected_claim_type"] == label and item["predicted_claim_type"] == label
            for item in predictions
        )
        fp_label = sum(
            item["expected_claim_type"] != label and item["predicted_claim_type"] == label
            for item in predictions
        )
        fn_label = sum(
            item["expected_claim_type"] == label and item["predicted_claim_type"] != label
            for item in predictions
        )
        label_precision = tp_label / (tp_label + fp_label) if tp_label + fp_label else 0.0
        label_recall = tp_label / (tp_label + fn_label) if tp_label + fn_label else 0.0
        label_f1 = (
            2 * label_precision * label_recall / (label_precision + label_recall)
            if label_precision + label_recall
            else 0.0
        )
        per_label[label] = {
            "precision": round(label_precision, 3),
            "recall": round(label_recall, 3),
            "f1": round(label_f1, 3),
            "support": tp_label + fn_label,
        }
    supported_labels = [
        label for label in labels if int(per_label[label]["support"]) > 0
    ]
    return {
        "benchmark": str(path),
        "total": total,
        "claim_type_accuracy": round(
            sum(item["type_correct"] for item in predictions) / max(1, total), 3
        ),
        "claim_type_macro_f1": round(
            sum(float(per_label[label]["f1"]) for label in supported_labels)
            / max(1, len(supported_labels)),
            3,
        ),
        "claim_type_per_label": per_label,
        "citation_needed": {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
        },
        "confusion_matrix": {key: dict(value) for key, value in confusion.items()},
        "errors": [
            item for item in predictions if not item["type_correct"] or not item["flag_correct"]
        ],
        "predictions": predictions,
    }
