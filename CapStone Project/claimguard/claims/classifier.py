"""Sentence-level claim classification."""

from __future__ import annotations

import re

from claimguard.claims.citations import extract_citations
from claimguard.models import Claim


class ClaimClassifier:
    """Classify sentences into broad academic claim categories."""

    FACTUAL_PATTERNS = (
        r"\b(found|reported|showed|demonstrated|observed|concluded|indicated|estimated|measured|documented)\b",
        r"\b(improves?|improved|increases?|increased|reduces?|reduced|outperforms?|achieves?|achieved)\b",
        r"\b(is associated with|are associated with|correlates? with|causes?|predicts?|leads? to|results? in)\b",
        r"\b(requires?|contains?|consists? of|depends? on|uses?|relies? on)\b",
        r"\b(has been|have been|is widely|are widely|is commonly|are commonly)\b",
        r"\b\d+(?:\.\d+)?\s*(%|percent|participants|patients|samples|documents|examples)\b",
        r"\b(prior work|previous studies|researchers|studies|evidence)\b",
    )
    METHOD_PATTERNS = (
        r"\b(we|this study|this project|our|in this work)\s+(used|use|trained|train|evaluated|evaluate|collected|implemented|fine-tuned|split|compare|compared)\b",
        r"\b(we|our)\s+(dataset|corpus|benchmark|training set|test set|baseline|experiment|model|pipeline)\b",
        r"\b(the|this|our)\s+(dataset|corpus|benchmark)\s+(contains?|includes?|consists? of)\b",
        r"\b(hyperparameter|cross-validation|train/test split|validation split|baseline model)\b",
        r"\b(the|our)\s+(experiments?|models?|notebook|optimizer|batch size|architecture|pipeline)\s+(use|uses|used|is|are|evaluate|evaluates|vary|varies)\b",
        r"\b(is|are)\s+(applied|implemented|trained|evaluated|configured)\b",
    )
    OPINION_PATTERNS = (
        r"\b(we believe|i believe|arguably|probably|promising|important|interesting|notable|surprising)\b",
        r"\b(should|could|may|might|appears|seems|interpret|interpreted as)\b",
    )
    DEFINITION_PATTERNS = (
        r"\b(is defined as|are defined as|refers to|means|is a type of|are a type of)\b",
        r"\b(is an?|are)\s+[a-z -]{0,80}\b(concept|method|architecture|technique|field|approach|model|framework)\b",
        r"\b(can be understood as|is known as|are known as)\b",
    )

    def classify_sentence(
        self,
        sentence: str,
        sentence_index: int,
        section: str = "unknown",
    ) -> Claim:
        """Return a structured claim classification for one sentence."""

        citations = extract_citations(sentence, sentence_index)
        normalized = sentence.strip()
        lowered = normalized.lower()

        if self._is_non_claim(normalized):
            claim_type = "non_claim"
            confidence = 0.85
            reason = "Sentence is too short, heading-like, or lacks claim structure."
        else:
            scores = self._score_sentence(lowered, has_citations=bool(citations))
            claim_type, confidence, reason = self._choose_label(scores, has_citations=bool(citations))

        citation_required = _citation_required(claim_type, section, lowered)
        missing_citation = citation_required and not citations
        return Claim(
            sentence=normalized,
            sentence_index=sentence_index,
            claim_type=claim_type,
            citations=citations,
            missing_citation=missing_citation,
            classification_confidence=confidence,
            classification_reason=reason,
            section=section,
            citation_context="same_sentence" if citations else "none",
            citation_required=citation_required,
            flag_severity=_flag_severity(lowered, missing_citation),
        )

    def classify_many(self, sentences: list[str]) -> list[Claim]:
        """Classify a list of sentences."""

        claims: list[Claim] = []
        current_section = "unknown"
        for index, sentence in enumerate(sentences):
            current_section = _infer_section(sentence, current_section)
            claim = self.classify_sentence(sentence, index, section=current_section)
            if (
                claim.missing_citation
                and claims
                and claims[-1].citations
                and _can_inherit_previous_citation(claim.sentence)
            ):
                claim.citations = list(claims[-1].citations)
                claim.missing_citation = False
                claim.citation_context = "previous_sentence"
                claim.flag_severity = "none"
            claims.append(claim)
        return claims

    @staticmethod
    def _matches(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

    def _score_sentence(self, text: str, has_citations: bool) -> dict[str, int]:
        scores = {
            "factual_claim": 0,
            "methodological_statement": 0,
            "opinion_or_interpretation": 0,
            "background_or_definition": 0,
        }
        if has_citations:
            scores["factual_claim"] += 2
        if self._matches(text, self.FACTUAL_PATTERNS):
            scores["factual_claim"] += 2
        if _has_number(text):
            scores["factual_claim"] += 1
        if self._matches(text, self.METHOD_PATTERNS):
            scores["methodological_statement"] += 3
        if self._matches(text, self.OPINION_PATTERNS):
            scores["opinion_or_interpretation"] += 2
        if self._matches(text, self.DEFINITION_PATTERNS):
            scores["background_or_definition"] += 3
        if re.search(r"\b(we|our|this study|this project|in this work)\b", text):
            scores["methodological_statement"] += 1
        return scores

    @staticmethod
    def _choose_label(scores: dict[str, int], has_citations: bool) -> tuple[str, float, str]:
        if scores["methodological_statement"] >= 3:
            return (
                "methodological_statement",
                _confidence(scores["methodological_statement"]),
                "Sentence describes the current study's data, model, experiment, or procedure.",
            )
        if scores["background_or_definition"] >= 3 and scores["factual_claim"] <= 3:
            return (
                "background_or_definition",
                _confidence(scores["background_or_definition"]),
                "Sentence defines or frames a concept rather than asserting a study result.",
            )
        if scores["opinion_or_interpretation"] >= 2 and scores["factual_claim"] < 3:
            return (
                "opinion_or_interpretation",
                _confidence(scores["opinion_or_interpretation"]),
                "Sentence uses subjective, hedged, or interpretive language.",
            )
        if scores["factual_claim"] > 0:
            reason = (
                "Sentence has citation markers or factual/empirical language."
                if has_citations
                else "Sentence asserts a factual or empirical proposition without a citation marker."
            )
            return ("factual_claim", _confidence(scores["factual_claim"]), reason)
        return ("non_claim", 0.7, "No strong claim, method, definition, or opinion cue was detected.")

    @staticmethod
    def _is_non_claim(sentence: str) -> bool:
        if len(sentence.split()) < 4:
            return True
        if re.fullmatch(r"[\d\W]+", sentence):
            return True
        return bool(re.fullmatch(r"[A-Z][A-Za-z ]{0,80}", sentence.strip()))


def _has_number(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:\.\d+)?\b", text))


def _confidence(score: int) -> float:
    return min(0.95, round(0.55 + (score * 0.1), 2))


SECTION_NAMES = (
    r"abstract|introduction|related work|background|methods?|methodology|"
    r"experiments?|results?|discussion|conclusions?|limitations?"
)
NUMBERED_SECTION_RE = re.compile(
    rf"(?:^|\s)\d+(?:\.\d+)*\s+({SECTION_NAMES})\b",
    flags=re.IGNORECASE,
)
PLAIN_SECTION_RE = re.compile(rf"^\s*({SECTION_NAMES})\b(?:\s*[:.]|\s*$)", re.IGNORECASE)


def _infer_section(sentence: str, current: str) -> str:
    prefix = sentence[:240]
    match = NUMBERED_SECTION_RE.search(prefix) or PLAIN_SECTION_RE.search(prefix)
    return match.group(1).lower().rstrip("s") if match else current


def _citation_required(claim_type: str, section: str, text: str) -> bool:
    if claim_type != "factual_claim":
        return False
    if section in {"abstract", "method", "methodology", "experiment", "result"}:
        return False
    if re.search(r"\b(we|our|this study|this project|the notebook)\b", text):
        return False
    return True


def _flag_severity(text: str, missing: bool) -> str:
    if not missing:
        return "none"
    if re.search(r"\b(all|always|never|causes?|eliminates?|proves?|\d+(?:\.\d+)?%)\b", text):
        return "high"
    if re.search(r"\b(studies|research|evidence|reported|demonstrated|outperforms?)\b", text):
        return "high"
    return "medium"


def _can_inherit_previous_citation(sentence: str) -> bool:
    return bool(
        re.match(
            r"\s*(this|these|such|they|it|the (?:study|paper|result|finding|method))\b",
            sentence,
            flags=re.IGNORECASE,
        )
    )
