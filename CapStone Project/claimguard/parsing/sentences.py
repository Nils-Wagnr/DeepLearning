"""Sentence segmentation helpers."""

from __future__ import annotations

import re

ABBREVIATIONS = (
    "e.g.",
    "i.e.",
    "et al.",
    "Dr.",
    "Prof.",
    "Fig.",
    "Eq.",
    "vs.",
)


def split_sentences(text: str) -> list[str]:
    """Split text into sentences with a lightweight academic-text heuristic."""

    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    placeholders: dict[str, str] = {}
    protected = cleaned
    for index, abbreviation in enumerate(ABBREVIATIONS):
        token = f"__ABBR_{index}__"
        placeholders[token] = abbreviation
        protected = protected.replace(abbreviation, token)

    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\[\(])", protected)
    sentences: list[str] = []
    for part in parts:
        restored = part
        for token, abbreviation in placeholders.items():
            restored = restored.replace(token, abbreviation)
        restored = restored.strip()
        if restored:
            sentences.append(restored)
    return sentences

