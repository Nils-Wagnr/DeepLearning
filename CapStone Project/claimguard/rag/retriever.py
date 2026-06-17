"""Evidence retrieval with optional sentence-transformers and FAISS."""

from __future__ import annotations

import logging
import math
import os
import re
from typing import Iterable

from claimguard.models import EvidencePassage, Reference

LOGGER = logging.getLogger(__name__)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
}


class EvidenceRetriever:
    """Retrieve evidence passages for a claim."""

    def __init__(self, passages: list[EvidencePassage]) -> None:
        self.passages = passages
        self._model = None
        self._faiss_index = None
        self._embeddings = None
        self._maybe_load_vector_backend()

    def retrieve(
        self,
        query: str,
        reference_indices: set[str] | None = None,
        top_k: int = 3,
    ) -> list[EvidencePassage]:
        """Return the top evidence passages for a query."""

        candidates = [
            passage
            for passage in self.passages
            if reference_indices is None
            or passage.reference_index is None
            or passage.reference_index in reference_indices
        ]
        if not candidates:
            return []

        scored = [
            EvidencePassage(
                text=passage.text,
                source=passage.source,
                score=_token_similarity(query, passage.text),
                reference_index=passage.reference_index,
            )
            for passage in candidates
        ]
        scored.sort(key=lambda passage: passage.score, reverse=True)
        return scored[:top_k]

    def _maybe_load_vector_backend(self) -> None:
        mode = os.getenv("CLAIMGUARD_USE_EMBEDDINGS", "auto").lower()
        if mode in {"0", "false", "no"} or not self.passages:
            return
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore
            from sentence_transformers import SentenceTransformer  # type: ignore

            model_name = os.getenv(
                "CLAIMGUARD_EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            )
            self._model = SentenceTransformer(model_name, local_files_only=True)
            vectors = self._model.encode(
                [passage.text for passage in self.passages],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            self._embeddings = np.asarray(vectors, dtype="float32")
            self._faiss_index = faiss.IndexFlatIP(self._embeddings.shape[1])
            self._faiss_index.add(self._embeddings)
            LOGGER.info("Loaded sentence-transformers + FAISS retrieval backend.")
        except Exception as exc:  # pragma: no cover - optional backend
            self._model = None
            self._faiss_index = None
            self._embeddings = None
            LOGGER.info("Using offline token retriever: %s", exc)


def build_evidence_passages(evidence_text: str, references: list[Reference]) -> list[EvidencePassage]:
    """Build evidence passages from a sample evidence section plus reference text."""

    passages: list[EvidencePassage] = []
    reference_lookup = {reference.index: reference for reference in references if reference.index}

    for paragraph in _paragraphs(evidence_text):
        source = "sample_evidence"
        reference_index = None
        label_match = re.match(r"^\[(?P<label>[^\]]+)\]\s*(?P<body>.*)", paragraph)
        body = paragraph
        if label_match:
            label = label_match.group("label").strip()
            source = label
            body = label_match.group("body").strip()
            reference_index = _match_label_to_reference(label, references)
        passages.append(
            EvidencePassage(
                text=body or paragraph,
                source=source,
                reference_index=reference_index,
            )
        )

    for reference in references:
        source = f"reference:{reference.index}" if reference.index else "reference"
        body_parts = [
            part
            for part in (reference.title, f"Year: {reference.year}" if reference.year else None, reference.raw_text)
            if part
        ]
        passages.append(
            EvidencePassage(
                text=". ".join(body_parts),
                source=source,
                reference_index=reference.index,
            )
        )

    return passages


def tokenize(text: str) -> set[str]:
    """Tokenize and lightly stem text for matching."""

    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {_stem(token) for token in tokens if token not in STOPWORDS and len(token) > 2}


def _token_similarity(left: str, right: str) -> float:
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    cosine = overlap / math.sqrt(len(left_tokens) * len(right_tokens))
    containment = overlap / max(1, len(left_tokens))
    return round((cosine * 0.55) + (containment * 0.45), 3)


def _paragraphs(text: str) -> Iterable[str]:
    for part in re.split(r"\n\s*\n|(?<=\.)\s*\n", text.strip()):
        cleaned = re.sub(r"\s+", " ", part).strip()
        if cleaned:
            yield cleaned


def _match_label_to_reference(label: str, references: list[Reference]) -> str | None:
    numeric = re.fullmatch(r"\d+", label)
    if numeric and label in {reference.index for reference in references}:
        return label

    label_lower = label.lower()
    year_match = re.search(r"\b((?:19|20)\d{2})\b", label)
    label_year = int(year_match.group(1)) if year_match else None
    for reference in references:
        if label_year and reference.year and label_year != reference.year:
            continue
        author_blob = " ".join(reference.authors).lower()
        if author_blob and any(part in author_blob for part in re.findall(r"[a-z]+", label_lower)):
            return reference.index
    return None


def _stem(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("ing") and len(token) > 5:
        return token[:-3]
    if token.endswith("ed") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token

