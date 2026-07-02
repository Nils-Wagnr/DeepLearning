"""RAG-style claim verification with top-k evidence and clear labels."""

from __future__ import annotations

import re
from typing import Any

from claimguard.claims.citations import strip_citations
from claimguard.models import Claim, ClaimVerification, EvidencePassage, Reference, ReferenceValidation
from claimguard.rag.retriever import EvidenceRetriever, build_evidence_passages, chunk_text, tokenize
from claimguard.rag.model_verifiers import (
    ModelVerifier,
    ModelVerifierUnavailable,
    create_model_verifier,
)
from claimguard.rag.sources import fetch_open_access_passages

TOP_K_EVIDENCE = 5
MIN_EVIDENCE_SCORE = 0.08

SUPPORT_LABELS = {
    "supported",
    "partially_supported",
    "not_supported",
    "contradicted",
    "insufficient_evidence",
}


class ClaimVerifier:
    """Verify cited factual claims against retrieved evidence passages."""

    def __init__(
        self,
        backend: str = "heuristic",
        model_verifier: ModelVerifier | None = None,
        strict_backend: bool = False,
    ) -> None:
        self.backend_name = backend.lower()
        self.model_verifier = model_verifier or create_model_verifier(self.backend_name)
        self.strict_backend = strict_backend

    def verify_claims(
        self,
        claims: list[Claim],
        references: list[Reference],
        validations: list[ReferenceValidation] | None = None,
        evidence_text: str = "",
    ) -> list[ClaimVerification]:
        """Verify all factual claims in a document."""

        passages = build_evidence_passages(evidence_text, references)
        passages.extend(_validation_abstract_passages(validations or []))
        passages.extend(fetch_open_access_passages(references, validations or []))
        retriever = EvidenceRetriever(passages)
        return [
            self.verify_claim(claim, references, retriever)
            for claim in claims
            if claim.claim_type == "factual_claim" and claim.citations
        ]

    def verify_claim(
        self,
        claim: Claim,
        references: list[Reference],
        retriever: EvidenceRetriever,
    ) -> ClaimVerification:
        """Verify one claim against a retrieval index."""

        if not claim.citations:
            return ClaimVerification(
                claim_index=claim.sentence_index,
                status="insufficient_evidence",
                confidence=0.0,
                evidence=[],
                rationale="The claim has no citation to retrieve evidence from.",
                verifier=self.backend_name,
            )

        cited_indices = map_citations_to_references(claim, references)
        query = strip_citations(claim.sentence)
        evidence = retriever.retrieve(
            query,
            set(cited_indices) if cited_indices else None,
            top_k=TOP_K_EVIDENCE,
        )

        evidence = [passage for passage in evidence if passage.score >= MIN_EVIDENCE_SCORE]
        if not evidence:
            return ClaimVerification(
                claim_index=claim.sentence_index,
                status="insufficient_evidence",
                confidence=0.0,
                evidence=[],
                rationale="No relevant evidence chunks were retrieved for the cited source.",
                cited_reference_indices=cited_indices,
                verifier=self.backend_name,
            )

        metadata: dict[str, Any] = {"retrieval_backend": retriever.backend}
        model = None
        latency_ms = None
        if self.model_verifier is None:
            status, confidence, rationale = _judge_support(query, evidence)
        else:
            try:
                verdict = self.model_verifier.verify(query, evidence)
                status = verdict.status
                confidence = verdict.confidence
                rationale = verdict.rationale
                model = verdict.model
                latency_ms = verdict.latency_ms
                metadata.update(verdict.metadata)
            except ModelVerifierUnavailable as exc:
                if self.strict_backend:
                    raise
                status = "insufficient_evidence"
                confidence = 0.0
                rationale = f"Selected verifier backend is unavailable: {exc}"
                model = getattr(self.model_verifier, "model", None)
                metadata["backend_error"] = str(exc)
        return ClaimVerification(
            claim_index=claim.sentence_index,
            status=status,
            confidence=confidence,
            evidence=evidence,
            rationale=rationale,
            cited_reference_indices=cited_indices,
            verifier=self.backend_name,
            model=model,
            latency_ms=latency_ms,
            metadata=metadata,
        )


def map_citations_to_references(claim: Claim, references: list[Reference]) -> list[str]:
    """Map citation markers to parsed reference indices when possible."""

    matched: list[str] = []
    indexed_references = {reference.index: reference for reference in references if reference.index}
    for citation in claim.citations:
        if citation.citation_type == "numeric":
            if citation.marker in indexed_references:
                matched.append(citation.marker)
            continue

        for reference in references:
            if citation.year and reference.year and citation.year != reference.year:
                continue
            author_blob = " ".join(reference.authors).lower()
            raw_blob = reference.raw_text.lower()
            hint = (citation.author_hint or "").lower()
            if hint and (hint in author_blob or hint in raw_blob):
                if reference.index:
                    matched.append(reference.index)
                break
    return sorted(set(matched), key=lambda item: int(item) if item.isdigit() else item)


def _judge_support(claim_text: str, evidence: list[EvidencePassage]) -> tuple[str, float, str]:
    combined = " ".join(passage.text for passage in evidence[:TOP_K_EVIDENCE])
    best_score = max((passage.score for passage in evidence), default=0.0)
    mean_top_score = sum(passage.score for passage in evidence[:3]) / max(1, len(evidence[:3]))
    coverage = _claim_coverage(claim_text, combined)
    lowered_claim = claim_text.lower()
    lowered_evidence = combined.lower()

    contradiction_strength = _contradiction_strength(lowered_claim, lowered_evidence)
    not_supported_strength = _not_supported_strength(lowered_evidence)

    if contradiction_strength >= 0.45:
        confidence = _confidence(best_score, mean_top_score, coverage, contradiction_strength)
        return (
            "contradicted",
            confidence,
            "Retrieved evidence contains negation, caveats, or opposite-direction language for the cited claim.",
        )

    if not_supported_strength >= 0.45:
        confidence = _confidence(best_score, mean_top_score, coverage, not_supported_strength)
        return (
            "not_supported",
            confidence,
            "Retrieved evidence says the cited source did not test or does not mention the claim.",
        )

    if best_score < 0.14 and coverage < 0.25:
        return (
            "insufficient_evidence",
            round(max(0.05, best_score), 3),
            "Retrieved chunks were too weakly related to assess support.",
        )

    if best_score >= 0.52 and coverage >= 0.55:
        return (
            "supported",
            _confidence(best_score, mean_top_score, coverage, 0.15),
            "Top evidence chunks strongly match the claim and cover most key terms.",
        )

    if best_score >= 0.25 or coverage >= 0.35:
        return (
            "partially_supported",
            _confidence(best_score, mean_top_score, coverage, 0.0, cap=0.78),
            "Evidence overlaps with the claim but leaves important terms, scope, or strength only partly established.",
        )

    return (
        "not_supported",
        _confidence(best_score, mean_top_score, coverage, 0.0, cap=0.62),
        "Relevant evidence was retrieved, but it did not establish the cited claim.",
    )


def _validation_abstract_passages(validations: list[ReferenceValidation]) -> list[EvidencePassage]:
    passages: list[EvidencePassage] = []
    for validation in validations:
        metadata = validation.metadata or {}
        abstract = metadata.get("abstract") or metadata.get("raw", {}).get("abstract")
        if not abstract:
            continue
        for index, chunk in enumerate(chunk_text(str(abstract))):
            passages.append(
                EvidencePassage(
                    text=chunk,
                    source=f"{validation.source}:abstract",
                    reference_index=validation.reference_index,
                    chunk_id=f"validation:{validation.reference_index}:abstract:{index}",
                    retrieval_method="unscored",
                    metadata={"validation_status": validation.status},
                )
            )
    return passages


def _claim_coverage(claim_text: str, evidence_text: str) -> float:
    claim_tokens = _important_claim_tokens(claim_text)
    evidence_tokens = tokenize(evidence_text)
    if not claim_tokens or not evidence_tokens:
        return 0.0
    return round(len(claim_tokens & evidence_tokens) / len(claim_tokens), 3)


def _important_claim_tokens(text: str) -> set[str]:
    tokens = tokenize(text)
    return {
        token
        for token in tokens
        if token
        not in {
            "study",
            "paper",
            "result",
            "show",
            "found",
            "report",
            "claim",
            "prior",
        }
    }


def _contradiction_strength(claim: str, evidence: str) -> float:
    strength = 0.0
    negation = r"\b(no|not|never|without|failed to|fails to|does not|do not|did not|cannot)\b"

    if re.search(r"\b(eliminate|eliminates|eliminated|all|always|never|requires no)\b", claim):
        if re.search(negation, evidence):
            strength = max(strength, 0.75)
        if re.search(r"\b(hallucinat|depends?|requires?|preprocess)\w*\b", evidence):
            strength = max(strength, 0.65)

    if re.search(r"\b(improves?|improved|increases?|increased|outperforms?|higher)\b", claim):
        if re.search(r"\b(no significant|did not improve|does not improve|worse|lower|decreased|reduced)\b", evidence):
            strength = max(strength, 0.75)

    if re.search(r"\b(reduces?|reduced|decreases?|decreased|lower)\b", claim):
        if re.search(r"\b(increased|higher|worse|did not reduce|does not reduce)\b", evidence):
            strength = max(strength, 0.75)

    if "requires no" in claim and re.search(r"\b(depends?|requires?|preprocess\w*)\b", evidence):
        strength = max(strength, 0.8)

    return strength


def _not_supported_strength(evidence: str) -> float:
    if re.search(
        r"\b(does not test|did not test|not evaluated|not evaluate|no evidence|not mention|unrelated)\b",
        evidence,
    ):
        return 0.7
    if re.search(r"\b(the source|this source|the article)\b.{0,80}\b(does not|did not|fails to)\b", evidence):
        return 0.6
    return 0.0


def _confidence(
    best_score: float,
    mean_top_score: float,
    coverage: float,
    cue_strength: float,
    cap: float = 0.92,
) -> float:
    value = (best_score * 0.42) + (mean_top_score * 0.20) + (coverage * 0.28) + (cue_strength * 0.10)
    return round(max(0.05, min(cap, value)), 3)
