"""End-to-end ClaimGuard analysis pipeline."""

from __future__ import annotations

import json
import logging
import csv
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claimguard.claims.classifier import ClaimClassifier
from claimguard.parsing.document import DocumentParser, split_document_sections
from claimguard.parsing.sentences import split_sentences
from claimguard.rag.verifier import ClaimVerifier
from claimguard.validation.references import ReferenceParser, ReferenceValidator

LOGGER = logging.getLogger(__name__)


def analyze_document(input_path: str | Path, enable_apis: bool | None = None) -> dict[str, Any]:
    """Analyze one document and return a JSON-serializable report."""

    path = Path(input_path)
    parser = DocumentParser()
    raw_text = parser.parse(path)
    sections = split_document_sections(raw_text)
    sentences = split_sentences(sections.main_text)

    claims = ClaimClassifier().classify_many(sentences)
    references = ReferenceParser().parse(sections.references_text)
    validations = ReferenceValidator(enable_apis=enable_apis).validate_all(references)
    verifications = ClaimVerifier().verify_claims(
        claims=claims,
        references=references,
        validations=validations,
        evidence_text=sections.evidence_text,
    )

    module_1 = build_module_1_output(claims)
    claim_count = module_1["summary"]["factual_claims"]
    missing_citation_count = module_1["summary"]["factual_claims_missing_citations"]
    verification_counts: dict[str, int] = {}
    for result in verifications:
        verification_counts[result.status] = verification_counts.get(result.status, 0) + 1

    return {
        "tool": "ClaimGuard",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_path": str(path),
        "summary": {
            "sentences": len(sentences),
            "factual_claims": claim_count,
            "claims_missing_citations": missing_citation_count,
            "references": len(references),
            "verified_claim_status_counts": verification_counts,
        },
        "module_1": module_1,
        "claims": [asdict(claim) for claim in claims],
        "references": [asdict(reference) for reference in references],
        "reference_validation": [asdict(validation) for validation in validations],
        "claim_verification": [asdict(verification) for verification in verifications],
        "notes": [
            "Offline mode uses parsed references and sample evidence passages.",
            "API validation is disabled unless CLAIMGUARD_ENABLE_APIS=true or --enable-apis is passed.",
        ],
    }


def write_json_report(report: dict[str, Any], output_path: str | Path) -> None:
    """Write an analysis report to disk."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Wrote report to %s", path)


def build_module_1_output(claims: list[Any]) -> dict[str, Any]:
    """Build a clear Module 1 JSON section for claim and citation detection."""

    claim_dicts = [asdict(claim) for claim in claims]
    claim_type_counts = _count_values(claim["claim_type"] for claim in claim_dicts)
    citation_type_counts = _count_values(
        citation["citation_type"]
        for claim in claim_dicts
        for citation in claim["citations"]
    )
    factual_claims = [claim for claim in claim_dicts if claim["claim_type"] == "factual_claim"]
    missing = [claim for claim in factual_claims if claim["missing_citation"]]

    return {
        "name": "claim_and_citation_detection",
        "summary": {
            "sentences_analyzed": len(claim_dicts),
            "claim_type_counts": claim_type_counts,
            "citation_type_counts": citation_type_counts,
            "sentences_with_citations": sum(1 for claim in claim_dicts if claim["citations"]),
            "total_citation_markers": sum(len(claim["citations"]) for claim in claim_dicts),
            "factual_claims": len(factual_claims),
            "factual_claims_with_citations": len(factual_claims) - len(missing),
            "factual_claims_missing_citations": len(missing),
        },
        "claims": claim_dicts,
    }


def write_claims_csv(report: dict[str, Any], output_path: str | Path) -> None:
    """Write Module 1 claim/citation rows as a human-readable CSV file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sentence_index",
        "claim_type",
        "missing_citation",
        "classification_confidence",
        "classification_reason",
        "citation_count",
        "citation_markers",
        "citation_raw_text",
        "citation_types",
        "citation_years",
        "author_hints",
        "sentence",
    ]
    claims = report.get("module_1", {}).get("claims", report.get("claims", []))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for claim in claims:
            citations = claim.get("citations", [])
            writer.writerow(
                {
                    "sentence_index": claim.get("sentence_index"),
                    "claim_type": claim.get("claim_type"),
                    "missing_citation": claim.get("missing_citation"),
                    "classification_confidence": claim.get("classification_confidence"),
                    "classification_reason": claim.get("classification_reason"),
                    "citation_count": len(citations),
                    "citation_markers": _join_csv_values(citation.get("marker") for citation in citations),
                    "citation_raw_text": _join_csv_values(citation.get("raw_text") for citation in citations),
                    "citation_types": _join_csv_values(citation.get("citation_type") for citation in citations),
                    "citation_years": _join_csv_values(citation.get("year") for citation in citations),
                    "author_hints": _join_csv_values(citation.get("author_hint") for citation in citations),
                    "sentence": claim.get("sentence"),
                }
            )
    LOGGER.info("Wrote Module 1 CSV to %s", path)


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _join_csv_values(values: Any) -> str:
    return "; ".join(str(value) for value in values if value not in {None, ""})
