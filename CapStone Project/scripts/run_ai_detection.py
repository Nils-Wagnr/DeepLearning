"""Run optional paragraph-level AI-generated-text detection."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from claimguard.ai_detection import AIDetector
from claimguard.config import load_environment
from claimguard.parsing.document import DocumentParser, split_document_sections


def main() -> None:
    parser = argparse.ArgumentParser(description="Score document paragraphs for likely AI generation.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--method",
        choices=["heuristic", "binoculars", "fast_detect_gpt"],
        default="heuristic",
    )
    args = parser.parse_args()
    load_environment()
    text = DocumentParser().parse(args.input)
    main_text = split_document_sections(text).main_text
    results = AIDetector(args.method).detect_document(main_text)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"method": args.method, "results": [asdict(item) for item in results]}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
