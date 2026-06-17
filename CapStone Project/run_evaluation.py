"""Command line entry point for ClaimGuard benchmark evaluation."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from claimguard.evaluation import evaluate_benchmark
from claimguard.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ClaimGuard on a benchmark CSV.")
    parser.add_argument("--benchmark", required=True, help="Path to benchmark CSV.")
    parser.add_argument("--output", required=True, help="Path for evaluation JSON.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    args = parser.parse_args()

    configure_logging(args.log_level)
    report = evaluate_benchmark(args.benchmark)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Wrote evaluation report to %s", output)


if __name__ == "__main__":
    main()
