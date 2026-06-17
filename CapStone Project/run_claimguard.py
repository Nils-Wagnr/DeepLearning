"""Command line entry point for ClaimGuard document analysis."""

from __future__ import annotations

import argparse

from claimguard.pipeline import analyze_document, write_claims_csv, write_json_report
from claimguard.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze academic citation integrity.")
    parser.add_argument("--input", required=True, help="Path to a .txt or .pdf input document.")
    parser.add_argument("--output", required=True, help="Path for the JSON analysis report.")
    parser.add_argument(
        "--claims-csv",
        help="Optional path for a Module 1 claim/citation CSV export.",
    )
    parser.add_argument(
        "--enable-apis",
        action="store_true",
        help="Enable CrossRef, Semantic Scholar, and OpenAlex validation.",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    args = parser.parse_args()

    configure_logging(args.log_level)
    report = analyze_document(args.input, enable_apis=args.enable_apis)
    write_json_report(report, args.output)
    if args.claims_csv:
        write_claims_csv(report, args.claims_csv)


if __name__ == "__main__":
    main()
