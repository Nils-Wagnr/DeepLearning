"""Fuzzy matching helpers with a stdlib fallback."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
}


def normalize_text(text: str | None) -> str:
    """Normalize text for fuzzy matching."""

    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("&", " and ")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.lower()
    text = re.sub(r"https?://(?:dx\.)?doi\.org/", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\bdoi\s*:\s*", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fuzzy_score(left: str | None, right: str | None) -> float:
    """Return a robust title/reference similarity score in [0, 1]."""

    normalized_left = normalize_text(left)
    normalized_right = normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0

    try:
        from rapidfuzz import fuzz  # type: ignore

        return round(
            max(
                fuzz.ratio(normalized_left, normalized_right),
                fuzz.token_sort_ratio(normalized_left, normalized_right),
                fuzz.token_set_ratio(normalized_left, normalized_right),
                fuzz.partial_ratio(normalized_left, normalized_right) * 0.92,
            )
            / 100.0,
            3,
        )
    except Exception:
        return round(
            max(
                SequenceMatcher(None, normalized_left, normalized_right).ratio(),
                _token_sort_ratio(normalized_left, normalized_right),
                _token_set_ratio(normalized_left, normalized_right),
                _jaccard_ratio(normalized_left, normalized_right),
            ),
            3,
        )


def meaningful_tokens(text: str | None) -> list[str]:
    """Return normalized, lightly stemmed tokens useful for matching."""

    normalized = normalize_text(text)
    return [
        _stem(token)
        for token in normalized.split()
        if token not in STOPWORDS and len(token) > 1
    ]


def _token_sort_ratio(left: str, right: str) -> float:
    left_sorted = " ".join(sorted(meaningful_tokens(left)))
    right_sorted = " ".join(sorted(meaningful_tokens(right)))
    if not left_sorted or not right_sorted:
        return 0.0
    return SequenceMatcher(None, left_sorted, right_sorted).ratio()


def _token_set_ratio(left: str, right: str) -> float:
    left_tokens = set(meaningful_tokens(left))
    right_tokens = set(meaningful_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    left_only = left_tokens - intersection
    right_only = right_tokens - intersection
    combined_left = " ".join(sorted(intersection | left_only))
    combined_right = " ".join(sorted(intersection | right_only))
    intersection_text = " ".join(sorted(intersection))
    if not intersection_text:
        return 0.0
    return max(
        SequenceMatcher(None, combined_left, combined_right).ratio(),
        SequenceMatcher(None, intersection_text, combined_left).ratio(),
        SequenceMatcher(None, intersection_text, combined_right).ratio(),
    )


def _jaccard_ratio(left: str, right: str) -> float:
    left_tokens = set(meaningful_tokens(left))
    right_tokens = set(meaningful_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    containment = overlap / max(1, min(len(left_tokens), len(right_tokens)))
    return max(overlap / union, containment * 0.9)


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
