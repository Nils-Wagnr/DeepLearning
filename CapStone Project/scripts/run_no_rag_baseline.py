"""Run an OpenAI parametric-knowledge baseline without retrieval."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from claimguard.config import load_environment
from claimguard.evaluation.evaluator import LABEL_ORDER, _per_label_metrics
from claimguard.rag.model_verifiers import OpenAIResponsesVerifier
from claimguard.rag.model_verifiers import ModelVerifierUnavailable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    load_environment()

    rows = _read_rows(args.benchmark)
    verifier = OpenAIResponsesVerifier()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    predictions = _load_checkpoint(output, args.benchmark)
    completed_ids = {item["case_id"] for item in predictions}
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for index, row in enumerate(rows, start=1):
        case_id = row.get("case_id") or f"row_{index}"
        if case_id in completed_ids:
            continue
        verdict = None
        last_error = ""
        for attempt in range(max(0, args.retries) + 1):
            try:
                verdict = verifier.verify_without_evidence(row["claim"])
                break
            except ModelVerifierUnavailable as exc:
                last_error = str(exc)
                if attempt < max(0, args.retries):
                    time.sleep(2 ** attempt)
        if verdict is None:
            _write_checkpoint(output, args.benchmark, verifier.model, predictions, last_error)
            raise RuntimeError(
                f"No-RAG baseline stopped at {case_id}; rerun the same command to resume: "
                f"{last_error}"
            )
        expected = row["expected_label"]
        prediction = {
            "case_id": case_id,
            "claim": row["claim"],
            "expected": expected,
            "predicted": verdict.status,
            "correct": verdict.status == expected,
            "confidence": verdict.confidence,
            "rationale": verdict.rationale,
            "latency_ms": verdict.latency_ms,
            "model": verdict.model,
            "usage": (verdict.metadata.get("usage") or {}),
        }
        predictions.append(prediction)
        completed_ids.add(case_id)
        _write_checkpoint(output, args.benchmark, verifier.model, predictions)
        confusion[expected][verdict.status] += 1

    # Rebuild confusion for resumed predictions as well.
    confusion = defaultdict(Counter)
    for item in predictions:
        confusion[item["expected"]][item["predicted"]] += 1

    labels = [label for label in LABEL_ORDER if any(p["expected"] == label for p in predictions)]
    per_label = _per_label_metrics(predictions, labels)
    macro_f1 = _mean(per_label[label]["f1"] for label in labels)
    correct = sum(item["correct"] for item in predictions)
    usage = _usage(predictions)
    failures = Counter(
        (item["expected"], item["predicted"])
        for item in predictions
        if not item["correct"]
    )
    typical = failures.most_common(1)[0] if failures else None
    report = {
        "benchmark": args.benchmark,
        "baseline": "openai_no_rag_internal_ablation",
        "model": verifier.model,
        "total": len(predictions),
        "metrics": {
            "accuracy": round(correct / len(predictions), 3) if predictions else 0.0,
            "macro_f1": macro_f1,
            "per_label": per_label,
        },
        "confusion_matrix": {key: dict(value) for key, value in confusion.items()},
        "runtime": {
            "model_calls": len(predictions),
            "mean_latency_ms": round(
                sum(item["latency_ms"] for item in predictions) / len(predictions), 1
            ) if predictions else 0.0,
        },
        "token_usage": usage,
        "monetary_cost": "not_logged",
        "typical_failure": (
            f"{typical[0][0]} -> {typical[0][1]} ({typical[1]} cases)" if typical else None
        ),
        "predictions": predictions,
        "limitations": [
            "This is an internal no-retrieval ablation, not an existing-tool benchmark.",
            "Gold labels describe claim--evidence relations; some cannot be inferred from the claim alone.",
            "Monetary cost was not logged and is not reconstructed from changing provider prices.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row.get("claim") and row.get("expected_label")]


def _usage(predictions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        key: sum(int(item["usage"].get(key) or 0) for item in predictions)
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }


def _load_checkpoint(path: Path, benchmark: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("benchmark") != benchmark:
        raise ValueError(f"Existing checkpoint {path} belongs to another benchmark")
    return list(payload.get("predictions", []))


def _write_checkpoint(
    path: Path,
    benchmark: str,
    model: str,
    predictions: list[dict[str, Any]],
    error: str | None = None,
) -> None:
    payload = {
        "status": "in_progress",
        "benchmark": benchmark,
        "baseline": "openai_no_rag_internal_ablation",
        "model": model,
        "completed": len(predictions),
        "last_error": error,
        "predictions": predictions,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _mean(values: Any) -> float:
    materialized = list(values)
    return round(sum(materialized) / len(materialized), 3) if materialized else 0.0


if __name__ == "__main__":
    main()
