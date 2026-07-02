"""End-to-end ClaimGuard analysis pipeline."""

from __future__ import annotations

import json
import logging
import csv
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claimguard.ai_detection import AIDetector
from claimguard.claims.classifier import ClaimClassifier
from claimguard.claims.citations import extract_citations
from claimguard.config import load_environment
from claimguard.parsing.document import DocumentParser, split_document_sections
from claimguard.parsing.sentences import split_sentences
from claimguard.rag.verifier import ClaimVerifier
from claimguard.validation.references import ReferenceParser, ReferenceValidator

LOGGER = logging.getLogger(__name__)


def analyze_document(
    input_path: str | Path,
    enable_apis: bool | None = None,
    verifier: str = "heuristic",
    ai_detection: str | None = None,
) -> dict[str, Any]:
    """Analyze one document and return a JSON-serializable report."""

    load_environment()
    path = Path(input_path)
    parser = DocumentParser()
    raw_text = parser.parse(path)
    sections = split_document_sections(raw_text)
    sentences = split_sentences(sections.main_text)

    claims = ClaimClassifier().classify_many(sentences)
    references = ReferenceParser().parse(sections.references_text)
    reference_validator = ReferenceValidator(enable_apis=enable_apis)
    validations = reference_validator.validate_all(references)
    verifications = ClaimVerifier(backend=verifier).verify_claims(
        claims=claims,
        references=references,
        validations=validations,
        evidence_text=sections.evidence_text,
    )
    ai_results = AIDetector(ai_detection).detect_document(sections.main_text) if ai_detection else []
    ai_citation_correlation = _ai_citation_correlation(ai_results)

    module_1 = build_module_1_output(claims)
    claim_count = module_1["summary"]["factual_claims"]
    missing_citation_count = module_1["summary"]["factual_claims_missing_citations"]
    verification_counts: dict[str, int] = {}
    for result in verifications:
        verification_counts[result.status] = verification_counts.get(result.status, 0) + 1

    reference_dicts = [asdict(reference) for reference in references]
    validation_dicts = [asdict(validation) for validation in validations]
    verification_dicts = [asdict(verification) for verification in verifications]
    return {
        "tool": "ClaimGuard",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_path": str(path),
        "configuration": {
            "apis_enabled": reference_validator.enable_apis,
            "verifier": verifier,
            "ai_detection": ai_detection,
        },
        "summary": {
            "sentences": len(sentences),
            "factual_claims": claim_count,
            "claims_missing_citations": missing_citation_count,
            "references": len(references),
            "verified_claim_status_counts": verification_counts,
        },
        "module_1": module_1,
        "module_2": {
            "name": "bibliographic_validation",
            "summary": {
                "references": len(references),
                "status_counts": _count_values(item.status for item in validations),
            },
            "references": reference_dicts,
            "validations": validation_dicts,
        },
        "module_3": {
            "name": "rag_claim_source_verification",
            "summary": {
                "claims_verified": len(verifications),
                "status_counts": verification_counts,
                "verifier_counts": _count_values(item.verifier for item in verifications),
                "retrieval_method_counts": _count_values(
                    evidence.retrieval_method
                    for item in verifications
                    for evidence in item.evidence
                ),
            },
            "verifications": verification_dicts,
        },
        "module_4": {
            "name": "ai_generated_text_detection",
            "enabled": bool(ai_detection),
            "summary": {
                "paragraphs": len(ai_results),
                "label_counts": _count_values(item.label for item in ai_results),
                "citation_correlation": ai_citation_correlation,
            },
            "results": [asdict(item) for item in ai_results],
        },
        "claims": [asdict(claim) for claim in claims],
        "references": reference_dicts,
        "reference_validation": validation_dicts,
        "claim_verification": verification_dicts,
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
            "flag_severity_counts": _count_values(claim["flag_severity"] for claim in missing),
            "citation_context_counts": _count_values(
                claim["citation_context"] for claim in claim_dicts if claim["citations"]
            ),
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
        "section",
        "citation_context",
        "citation_required",
        "flag_severity",
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
                    "section": claim.get("section"),
                    "citation_context": claim.get("citation_context"),
                    "citation_required": claim.get("citation_required"),
                    "flag_severity": claim.get("flag_severity"),
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


def write_markdown_report(report: dict[str, Any], output_path: str | Path) -> None:
    """Write a concise, human-readable integrity report."""

    summary = report.get("summary", {})
    configuration = report.get("configuration", {})
    reference_summary = report.get("module_2", {}).get("summary", {})
    verification_summary = report.get("module_3", {}).get("summary", {})
    missing = [
        item
        for item in report.get("module_1", {}).get("claims", [])
        if item.get("missing_citation")
    ]
    verifications = report.get("claim_verification", [])
    lines = [
        "# ClaimGuard integrity report",
        "",
        f"Input: `{report.get('input_path', '')}`",
        "",
        f"Verifier: `{configuration.get('verifier', 'heuristic')}`",
        "",
        "## Summary",
        "",
        f"- Sentences: {summary.get('sentences', 0)}",
        f"- Factual claims: {summary.get('factual_claims', 0)}",
        f"- Citation-needed flags: {summary.get('claims_missing_citations', 0)}",
        f"- Parsed references: {summary.get('references', 0)}",
        f"- Reference validation: {reference_summary.get('status_counts', {})}",
        f"- Claim verification: {verification_summary.get('status_counts', {})}",
        "",
        "## Citation-needed flags",
        "",
    ]
    if not missing:
        lines.append("No uncited external factual claims were flagged.")
    for item in missing:
        lines.extend(
            [
                f"### Sentence {item.get('sentence_index')} — {item.get('flag_severity', 'medium')}",
                "",
                str(item.get("sentence", "")),
                "",
            ]
        )
    lines.extend(["## Source-support review", ""])
    if not verifications:
        lines.append("No cited factual claims reached source verification.")
    by_index = {item.get("sentence_index"): item for item in report.get("claims", [])}
    for item in verifications:
        claim = by_index.get(item.get("claim_index"), {})
        metadata = item.get("metadata") or {}
        usage = metadata.get("usage") or {}
        evidence = item.get("evidence") or []
        lines.extend(
            [
                f"### Sentence {item.get('claim_index')} — {item.get('status')}",
                "",
                str(claim.get("sentence", "")),
                "",
                f"- Backend: `{item.get('verifier', 'heuristic')}`",
                f"- Model: `{item.get('model') or 'not called'}`",
                f"- Confidence: `{item.get('confidence', 0)}`",
                f"- Latency: `{item.get('latency_ms') if item.get('latency_ms') is not None else 'n/a'} ms`",
                f"- Cited references: `{', '.join(item.get('cited_reference_indices') or []) or 'none'}`",
                f"- Tokens: input `{usage.get('input_tokens', 'n/a')}`, output `{usage.get('output_tokens', 'n/a')}`, total `{usage.get('total_tokens', 'n/a')}`",
                f"- Response ID: `{metadata.get('response_id') or 'n/a'}`",
                "",
                f"Rationale: {item.get('rationale', '')}",
                "",
            ]
        )
        if evidence:
            top = evidence[0]
            top_text = str(top.get("text", "")).replace("\n", " ")
            lines.extend(
                [
                    f"Top evidence (`{top.get('source', 'unknown')}`, score `{top.get('score', 0)}`):",
                    "",
                    f"> {top_text}",
                    "",
                ]
            )
    lines.extend(
        [
            "## Interpretation warning",
            "",
            "ClaimGuard is a triage tool. Every flag requires human review; AI-text scores are not proof of authorship.",
            "",
        ]
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("Wrote Markdown report to %s", path)


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _join_csv_values(values: Any) -> str:
    return "; ".join(str(value) for value in values if value not in {None, ""})


def _ai_citation_correlation(results: list[Any]) -> dict[str, Any]:
    """Descriptive AI-score/citation summary; never interpreted as causation."""

    cited_scores: list[float] = []
    uncited_scores: list[float] = []
    for result in results:
        target = cited_scores if extract_citations(result.text, result.paragraph_index) else uncited_scores
        if result.label not in {"unavailable", "insufficient_text"}:
            target.append(float(result.score))
    return {
        "cited_paragraphs_scored": len(cited_scores),
        "uncited_paragraphs_scored": len(uncited_scores),
        "mean_ai_score_cited": round(sum(cited_scores) / len(cited_scores), 3) if cited_scores else None,
        "mean_ai_score_uncited": round(sum(uncited_scores) / len(uncited_scores), 3)
        if uncited_scores
        else None,
        "warning": "Descriptive association only; AI scores are not reliable authorship labels.",
    }
