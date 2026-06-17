"""RAG-style claim verification heuristics."""

from __future__ import annotations

import re

from claimguard.claims.citations import strip_citations
from claimguard.models import Claim, ClaimVerification, EvidencePassage, Reference, ReferenceValidation
from claimguard.rag.retriever import EvidenceRetriever, build_evidence_passages


class ClaimVerifier:
    """Verify cited factual claims against retrieved evidence passages."""

    def verify_claims(
        self,
        claims: list[Claim],
        references: list[Reference],
        validations: list[ReferenceValidation] | None = None,
        evidence_text: str = "",
    ) -> list[ClaimVerification]:
        """Verify all cited factual claims in a document."""

        del validations  # Reserved for future weighting with API metadata.
        passages = build_evidence_passages(evidence_text, references)
        retriever = EvidenceRetriever(passages)
        return [
            self.verify_claim(claim, references, retriever)
            for claim in claims
            if claim.claim_type == "factual_claim"
        ]

    def verify_claim(
        self,
        claim: Claim,
        references: list[Reference],
        retriever: EvidenceRetriever,
    ) -> ClaimVerification:
        """Verify one claim against the evidence index."""

        if not claim.citations:
            return ClaimVerification(
                claim_index=claim.sentence_index,
                status="insufficient_evidence",
                confidence=0.0,
                evidence=[],
                rationale="The claim has no citation to retrieve evidence from.",
            )

        cited_indices = map_citations_to_references(claim, references)
        query = strip_citations(claim.sentence)
        evidence = retriever.retrieve(query, set(cited_indices) if cited_indices else None)
        if not evidence:
            return ClaimVerification(
                claim_index=claim.sentence_index,
                status="insufficient_evidence",
                confidence=0.0,
                evidence=[],
                rationale="No evidence passages were available for the cited source.",
                cited_reference_indices=cited_indices,
            )

        status, confidence, rationale = _judge_support(query, evidence)
        return ClaimVerification(
            claim_index=claim.sentence_index,
            status=status,
            confidence=confidence,
            evidence=evidence,
            rationale=rationale,
            cited_reference_indices=cited_indices,
        )


def map_citations_to_references(claim: Claim, references: list[Reference]) -> list[str]:
    """Map citation markers to parsed reference indices when possible."""

    matched: list[str] = []
    for citation in claim.citations:
        if citation.citation_type == "numeric":
            if any(reference.index == citation.marker for reference in references):
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
    combined = " ".join(passage.text for passage in evidence[:3])
    best_score = max((passage.score for passage in evidence), default=0.0)
    lowered_claim = claim_text.lower()
    lowered_evidence = combined.lower()

    if _has_not_supported_cue(lowered_evidence):
        return (
            "not_supported",
            round(max(0.35, min(0.85, best_score + 0.25)), 3),
            "Retrieved evidence explicitly says the tested relationship was not evaluated or supported.",
        )

    if _has_contradiction(lowered_claim, lowered_evidence):
        return (
            "contradicted",
            round(max(0.45, min(0.9, best_score + 0.25)), 3),
            "Retrieved evidence contains negation or opposite-direction language for the claim.",
        )

    if best_score >= 0.46:
        return (
            "supported",
            round(min(0.95, best_score + 0.25), 3),
            "Retrieved evidence overlaps strongly with the main claim terms.",
        )
    if best_score >= 0.24:
        return (
            "partially_supported",
            round(min(0.75, best_score + 0.20), 3),
            "Retrieved evidence shares some key terms but does not fully establish the claim.",
        )
    return (
        "not_supported",
        round(min(0.6, best_score + 0.15), 3),
        "Retrieved evidence was available but did not match the claim closely.",
    )


def _has_contradiction(claim: str, evidence: str) -> bool:
    negation = r"\b(no|not|never|without|failed to|fails to|does not|do not|did not|cannot)\b"
    if re.search(r"\b(eliminate|eliminates|eliminated|all|always|never|requires no)\b", claim):
        if re.search(negation, evidence) or re.search(r"\b(hallucinat|depends?|requires?|preprocess)\w*\b", evidence):
            return True
    if re.search(r"\b(improves?|increases?|reduces?|outperforms?)\b", claim):
        return bool(re.search(r"\b(no significant|did not improve|does not improve|worse|lower)\b", evidence))
    if "requires no" in claim and re.search(r"\b(depends?|requires?|preprocess\w*)\b", evidence):
        return True
    return False


def _has_not_supported_cue(evidence: str) -> bool:
    return bool(
        re.search(
            r"\b(does not test|did not test|not evaluated|not evaluate|no evidence|not mention|unrelated)\b",
            evidence,
        )
    )
