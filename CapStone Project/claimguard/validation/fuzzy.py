"""Fuzzy matching helpers with a stdlib fallback."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


def normalize_text(text: str | None) -> str:
    """Normalize text for fuzzy matching."""

    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"doi:\s*", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fuzzy_score(left: str | None, right: str | None) -> float:
    """Return a similarity score in [0, 1]."""

    normalized_left = normalize_text(left)
    normalized_right = normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0

    try:
        from rapidfuzz import fuzz  # type: ignore

        return fuzz.token_set_ratio(normalized_left, normalized_right) / 100.0
    except Exception:
        return SequenceMatcher(None, normalized_left, normalized_right).ratio()

