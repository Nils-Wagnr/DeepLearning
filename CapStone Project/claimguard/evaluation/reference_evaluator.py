"""Offline benchmark for Module 2 bibliography parsing."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from claimguard.validation.fuzzy import fuzzy_score, normalize_text
from claimguard.validation.references import ReferenceParser


FIELDS = ("index", "title", "authors", "year", "doi", "venue")


def evaluate_reference_parsing(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    predictions: list[dict[str, Any]] = []
    correct = {field: 0 for field in FIELDS}
    for row in rows:
        parsed_items = ReferenceParser().parse(row["raw_reference"])
        parsed = parsed_items[0] if parsed_items else None
        checks = {field: False for field in FIELDS}
        if parsed:
            checks = {
                "index": normalize_text(parsed.index) == normalize_text(row["expected_index"]),
                "title": fuzzy_score(parsed.title, row["expected_title"]) >= 0.88,
                "authors": all(
                    normalize_text(author) in normalize_text(" ".join(parsed.authors))
                    for author in row["expected_authors"].split(";")
                    if author
                ),
                "year": str(parsed.year or "") == row["expected_year"],
                "doi": normalize_text(parsed.doi) == normalize_text(row["expected_doi"]),
                "venue": fuzzy_score(parsed.venue, row["expected_venue"]) >= 0.75,
            }
        for field, value in checks.items():
            correct[field] += int(value)
        predictions.append(
            {
                "case_id": row["case_id"],
                "checks": checks,
                "parsed": {
                    "index": parsed.index if parsed else None,
                    "title": parsed.title if parsed else None,
                    "authors": parsed.authors if parsed else [],
                    "year": parsed.year if parsed else None,
                    "doi": parsed.doi if parsed else None,
                    "venue": parsed.venue if parsed else None,
                },
            }
        )
    total = len(rows)
    return {
        "benchmark": str(path),
        "total": total,
        "field_accuracy": {
            field: round(value / max(1, total), 3) for field, value in correct.items()
        },
        "all_fields_accuracy": round(
            sum(all(item["checks"].values()) for item in predictions) / max(1, total), 3
        ),
        "errors": [item for item in predictions if not all(item["checks"].values())],
        "predictions": predictions,
    }
