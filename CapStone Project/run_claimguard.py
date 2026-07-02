"""Command line entry point for ClaimGuard document analysis."""

from __future__ import annotations

import argparse
import os

from claimguard.config import load_environment
from claimguard.pipeline import (
    analyze_document,
    write_claims_csv,
    write_json_report,
    write_markdown_report,
)
from claimguard.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze academic citation integrity.")
    parser.add_argument("--input", required=True, help="Path to a .txt or .pdf input document.")
    parser.add_argument("--output", required=True, help="Path for the JSON analysis report.")
    parser.add_argument(
        "--claims-csv",
        help="Optional path for a Module 1 claim/citation CSV export.",
    )
    api_group = parser.add_mutually_exclusive_group()
    api_group.add_argument(
        "--enable-apis",
        action="store_true",
        default=None,
        help="Enable CrossRef, Semantic Scholar, and OpenAlex validation.",
    )
    api_group.add_argument(
        "--disable-apis",
        action="store_false",
        dest="enable_apis",
        help="Disable scholarly API validation even if enabled in .env.",
    )
    parser.add_argument(
        "--verifier",
        choices=["heuristic", "ollama", "openai", "lora"],
        default="heuristic",
        help="Claim-evidence verifier backend.",
    )
    parser.add_argument(
        "--ai-detection",
        choices=["heuristic", "binoculars"],
        help="Enable optional paragraph-level AI-generated-text detection.",
    )
    parser.add_argument(
        "--fetch-full-text",
        action="store_true",
        help="Fetch a bounded number of open-access source PDFs (requires APIs/email).",
    )
    parser.add_argument("--markdown-output", help="Optional concise human-readable report path.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    args = parser.parse_args()

    load_environment()
    configure_logging(args.log_level)
    if args.fetch_full_text:
        os.environ["CLAIMGUARD_FETCH_FULL_TEXT"] = "true"
    report = analyze_document(
        args.input,
        enable_apis=args.enable_apis,
        verifier=args.verifier,
        ai_detection=args.ai_detection,
    )
    write_json_report(report, args.output)
    if args.claims_csv:
        write_claims_csv(report, args.claims_csv)
    if args.markdown_output:
        write_markdown_report(report, args.markdown_output)


if __name__ == "__main__":
    main()
