"""Evaluate Module 2 parsing and online bibliographic validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from claimguard.config import load_environment
from claimguard.evaluation.bibliographic_evaluator import evaluate_bibliographic_validation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to pause between references to reduce public-API rate limiting.",
    )
    args = parser.parse_args()

    load_environment()
    report = evaluate_bibliographic_validation(
        args.benchmark,
        timeout_seconds=args.timeout,
        delay_seconds=max(0.0, args.delay),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
