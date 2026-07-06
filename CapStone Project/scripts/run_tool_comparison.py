"""Compare predictions exported from ClaimGuard and existing tools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from claimguard.evaluation.tool_comparison import compare_tools


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare tools on a shared labeled benchmark.")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--tool",
        action="append",
        required=True,
        metavar="NAME=PATH",
        help="Prediction CSV/JSON; repeat for each tool.",
    )
    args = parser.parse_args()
    files: dict[str, str] = {}
    for specification in args.tool:
        if "=" not in specification:
            raise SystemExit("--tool must use NAME=PATH")
        name, path = specification.split("=", 1)
        files[name.strip()] = path.strip()
    report = compare_tools(args.benchmark, files)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
