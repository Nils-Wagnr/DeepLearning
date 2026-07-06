"""Gold-labeled evaluation for Module 2 bibliographic validation."""

from __future__ import annotations

import csv
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from claimguard.evaluation.evaluator import _per_label_metrics
from claimguard.validation.references import ReferenceParser, ReferenceValidator

GOLD_STATUSES = (
    "verified",
    "partially_matched",
    "unverified",
    "retracted_or_problematic",
)
EXISTING_STATUSES = {"verified", "partially_matched", "retracted_or_problematic"}


def evaluate_bibliographic_validation(
    benchmark_path: str | Path,
    timeout_seconds: int = 10,
    delay_seconds: float = 0.0,
) -> dict[str, Any]:
    """Evaluate parsing, metadata identity, DOI resolution, and retraction flags."""

    rows = _read_rows(benchmark_path)
    parser = ReferenceParser()
    validator = ReferenceValidator(enable_apis=True, timeout_seconds=timeout_seconds)
    predictions: list[dict[str, Any]] = []
    status_confusion: dict[str, Counter[str]] = defaultdict(Counter)

    for row_index, row in enumerate(rows):
        if row_index and delay_seconds > 0:
            time.sleep(delay_seconds)
        parsed = parser.parse(row["raw_reference"])
        reference = parsed[0] if parsed else None
        if reference is None:
            predicted_status = "unverified"
            validation_summary: dict[str, Any] = {
                "source": "parser",
                "confidence": 0.0,
                "details": "Reference parser returned no record.",
            }
            predicted_doi_valid = False if row["expected_doi_valid"] is not None else None
        else:
            validation = validator.validate(reference)
            predicted_status = validation.status
            metadata = validation.metadata or {}
            candidate_doi = metadata.get("doi")
            predicted_doi_valid = (
                _same_doi(reference.doi, candidate_doi)
                if row["expected_doi_valid"] is not None
                else None
            )
            validation_summary = {
                "source": validation.source,
                "confidence": validation.confidence,
                "matched_title": validation.matched_title,
                "matched_year": validation.matched_year,
                "doi": validation.doi,
                "details": validation.details,
                "candidate_is_retracted": bool(metadata.get("is_retracted")),
                "api_degraded": bool(metadata.get("api_failures"))
                or _api_degraded(validation.details),
                "api_failures": metadata.get("api_failures", []),
            }

        expected_status = row["expected_status"]
        predicted_exists = predicted_status in EXISTING_STATUSES
        predicted_retracted = predicted_status == "retracted_or_problematic"
        item = {
            "case_id": row["case_id"],
            "case_type": row["case_type"],
            "source_document": row["source_document"],
            "raw_reference": row["raw_reference"],
            "gold_notes": row["gold_notes"],
            "parser_record_count": len(parsed),
            "parsed": {
                "index": reference.index if reference else None,
                "title": reference.title if reference else None,
                "authors": reference.authors if reference else [],
                "year": reference.year if reference else None,
                "doi": reference.doi if reference else None,
                "venue": reference.venue if reference else None,
            },
            "expected_status": expected_status,
            "predicted_status": predicted_status,
            "status_correct": predicted_status == expected_status,
            "expected_exists": row["expected_exists"],
            "predicted_exists": predicted_exists,
            "exists_correct": predicted_exists == row["expected_exists"],
            "expected_doi_valid": row["expected_doi_valid"],
            "predicted_doi_valid": predicted_doi_valid,
            "doi_correct": (
                predicted_doi_valid == row["expected_doi_valid"]
                if row["expected_doi_valid"] is not None
                else None
            ),
            "expected_retracted": row["expected_retracted"],
            "predicted_retracted": predicted_retracted,
            "retraction_correct": predicted_retracted == row["expected_retracted"],
            "validation": validation_summary,
        }
        predictions.append(item)
        status_confusion[expected_status][predicted_status] += 1

    status_rows = [
        {
            "expected": item["expected_status"],
            "predicted": item["predicted_status"],
            "correct": item["status_correct"],
        }
        for item in predictions
    ]
    labels = list(GOLD_STATUSES)
    status_per_label = _per_label_metrics(status_rows, labels)
    status_macro_f1 = round(sum(values["f1"] for values in status_per_label.values()) / len(labels), 3)
    doi_items = [item for item in predictions if item["expected_doi_valid"] is not None]

    return {
        "benchmark": str(benchmark_path),
        "total": len(predictions),
        "case_type_counts": dict(Counter(item["case_type"] for item in predictions)),
        "parser": {
            "single_record_accuracy": _accuracy(
                item["parser_record_count"] == 1 for item in predictions
            ),
            "single_record_count": sum(item["parser_record_count"] == 1 for item in predictions),
        },
        "status_classification": {
            "accuracy": _accuracy(item["status_correct"] for item in predictions),
            "macro_f1": status_macro_f1,
            "per_label": status_per_label,
            "confusion_matrix": {key: dict(value) for key, value in status_confusion.items()},
        },
        "existence": _binary_metrics(
            [(item["expected_exists"], item["predicted_exists"]) for item in predictions]
        ),
        "doi_resolution": {
            **_binary_metrics(
                [(item["expected_doi_valid"], item["predicted_doi_valid"]) for item in doi_items]
            ),
            "applicable_cases": len(doi_items),
        },
        "retraction": _binary_metrics(
            [(item["expected_retracted"], item["predicted_retracted"]) for item in predictions]
        ),
        "api_unavailable_cases": [
            item["case_id"] for item in predictions if item["predicted_status"] == "api_unavailable"
        ],
        "api_degraded_cases": [
            item["case_id"]
            for item in predictions
            if item["validation"].get("api_degraded", False)
        ],
        "subset_accuracy": {
            case_type: _accuracy(
                item["status_correct"] for item in predictions if item["case_type"] == case_type
            )
            for case_type in sorted({item["case_type"] for item in predictions})
        },
        "errors": [item for item in predictions if not item["status_correct"]],
        "predictions": predictions,
        "limitations": [
            "Gold labels were manually assigned to authentic report references and controlled perturbations.",
            "The benchmark is small; retraction metrics have only two positive cases.",
            "API coverage and rate limits can change results over time.",
            "DOI validity means resolution to matching metadata, not legal or scientific validity of a work.",
        ],
    }


def _read_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        source = list(csv.DictReader(handle))
    required = {
        "case_id",
        "case_type",
        "source_document",
        "raw_reference",
        "expected_exists",
        "expected_status",
        "expected_doi_valid",
        "expected_retracted",
        "gold_notes",
    }
    missing = required - set(source[0] if source else {})
    if missing:
        raise ValueError(f"Benchmark is missing columns: {sorted(missing)}")
    rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(source, start=2):
        expected_status = row["expected_status"].strip()
        if expected_status not in GOLD_STATUSES:
            raise ValueError(f"Row {row_number} has unsupported expected_status {expected_status!r}")
        rows.append(
            {
                **row,
                "expected_exists": _parse_bool(row["expected_exists"], row_number),
                "expected_doi_valid": _parse_optional_bool(row["expected_doi_valid"], row_number),
                "expected_retracted": _parse_bool(row["expected_retracted"], row_number),
                "expected_status": expected_status,
            }
        )
    return rows


def _parse_bool(value: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Row {row_number} has invalid boolean {value!r}")


def _parse_optional_bool(value: str, row_number: int) -> bool | None:
    if value.strip().lower() in {"", "na", "n/a", "none"}:
        return None
    return _parse_bool(value, row_number)


def _binary_metrics(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    true_positive = sum(expected and predicted for expected, predicted in pairs)
    true_negative = sum(not expected and not predicted for expected, predicted in pairs)
    false_positive = sum(not expected and predicted for expected, predicted in pairs)
    false_negative = sum(expected and not predicted for expected, predicted in pairs)
    precision = _divide(true_positive, true_positive + false_positive)
    recall = _divide(true_positive, true_positive + false_negative)
    return {
        "n": len(pairs),
        "accuracy": _divide(true_positive + true_negative, len(pairs)),
        "precision": precision,
        "recall": recall,
        "f1": _divide(2 * precision * recall, precision + recall),
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def _same_doi(left: str | None, right: str | None) -> bool:
    def normalize(value: str | None) -> str:
        return (value or "").lower().replace("https://doi.org/", "").strip().rstrip(".,;)")

    return bool(normalize(left)) and normalize(left) == normalize(right)


def _api_degraded(details: str | None) -> bool:
    lowered = (details or "").lower()
    return any(
        marker in lowered
        for marker in ("http 429", "timeout", "network error", "lookup unavailable")
    )


def _accuracy(values: Any) -> float:
    materialized = list(values)
    return _divide(sum(bool(value) for value in materialized), len(materialized))


def _divide(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0
