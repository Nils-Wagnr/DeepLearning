"""Paragraph-level AI-text detection with a Binoculars integration."""

from __future__ import annotations

import math
import os
import re
from typing import Any

from claimguard.models import AIDetectionResult


class AIDetector:
    """Detect likely AI-generated paragraphs.

    ``binoculars`` uses the ICML 2024 reference implementation when installed.
    ``heuristic`` is a lightweight baseline and must not be treated as proof of
    authorship.
    """

    def __init__(self, method: str = "heuristic") -> None:
        self.method = method.lower()
        self._engine: Any = None
        if self.method not in {"heuristic", "binoculars"}:
            raise ValueError("AI detection method must be heuristic or binoculars")

    def detect_document(self, text: str) -> list[AIDetectionResult]:
        paragraphs = [
            re.sub(r"\s+", " ", item).strip()
            for item in re.split(r"\n\s*\n", text)
            if item.strip()
        ]
        return [self.detect(paragraph, index) for index, paragraph in enumerate(paragraphs)]

    def detect(self, text: str, paragraph_index: int = 0) -> AIDetectionResult:
        if len(text.split()) < 40:
            return AIDetectionResult(
                paragraph_index=paragraph_index,
                text=text,
                label="insufficient_text",
                score=0.0,
                confidence=0.0,
                method=self.method,
                rationale="Fewer than 40 words; AI-text detection would be unreliable.",
            )
        if self.method == "binoculars":
            return self._detect_binoculars(text, paragraph_index)
        return self._detect_heuristic(text, paragraph_index)

    def _detect_binoculars(self, text: str, paragraph_index: int) -> AIDetectionResult:
        if self._engine is None:
            try:
                from binoculars import Binoculars

                kwargs: dict[str, Any] = {}
                if os.getenv("BINOCULARS_OBSERVER_MODEL"):
                    kwargs["observer_name_or_path"] = os.environ["BINOCULARS_OBSERVER_MODEL"]
                if os.getenv("BINOCULARS_PERFORMER_MODEL"):
                    kwargs["performer_name_or_path"] = os.environ["BINOCULARS_PERFORMER_MODEL"]
                self._engine = Binoculars(**kwargs)
            except Exception as exc:
                return AIDetectionResult(
                    paragraph_index=paragraph_index,
                    text=text,
                    label="unavailable",
                    score=0.0,
                    confidence=0.0,
                    method="binoculars",
                    rationale=f"Binoculars could not be loaded: {exc}",
                )
        try:
            raw_prediction = str(self._engine.predict(text))
            raw_score = float(self._engine.compute_score(text))
        except Exception as exc:
            return AIDetectionResult(
                paragraph_index=paragraph_index,
                text=text,
                label="unavailable",
                score=0.0,
                confidence=0.0,
                method="binoculars",
                rationale=f"Binoculars inference failed: {exc}",
            )
        is_ai = "ai" in raw_prediction.lower() and "human" not in raw_prediction.lower()
        return AIDetectionResult(
            paragraph_index=paragraph_index,
            text=text,
            label="likely_ai" if is_ai else "likely_human",
            score=round(raw_score, 4),
            confidence=0.8,
            method="binoculars",
            rationale=(
                f"Reference Binoculars prediction: {raw_prediction}. The score is model-pair "
                "dependent and must be interpreted with the calibrated threshold."
            ),
        )

    @staticmethod
    def _detect_heuristic(text: str, paragraph_index: int) -> AIDetectionResult:
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
        lengths = [len(sentence.split()) for sentence in sentences] or [len(text.split())]
        mean = sum(lengths) / len(lengths)
        variance = sum((value - mean) ** 2 for value in lengths) / len(lengths)
        variation = math.sqrt(variance) / max(1.0, mean)
        transitions = len(
            re.findall(
                r"\b(furthermore|moreover|additionally|overall|in conclusion|notably)\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        repeated_openers = _repeated_sentence_opener_ratio(sentences)
        score = min(
            1.0,
            max(0.0, (0.42 - variation) * 0.9 + transitions * 0.06 + repeated_openers * 0.35),
        )
        label = "likely_ai" if score >= 0.62 else "uncertain" if score >= 0.42 else "likely_human"
        return AIDetectionResult(
            paragraph_index=paragraph_index,
            text=text,
            label=label,
            score=round(score, 3),
            confidence=round(abs(score - 0.5) * 1.4, 3),
            method="heuristic_baseline",
            rationale=(
                "Baseline score from sentence-length regularity, repeated sentence openings, and "
                "formulaic transitions; it is not evidence of authorship."
            ),
        )


def _repeated_sentence_opener_ratio(sentences: list[str]) -> float:
    openers = [" ".join(re.findall(r"[a-z]+", item.lower())[:2]) for item in sentences]
    openers = [item for item in openers if item]
    if len(openers) < 2:
        return 0.0
    return 1.0 - (len(set(openers)) / len(openers))
