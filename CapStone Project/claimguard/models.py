"""Shared dataclasses for ClaimGuard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Citation:
    """A citation marker found in a sentence."""

    raw_text: str
    marker: str
    citation_type: str
    sentence_index: int
    year: int | None = None
    author_hint: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    group_id: str | None = None


@dataclass(slots=True)
class Claim:
    """A sentence-level claim classification."""

    sentence: str
    sentence_index: int
    claim_type: str
    citations: list[Citation] = field(default_factory=list)
    missing_citation: bool = False
    classification_confidence: float = 0.0
    classification_reason: str = ""
    section: str = "unknown"
    citation_context: str = "none"
    citation_required: bool = False
    flag_severity: str = "none"


@dataclass(slots=True)
class Reference:
    """A parsed bibliography entry."""

    raw_text: str
    index: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    venue: str | None = None


@dataclass(slots=True)
class ReferenceValidation:
    """Reference validation outcome from optional scholarly APIs."""

    reference_index: str | None
    status: str
    confidence: float
    source: str
    matched_title: str | None = None
    matched_year: int | None = None
    doi: str | None = None
    details: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidencePassage:
    """A retrieved evidence passage."""

    text: str
    source: str
    score: float = 0.0
    reference_index: str | None = None
    chunk_id: str | None = None
    retrieval_method: str = "lexical"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ClaimVerification:
    """RAG-style verification result for one claim."""

    claim_index: int
    status: str
    confidence: float
    evidence: list[EvidencePassage] = field(default_factory=list)
    rationale: str = ""
    cited_reference_indices: list[str] = field(default_factory=list)
    verifier: str = "heuristic"
    model: str | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIDetectionResult:
    """AI-generated-text detection result for one paragraph."""

    paragraph_index: int
    text: str
    label: str
    score: float
    confidence: float
    method: str
    rationale: str


@dataclass(slots=True)
class DocumentSections:
    """Text split into useful regions."""

    main_text: str
    references_text: str = ""
    evidence_text: str = ""
