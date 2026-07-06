"""Evaluate a Crossref-only bibliographic baseline on one report's references."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from claimguard.config import load_environment
from claimguard.parsing.document import DocumentParser, split_document_sections
from claimguard.validation.references import ApiLookupError, ReferenceParser, ReferenceValidator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    load_environment()
    text = DocumentParser().parse(args.input)
    references = ReferenceParser().parse(split_document_sections(text).references_text)
    validator = ReferenceValidator(enable_apis=True, timeout_seconds=args.timeout, max_results=3)
    rows = []
    for reference in references:
        try:
            candidate = validator._query_crossref(reference)  # controlled baseline: Crossref only
            error = None
        except ApiLookupError as exc:
            candidate = None
            error = str(exc)
        score = float(candidate.get("score", 0.0)) if candidate else 0.0
        status = "strong_match" if score >= 0.75 else "weak_match" if candidate else "unavailable"
        candidate_title = candidate.get("title") if candidate else None
        exact_title_match = bool(
            candidate_title
            and _normalized_title(reference.title or "") == _normalized_title(str(candidate_title))
        )
        rows.append(
            {
                "reference_index": reference.index,
                "parsed_title": reference.title,
                "parsed_year": reference.year,
                "parsed_venue": reference.venue,
                "crossref_status": status,
                "crossref_score": round(score, 3),
                "crossref_title": candidate_title,
                "crossref_year": candidate.get("year") if candidate else None,
                "crossref_doi": candidate.get("doi") if candidate else None,
                "error": error,
                "exact_title_match": exact_title_match,
            }
        )

    report = {
        "input": args.input,
        "tool": "Crossref REST API (title/bibliographic query only)",
        "total": len(rows),
        "strong_matches": sum(row["crossref_status"] == "strong_match" for row in rows),
        "exact_title_matches": sum(row["exact_title_match"] for row in rows),
        "weak_matches": sum(row["crossref_status"] == "weak_match" for row in rows),
        "unavailable": sum(row["crossref_status"] == "unavailable" for row in rows),
        "threshold": 0.75,
        "rows": rows,
        "caveat": (
            "Crossref is a bibliographic lookup baseline. It does not classify citation need "
            "or verify whether a source supports a claim."
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def _normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


if __name__ == "__main__":
    main()
