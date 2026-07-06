"""Paragraph-level AI-text detection with a Binoculars integration."""

from __future__ import annotations

import math
import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from claimguard.models import AIDetectionResult


class AIDetector:
    """Detect likely AI-generated paragraphs.

    ``binoculars`` uses the ICML 2024 reference implementation when installed.
    ``fast_detect_gpt`` calls the official FastDetect API and returns its
    conditional-probability-curvature score.
    ``heuristic`` is a lightweight baseline and must not be treated as proof of
    authorship.
    """

    def __init__(self, method: str = "heuristic") -> None:
        self.method = method.lower()
        self._engine: Any = None
        if self.method not in {"heuristic", "binoculars", "fast_detect_gpt"}:
            raise ValueError(
                "AI detection method must be heuristic, binoculars, or fast_detect_gpt"
            )

    def detect_document(self, text: str) -> list[AIDetectionResult]:
        raw_paragraphs = [
            re.sub(r"\s+", " ", item).strip()
            for item in re.split(r"\n\s*\n", text)
            if item.strip()
        ]
        paragraphs = [
            passage
            for paragraph in raw_paragraphs
            for passage in _bounded_passages(paragraph)
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
        if self.method == "fast_detect_gpt":
            return self._detect_fast_detect_gpt(text, paragraph_index)
        return self._detect_heuristic(text, paragraph_index)

    def _detect_fast_detect_gpt(self, text: str, paragraph_index: int) -> AIDetectionResult:
        api_key = os.getenv("FASTDETECT_API_KEY")
        if not api_key:
            return AIDetectionResult(
                paragraph_index=paragraph_index,
                text=text,
                label="unavailable",
                score=0.0,
                confidence=0.0,
                method="fast_detect_gpt_api",
                rationale="FASTDETECT_API_KEY is not configured; no detection was performed.",
            )
        endpoint = os.getenv(
            "FASTDETECT_API_ENDPOINT", "https://api.fastdetect.net/api/detect"
        )
        detector = os.getenv(
            "FASTDETECT_MODEL",
            "fast-detect(llama3-8b/llama3-8b-instruct)",
        )
        payload = {"detector": detector, "text": text}
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ClaimGuard/0.2",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:  # nosec - configured official API
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return _unavailable_result(
                text, paragraph_index, "fast_detect_gpt_api", f"HTTP {exc.code}"
            )
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return _unavailable_result(
                text, paragraph_index, "fast_detect_gpt_api", f"API error: {exc}"
            )
        if result.get("code") != 0:
            return _unavailable_result(
                text,
                paragraph_index,
                "fast_detect_gpt_api",
                f"Service returned {result.get('msg', 'an unknown error')}",
            )
        data = result.get("data") or {}
        try:
            probability = float(data["prob"])
        except (KeyError, TypeError, ValueError):
            return _unavailable_result(
                text, paragraph_index, "fast_detect_gpt_api", "Response omitted data.prob"
            )
        probability = max(0.0, min(1.0, probability))
        threshold = float(os.getenv("FASTDETECT_THRESHOLD", "0.5"))
        details = data.get("details") or {}
        label = "likely_ai" if probability >= threshold else "likely_human"
        return AIDetectionResult(
            paragraph_index=paragraph_index,
            text=text,
            label=label,
            score=round(probability, 4),
            confidence=round(abs(probability - threshold) / max(threshold, 1 - threshold), 3),
            method="fast_detect_gpt_api",
            rationale=(
                f"Fast-DetectGPT probability score using {detector}; criterion="
                f"{details.get('crit', 'not returned')}, tokens={details.get('ntoken', 'not returned')}. "
                "This service score is not calibrated as proof of authorship for ClaimGuard reports."
            ),
        )

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


def _bounded_passages(text: str, target_words: int = 120, maximum_words: int = 180) -> list[str]:
    """Split collapsed PDF paragraphs into detector-sized sentence windows."""

    if len(text.split()) <= maximum_words:
        return [text]
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    passages: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and current_words >= target_words and current_words + sentence_words > maximum_words:
            passages.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words
    if current:
        tail = " ".join(current)
        if passages and len(tail.split()) < 40:
            passages[-1] = f"{passages[-1]} {tail}"
        else:
            passages.append(tail)
    return passages or [text]


def _unavailable_result(
    text: str,
    paragraph_index: int,
    method: str,
    reason: str,
) -> AIDetectionResult:
    return AIDetectionResult(
        paragraph_index=paragraph_index,
        text=text,
        label="unavailable",
        score=0.0,
        confidence=0.0,
        method=method,
        rationale=f"Fast-DetectGPT detection was unavailable: {reason}.",
    )
