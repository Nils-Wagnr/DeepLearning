"""Evaluate offline reference-field extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from claimguard.evaluation.reference_evaluator import evaluate_reference_parsing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate_reference_parsing(args.benchmark)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
