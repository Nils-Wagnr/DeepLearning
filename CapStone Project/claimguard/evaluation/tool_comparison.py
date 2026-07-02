"""Shared benchmark comparison for ClaimGuard and external tools."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from claimguard.evaluation.evaluator import _micro_metrics, _per_label_metrics


def compare_tools(
    benchmark_path: str | Path,
    prediction_files: dict[str, str | Path],
) -> dict[str, Any]:
    expected = _read_expected(benchmark_path)
    reports: dict[str, Any] = {}
    for name, path in prediction_files.items():
        predicted = _read_predictions(path)
        rows = [
            {
                "case_id": case_id,
                "expected": label,
                "predicted": predicted.get(case_id, "missing"),
                "correct": predicted.get(case_id) == label,
            }
            for case_id, label in expected.items()
        ]
        labels = sorted(set(expected.values()))
        available = [row for row in rows if row["predicted"] != "missing"]
        per_label = _per_label_metrics(available, labels)
        micro = _micro_metrics(available, labels)
        macro_f1 = sum(item["f1"] for item in per_label.values()) / max(1, len(per_label))
        reports[name] = {
            "prediction_file": str(path),
            "coverage": round(len(available) / max(1, len(rows)), 3),
            "accuracy": round(
                sum(1 for row in available if row["correct"]) / max(1, len(available)), 3
            ),
            "macro_f1": round(macro_f1, 3),
            "micro_f1": micro["f1"],
            "per_label": per_label,
            "errors": [row for row in available if not row["correct"]],
            "missing_case_ids": [row["case_id"] for row in rows if row["predicted"] == "missing"],
        }
    leaderboard = sorted(
        (
            {"tool": name, "accuracy": item["accuracy"], "macro_f1": item["macro_f1"], "coverage": item["coverage"]}
            for name, item in reports.items()
        ),
        key=lambda item: (item["macro_f1"], item["coverage"]),
        reverse=True,
    )
    return {"benchmark": str(benchmark_path), "leaderboard": leaderboard, "tools": reports}


def _read_expected(path: str | Path) -> dict[str, str]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return {
            str(row["case_id"]).strip(): str(row["expected_label"]).strip()
            for row in csv.DictReader(handle)
        }


def _read_predictions(path: str | Path) -> dict[str, str]:
    source = Path(path)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        rows = payload.get("predictions", payload) if isinstance(payload, dict) else payload
        return {
            str(row["case_id"]).strip(): str(row.get("predicted", row.get("label", ""))).strip()
            for row in rows
        }
    with source.open("r", encoding="utf-8", newline="") as handle:
        return {
            str(row["case_id"]).strip(): str(row.get("predicted", row.get("label", ""))).strip()
            for row in csv.DictReader(handle)
        }
