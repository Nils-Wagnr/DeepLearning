"""Run the same benchmark with baseline, local, frontier, and LoRA verifiers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from claimguard.config import load_environment
from claimguard.evaluation import evaluate_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare ClaimGuard verifier backends fairly.")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--markdown-output",
        help="Optional readable comparison report with leaderboard and failure examples.",
    )
    parser.add_argument(
        "--verifiers",
        default="heuristic,ollama,openai",
        help="Comma-separated subset of heuristic,ollama,openai,lora.",
    )
    args = parser.parse_args()
    load_environment()
    reports: dict[str, object] = {}
    for backend in [item.strip() for item in args.verifiers.split(",") if item.strip()]:
        try:
            reports[backend] = _sanitize_report(
                evaluate_benchmark(
                    args.benchmark,
                    verifier_backend=backend,
                    strict_backend=True,
                )
            )
        except Exception as exc:
            reports[backend] = {"verifier": backend, "available": False, "error": str(exc)}
    leaderboard = []
    for backend, report in reports.items():
        if not isinstance(report, dict) or "metrics" not in report:
            continue
        usage = _aggregate_usage(report)
        leaderboard.append(
            {
                "verifier": backend,
                "n": report["total"],
                "accuracy": report["metrics"]["accuracy"],
                "macro_f1": report["metrics"]["macro_f1"],
                "agreement_with_gold": report["metrics"]["accuracy"],
                "mean_latency_ms": report["runtime"]["mean_latency_ms"],
                "model_calls": report["runtime"]["model_calls"],
                "token_usage": usage,
                "monetary_cost": "not_logged",
                "typical_failure": _typical_failure(report),
            }
        )
    leaderboard.sort(key=lambda item: (item["macro_f1"], item["accuracy"]), reverse=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    comparison = {
        "benchmark": args.benchmark,
        "leaderboard": leaderboard,
        "pairwise_agreement": _pairwise_agreement(reports),
        "cost_note": (
            "Monetary cost was not logged and is not inferred from changing provider prices. "
            "Token counts are aggregated where the backend returned them."
        ),
        "reports": reports,
    }
    output.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    if args.markdown_output:
        markdown = Path(args.markdown_output)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(_to_markdown(comparison), encoding="utf-8")


def _to_markdown(comparison: dict[str, object]) -> str:
    lines = [
        "# ClaimGuard model comparison",
        "",
        f"Benchmark: `{comparison['benchmark']}`",
        "",
        "## Leaderboard",
        "",
        "| Backend | N | Accuracy | Macro-F1 | Mean latency | Model calls | Tokens | Cost | Typical failure |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    reports = comparison.get("reports", {})
    assert isinstance(reports, dict)
    leaderboard = comparison.get("leaderboard", [])
    assert isinstance(leaderboard, list)
    for row in leaderboard:
        assert isinstance(row, dict)
        report = reports.get(str(row["verifier"]), {})
        runtime = report.get("runtime", {}) if isinstance(report, dict) else {}
        lines.append(
            "| {verifier} | {n} | {accuracy:.3f} | {macro_f1:.3f} | {latency:.1f} ms | "
            "{calls} | {tokens} | {cost} | {failure} |".format(
                verifier=row["verifier"],
                n=row["n"],
                accuracy=float(row["accuracy"]),
                macro_f1=float(row["macro_f1"]),
                latency=float(row["mean_latency_ms"]),
                calls=row.get("model_calls", runtime.get("model_calls", "-")),
                tokens=_format_usage(row.get("token_usage", {})),
                cost=row.get("monetary_cost", "not_logged"),
                failure=row.get("typical_failure") or "none observed",
            )
        )

    lines.extend(["", "## Pairwise agreement", "", "| Backends | Shared N | Agreement |", "|---|---:|---:|"])
    pairwise = comparison.get("pairwise_agreement", [])
    assert isinstance(pairwise, list)
    for item in pairwise:
        assert isinstance(item, dict)
        lines.append(
            f"| {item['left']} vs {item['right']} | {item['shared_n']} | "
            f"{float(item['agreement']):.3f} |"
        )

    lines.extend(["", "## Backend details", ""])
    for backend, report in reports.items():
        lines.extend([f"### {backend}", ""])
        if not isinstance(report, dict) or "metrics" not in report:
            error = report.get("error", "Backend unavailable") if isinstance(report, dict) else report
            lines.extend([f"Unavailable: `{error}`", ""])
            continue
        metrics = report["metrics"]
        lines.append(
            f"Accuracy **{float(metrics['accuracy']):.3f}**, Macro-F1 "
            f"**{float(metrics['macro_f1']):.3f}**."
        )
        lines.extend(["", "| Label | Precision | Recall | F1 | Support |", "|---|---:|---:|---:|---:|"])
        for label, values in metrics["per_label"].items():
            lines.append(
                f"| {label} | {float(values['precision']):.3f} | "
                f"{float(values['recall']):.3f} | {float(values['f1']):.3f} | "
                f"{values['support']} |"
            )
        failures = report.get("qualitative_examples", {}).get("misclassifications", [])
        lines.extend(["", "Representative errors:", ""])
        if not failures:
            lines.append("- None on this benchmark.")
        for item in failures[:3]:
            lines.append(
                f"- `{item['case_id']}`: expected **{item['expected']}**, predicted "
                f"**{item['predicted']}** (confidence {float(item['confidence']):.3f})."
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation limits",
            "",
            "- Compare backends only when they were run on the same benchmark and retrieval setup.",
            "- API and local-model latency depend on hardware, network load, and warm-up state.",
            "- This report records evidence, not proof of academic misconduct.",
            "",
        ]
    )
    return "\n".join(lines)


def _aggregate_usage(report: dict[str, Any]) -> dict[str, int | None]:
    openai_input = 0
    openai_output = 0
    openai_total = 0
    ollama_prompt = 0
    ollama_generated = 0
    saw_openai = False
    saw_ollama = False
    for prediction in report.get("predictions", []):
        metadata = prediction.get("metadata") or {}
        usage = metadata.get("usage") or {}
        if usage:
            saw_openai = True
            openai_input += int(usage.get("input_tokens") or 0)
            openai_output += int(usage.get("output_tokens") or 0)
            openai_total += int(usage.get("total_tokens") or 0)
        if "prompt_eval_count" in metadata or "eval_count" in metadata:
            saw_ollama = True
            ollama_prompt += int(metadata.get("prompt_eval_count") or 0)
            ollama_generated += int(metadata.get("eval_count") or 0)
    return {
        "input_tokens": openai_input if saw_openai else None,
        "output_tokens": openai_output if saw_openai else None,
        "total_tokens": openai_total if saw_openai else None,
        "prompt_tokens": ollama_prompt if saw_ollama else None,
        "generated_tokens": ollama_generated if saw_ollama else None,
    }


def _typical_failure(report: dict[str, Any]) -> str | None:
    failures = Counter(
        (item["expected"], item["predicted"])
        for item in report.get("predictions", [])
        if not item.get("correct")
    )
    if not failures:
        return None
    (expected, predicted), count = failures.most_common(1)[0]
    return f"{expected} -> {predicted} ({count} case{'s' if count != 1 else ''})"


def _pairwise_agreement(reports: dict[str, object]) -> list[dict[str, object]]:
    available = {
        backend: {
            item["case_id"]: item["predicted"]
            for item in report.get("predictions", [])
        }
        for backend, report in reports.items()
        if isinstance(report, dict) and "metrics" in report
    }
    rows: list[dict[str, object]] = []
    for left, right in combinations(available, 2):
        shared = sorted(set(available[left]) & set(available[right]))
        agreements = sum(available[left][case_id] == available[right][case_id] for case_id in shared)
        rows.append(
            {
                "left": left,
                "right": right,
                "shared_n": len(shared),
                "agreements": agreements,
                "agreement": round(agreements / len(shared), 3) if shared else 0.0,
            }
        )
    return rows


def _format_usage(usage: object) -> str:
    if not isinstance(usage, dict):
        return "not logged"
    if usage.get("total_tokens") is not None:
        return (
            f"{usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out "
            f"({usage.get('total_tokens', 0)} total)"
        )
    if usage.get("prompt_tokens") is not None:
        return f"{usage.get('prompt_tokens', 0)} prompt / {usage.get('generated_tokens', 0)} generated"
    return "not logged"


def _sanitize_report(report: dict[str, Any]) -> dict[str, Any]:
    """Remove provider/account request identifiers while preserving measured usage."""

    private_keys = {
        "response_id",
        "request_id",
        "response_organization",
        "response_project",
        "configured_project",
        "configured_organization",
    }

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if key not in private_keys}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(report)


if __name__ == "__main__":
    main()
