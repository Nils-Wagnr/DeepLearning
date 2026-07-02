"""Run the same benchmark with baseline, local, frontier, and LoRA verifiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
            reports[backend] = evaluate_benchmark(
                args.benchmark,
                verifier_backend=backend,
                strict_backend=True,
            )
        except Exception as exc:
            reports[backend] = {"verifier": backend, "available": False, "error": str(exc)}
    leaderboard = []
    for backend, report in reports.items():
        if not isinstance(report, dict) or "metrics" not in report:
            continue
        leaderboard.append(
            {
                "verifier": backend,
                "accuracy": report["metrics"]["accuracy"],
                "macro_f1": report["metrics"]["macro_f1"],
                "mean_latency_ms": report["runtime"]["mean_latency_ms"],
            }
        )
    leaderboard.sort(key=lambda item: (item["macro_f1"], item["accuracy"]), reverse=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    comparison = {"benchmark": args.benchmark, "leaderboard": leaderboard, "reports": reports}
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
        "| Backend | Accuracy | Macro-F1 | Mean latency | Model calls |",
        "|---|---:|---:|---:|---:|",
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
            "| {verifier} | {accuracy:.3f} | {macro_f1:.3f} | {latency:.1f} ms | {calls} |".format(
                verifier=row["verifier"],
                accuracy=float(row["accuracy"]),
                macro_f1=float(row["macro_f1"]),
                latency=float(row["mean_latency_ms"]),
                calls=runtime.get("model_calls", "-"),
            )
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


if __name__ == "__main__":
    main()
