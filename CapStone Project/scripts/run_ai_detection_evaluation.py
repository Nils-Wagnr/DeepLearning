"""Evaluate a configured AI-text detector on a labeled paragraph CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from claimguard.ai_detection import AIDetector
from claimguard.config import load_environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--method",
        choices=["heuristic", "binoculars", "fast_detect_gpt"],
        required=True,
    )
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    load_environment()
    rows = _read_rows(args.benchmark)
    detector = AIDetector(args.method)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    predictions = _load_checkpoint(output, args.benchmark, args.method)
    completed = {item["case_id"] for item in predictions}
    for index, row in enumerate(rows):
        if row["case_id"] in completed:
            continue
        result = None
        latency_ms = 0.0
        for attempt in range(max(0, args.retries) + 1):
            started = time.perf_counter()
            candidate = detector.detect(row["text"], index)
            latency_ms = (time.perf_counter() - started) * 1000
            if candidate.label != "unavailable":
                result = candidate
                break
            if attempt < max(0, args.retries):
                time.sleep(2**attempt)
        if result is None:
            _write_report(
                output,
                args.benchmark,
                args.method,
                predictions,
                complete=False,
                last_error=f"Stopped at {row['case_id']}: {candidate.rationale}",
            )
            raise RuntimeError(
                f"Detector unavailable at {row['case_id']}; rerun the command to resume"
            )
        predictions.append(
            {
                "case_id": row["case_id"],
                "expected": row["expected_label"],
                "predicted": _binary_label(result.label),
                "detector_label": result.label,
                "score": result.score,
                "latency_ms": round(latency_ms, 1),
                "citation_count": int(row.get("citation_count") or 0),
                "source": row.get("source", ""),
                "rationale": result.rationale,
            }
        )
        completed.add(row["case_id"])
        _write_report(output, args.benchmark, args.method, predictions, complete=False)
    _write_report(output, args.benchmark, args.method, predictions, complete=True)


def _build_report(
    benchmark: str,
    method: str,
    predictions: list[dict[str, Any]],
    complete: bool,
    last_error: str | None = None,
) -> dict[str, Any]:
    available = [item for item in predictions if item["predicted"] is not None]
    benchmark_path = Path(benchmark)
    return {
        "status": "complete" if complete else "in_progress",
        "benchmark": benchmark,
        "benchmark_sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        "method": method,
        "total": len(predictions),
        "available": len(available),
        "metrics": _binary_metrics(available),
        "mean_latency_ms": round(
            sum(item["latency_ms"] for item in available) / len(available), 1
        )
        if available
        else 0.0,
        "citation_patterns": _citation_patterns(available),
        "predictions": predictions,
        "last_error": last_error,
        "limitations": [
            "AI-detection labels require known generation provenance; report authorship is not inferred.",
            "Scores can fail after paraphrasing, editing, domain shift, or model changes.",
            "Citation association is descriptive and does not imply causation or misconduct.",
        ],
    }


def _write_report(
    output: Path,
    benchmark: str,
    method: str,
    predictions: list[dict[str, Any]],
    complete: bool,
    last_error: str | None = None,
) -> None:
    output.write_text(
        json.dumps(
            _build_report(benchmark, method, predictions, complete, last_error),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _load_checkpoint(
    output: Path,
    benchmark: str,
    method: str,
) -> list[dict[str, Any]]:
    if not output.exists():
        return []
    payload = json.loads(output.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(Path(benchmark).read_bytes()).hexdigest()
    if payload.get("benchmark_sha256") != expected_hash or payload.get("method") != method:
        raise ValueError("Existing checkpoint belongs to another benchmark or detector")
    return list(payload.get("predictions", []))


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"case_id", "text", "expected_label"}
    if not rows:
        raise ValueError("AI-detection benchmark has no rows")
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"AI-detection benchmark is missing columns: {sorted(missing)}")
    for number, row in enumerate(rows, start=2):
        if row["expected_label"] not in {"human", "ai"}:
            raise ValueError(f"Row {number} expected_label must be human or ai")
        if len(row["text"].split()) < 40:
            raise ValueError(f"Row {number} has fewer than 40 words")
    return rows


def _binary_label(label: str) -> str | None:
    if label == "likely_ai":
        return "ai"
    if label == "likely_human":
        return "human"
    return None


def _binary_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    tp = sum(row["expected"] == "ai" and row["predicted"] == "ai" for row in rows)
    tn = sum(row["expected"] == "human" and row["predicted"] == "human" for row in rows)
    fp = sum(row["expected"] == "human" and row["predicted"] == "ai" for row in rows)
    fn = sum(row["expected"] == "ai" and row["predicted"] == "human" for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "n": len(rows),
        "accuracy": round((tp + tn) / len(rows), 3) if rows else 0.0,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(2 * precision * recall / (precision + recall), 3)
        if precision + recall
        else 0.0,
        "auroc": _auroc(rows),
    }


def _auroc(rows: list[dict[str, Any]]) -> float | None:
    positives = [row for row in rows if row["expected"] == "ai"]
    negatives = [row for row in rows if row["expected"] == "human"]
    if not positives or not negatives:
        return None
    wins = sum(
        1 if positive["score"] > negative["score"] else 0.5
        if positive["score"] == negative["score"]
        else 0
        for positive in positives
        for negative in negatives
    )
    return round(wins / (len(positives) * len(negatives)), 3)


def _citation_patterns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {
        label: [row["citation_count"] for row in rows if row["predicted"] == label]
        for label in ("ai", "human")
    }
    return {
        f"mean_citations_predicted_{label}": round(sum(values) / len(values), 3)
        if values
        else None
        for label, values in groups.items()
    }


if __name__ == "__main__":
    main()
