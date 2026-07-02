"""Evidence retrieval with chunking, optional embeddings, and lexical fallback."""

from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter
from typing import Iterable

from claimguard.models import EvidencePassage, Reference

LOGGER = logging.getLogger(__name__)
_VECTOR_FALLBACK_LOGGED = False
_EMBEDDING_MODEL_CACHE: dict[tuple[str, bool], object] = {}
_FAISS_FALLBACK_LOGGED = False

DEFAULT_TOP_K = 5
DEFAULT_CHUNK_WORDS = 95
DEFAULT_OVERLAP_WORDS = 20

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
    """Retrieve top-k evidence chunks for a claim."""

    def __init__(self, passages: list[EvidencePassage]) -> None:
        self.passages = passages
        self.backend = "lexical"
        self._model = None
        self._faiss_index = None
        self._embeddings = None
        self._numpy = None
        self._maybe_load_vector_backend()

    def retrieve(
        self,
        query: str,
        reference_indices: set[str] | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[EvidencePassage]:
        """Return top-k evidence chunks for a query."""

        candidate_indices = self._candidate_indices(reference_indices)
        if not candidate_indices:
            return []

        if self.backend == "faiss":
            vector_results = self._retrieve_with_faiss(query, candidate_indices, top_k)
            if vector_results:
                return vector_results

        if self.backend == "embedding":
            vector_results = self._retrieve_with_embeddings(query, candidate_indices, top_k)
            if vector_results:
                return vector_results

        return self._retrieve_lexical(query, candidate_indices, top_k)

    def _candidate_indices(self, reference_indices: set[str] | None) -> list[int]:
        if not reference_indices:
            return list(range(len(self.passages)))

        indices: list[int] = []
        for index, passage in enumerate(self.passages):
            if passage.reference_index is None or passage.reference_index in reference_indices:
                indices.append(index)
        return indices

    def _retrieve_with_faiss(
        self, query: str, candidate_indices: list[int], top_k: int
    ) -> list[EvidencePassage]:
        if self._model is None or self._faiss_index is None:
            return []
        try:
            query_vector = self._model.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            query_vector = self._numpy.asarray(query_vector, dtype="float32")
            search_k = min(len(self.passages), max(top_k * 5, top_k))
            scores, indices = self._faiss_index.search(query_vector, search_k)
        except Exception as exc:  # pragma: no cover - optional backend
            LOGGER.warning("FAISS retrieval failed; falling back to lexical retrieval: %s", exc)
            return []

        allowed = set(candidate_indices)
        results: list[EvidencePassage] = []
        for raw_score, raw_index in zip(scores[0], indices[0]):
            index = int(raw_index)
            if index < 0 or index not in allowed:
                continue
            results.append(self._scored_copy(index, float(raw_score), "faiss"))
            if len(results) >= top_k:
                break
        return results

    def _retrieve_with_embeddings(
        self, query: str, candidate_indices: list[int], top_k: int
    ) -> list[EvidencePassage]:
        if self._model is None or self._embeddings is None or self._numpy is None:
            return []
        try:
            query_vector = self._model.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            query_vector = self._numpy.asarray(query_vector, dtype="float32")
            candidate_vectors = self._embeddings[candidate_indices]
            scores = candidate_vectors @ query_vector[0]
        except Exception as exc:  # pragma: no cover - optional backend
            LOGGER.warning("Embedding retrieval failed; falling back to lexical retrieval: %s", exc)
            return []

        ranked = sorted(
            zip(candidate_indices, scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [
            self._scored_copy(index, float(score), "embedding")
            for index, score in ranked[:top_k]
        ]

    def _retrieve_lexical(
        self, query: str, candidate_indices: list[int], top_k: int
    ) -> list[EvidencePassage]:
        scored = [
            self._scored_copy(
                index,
                _lexical_similarity(query, self.passages[index].text),
                "lexical",
            )
            for index in candidate_indices
        ]
        scored.sort(key=lambda passage: passage.score, reverse=True)
        return scored[:top_k]

    def _scored_copy(self, index: int, raw_score: float, method: str) -> EvidencePassage:
        passage = self.passages[index]
        score = _normalize_score(raw_score, method)
        return EvidencePassage(
            text=passage.text,
            source=passage.source,
            score=score,
            reference_index=passage.reference_index,
            chunk_id=passage.chunk_id,
            retrieval_method=method,
            metadata=dict(passage.metadata),
        )

    def _maybe_load_vector_backend(self) -> None:
        mode = os.getenv("CLAIMGUARD_USE_EMBEDDINGS", "auto").lower()
        if mode in {"0", "false", "no"} or not self.passages:
            return

        try:
            import numpy as np  # type: ignore
            from sentence_transformers import SentenceTransformer  # type: ignore

            model_name = os.getenv(
                "CLAIMGUARD_EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            )
            local_only = mode == "auto" or os.getenv(
                "CLAIMGUARD_EMBEDDING_LOCAL_ONLY", "true"
            ).lower() in {"1", "true", "yes"}
            cache_key = (model_name, local_only)
            self._model = _EMBEDDING_MODEL_CACHE.get(cache_key)
            if self._model is None:
                self._model = SentenceTransformer(model_name, local_files_only=local_only)
                _EMBEDDING_MODEL_CACHE[cache_key] = self._model
            vectors = self._model.encode(
                [passage.text for passage in self.passages],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            self._numpy = np
            self._embeddings = np.asarray(vectors, dtype="float32")
            self.backend = "embedding"
        except Exception as exc:  # pragma: no cover - optional backend
            global _VECTOR_FALLBACK_LOGGED
            self._model = None
            self._embeddings = None
            self._numpy = None
            if not _VECTOR_FALLBACK_LOGGED:
                LOGGER.info("Using lexical retriever; embedding backend unavailable: %s", exc)
                _VECTOR_FALLBACK_LOGGED = True
            else:
                LOGGER.debug("Embedding backend remains unavailable: %s", exc)
            return

        try:
            import faiss  # type: ignore

            self._faiss_index = faiss.IndexFlatIP(self._embeddings.shape[1])
            self._faiss_index.add(self._embeddings)
            self.backend = "faiss"
            LOGGER.info("Loaded sentence-transformers + FAISS retrieval backend.")
        except Exception as exc:  # pragma: no cover - optional backend
            global _FAISS_FALLBACK_LOGGED
            self._faiss_index = None
            if not _FAISS_FALLBACK_LOGGED:
                LOGGER.info("Using embedding cosine fallback; FAISS unavailable: %s", exc)
                _FAISS_FALLBACK_LOGGED = True
            else:
                LOGGER.debug("FAISS remains unavailable: %s", exc)


def build_evidence_passages(evidence_text: str, references: list[Reference]) -> list[EvidencePassage]:
    """Build chunked evidence passages from sample evidence and references."""

    passages: list[EvidencePassage] = []
    seen: set[str] = set()

    for paragraph_index, paragraph in enumerate(_paragraphs(evidence_text)):
        source = "sample_evidence"
        reference_index = None
        body = paragraph
        label_match = re.match(r"^\[(?P<label>[^\]]+)\]\s*(?P<body>.*)", paragraph)
        if label_match:
            label = label_match.group("label").strip()
            source = label
            body = label_match.group("body").strip()
            reference_index = _match_label_to_reference(label, references)

        passages.extend(
            _chunk_to_passages(
                body or paragraph,
                source=source,
                reference_index=reference_index,
                base_id=f"evidence:{paragraph_index}",
                seen=seen,
            )
        )

    for reference_position, reference in enumerate(references):
        source = f"reference:{reference.index}" if reference.index else "reference"
        body_parts = [
            part
            for part in (
                reference.title,
                "Authors: " + ", ".join(reference.authors) if reference.authors else None,
                f"Year: {reference.year}" if reference.year else None,
                f"DOI: {reference.doi}" if reference.doi else None,
                reference.raw_text,
            )
            if part
        ]
        passages.extend(
            _chunk_to_passages(
                ". ".join(body_parts),
                source=source,
                reference_index=reference.index,
                base_id=f"reference:{reference.index or reference_position}",
                seen=seen,
            )
        )

    return passages


def tokenize(text: str) -> set[str]:
    """Tokenize and lightly stem text for matching."""

    return set(_token_list(text))


def _chunk_to_passages(
    text: str,
    source: str,
    reference_index: str | None,
    base_id: str,
    seen: set[str],
) -> list[EvidencePassage]:
    chunks = chunk_text(text)
    passages: list[EvidencePassage] = []
    for chunk_index, chunk in enumerate(chunks):
        key = re.sub(r"\W+", " ", chunk.lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        passages.append(
            EvidencePassage(
                text=chunk,
                source=source,
                reference_index=reference_index,
                chunk_id=f"{base_id}:chunk:{chunk_index}",
                retrieval_method="unscored",
                metadata={"chunk_index": chunk_index, "word_count": len(chunk.split())},
            )
        )
    return passages


def chunk_text(
    text: str,
    max_words: int = DEFAULT_CHUNK_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> list[str]:
    """Split text into sentence-aware overlapping chunks."""

    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    sentences = _split_sentences(cleaned)
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        words = sentence.split()
        if current and current_words + len(words) > max_words:
            chunks.append(" ".join(current).strip())
            overlap = _tail_words(" ".join(current), overlap_words)
            current = [overlap] if overlap else []
            current_words = len(overlap.split()) if overlap else 0
        current.append(sentence)
        current_words += len(words)

    if current:
        chunks.append(" ".join(current).strip())

    if len(chunks) == 1 and len(chunks[0].split()) > max_words:
        return _fixed_word_chunks(chunks[0], max_words, overlap_words)
    return chunks


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\[])|(?<=;)\s+(?=[A-Z0-9])", text)
    return [part.strip() for part in parts if part.strip()]


def _fixed_word_chunks(text: str, max_words: int, overlap_words: int) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks: list[str] = []
    start = 0
    stride = max(1, max_words - overlap_words)
    while start < len(words):
        chunk = " ".join(words[start : start + max_words]).strip()
        if chunk:
            chunks.append(chunk)
        start += stride
    return chunks


def _tail_words(text: str, count: int) -> str:
    if count <= 0:
        return ""
    words = text.split()
    return " ".join(words[-count:])


def _lexical_similarity(left: str, right: str) -> float:
    left_tokens = _token_list(left)
    right_tokens = _token_list(right)
    if not left_tokens or not right_tokens:
        return 0.0

    left_set = set(left_tokens)
    right_set = set(right_tokens)
    overlap = len(left_set & right_set)
    cosine = _counter_cosine(Counter(left_tokens), Counter(right_tokens))
    containment = overlap / max(1, len(left_set))
    jaccard = overlap / max(1, len(left_set | right_set))
    bigram_score = _bigram_overlap(left_tokens, right_tokens)
    phrase_bonus = 0.06 if _has_key_phrase_overlap(left, right) else 0.0
    score = (cosine * 0.40) + (containment * 0.32) + (jaccard * 0.12) + (bigram_score * 0.16)
    return round(min(1.0, score + phrase_bonus), 3)


def _counter_cosine(left: Counter[str], right: Counter[str]) -> float:
    shared = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _bigram_overlap(left_tokens: list[str], right_tokens: list[str]) -> float:
    left_bigrams = set(zip(left_tokens, left_tokens[1:]))
    right_bigrams = set(zip(right_tokens, right_tokens[1:]))
    if not left_bigrams or not right_bigrams:
        return 0.0
    return len(left_bigrams & right_bigrams) / max(1, len(left_bigrams))


def _has_key_phrase_overlap(left: str, right: str) -> bool:
    left_phrases = _nounish_phrases(left)
    right_normalized = " ".join(_token_list(right))
    return any(phrase in right_normalized for phrase in left_phrases)


def _nounish_phrases(text: str) -> list[str]:
    tokens = _token_list(text)
    phrases: list[str] = []
    for size in (4, 3):
        for index in range(0, max(0, len(tokens) - size + 1)):
            phrase = " ".join(tokens[index : index + size])
            if phrase:
                phrases.append(phrase)
    return phrases


def _token_list(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(token) for token in tokens if token not in STOPWORDS and len(token) > 2]


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


def _normalize_score(raw_score: float, method: str) -> float:
    if method in {"faiss", "embedding"}:
        return round(max(0.0, min(1.0, raw_score)), 3)
    return round(max(0.0, min(1.0, raw_score)), 3)


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
