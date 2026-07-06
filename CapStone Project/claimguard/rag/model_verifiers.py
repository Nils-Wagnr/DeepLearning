"""Local, frontier, and fine-tuned model backends for claim verification."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from claimguard.models import EvidencePassage

LOGGER = logging.getLogger(__name__)

LABELS = (
    "supported",
    "partially_supported",
    "not_supported",
    "contradicted",
    "insufficient_evidence",
)


class ModelVerifierUnavailable(RuntimeError):
    """Raised when an explicitly selected model backend cannot be used."""


@dataclass(slots=True)
class BackendVerdict:
    status: str
    confidence: float
    rationale: str
    backend: str
    model: str
    latency_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelVerifier(Protocol):
    name: str
    model: str

    def verify(self, claim: str, evidence: list[EvidencePassage]) -> BackendVerdict: ...


def create_model_verifier(name: str) -> ModelVerifier | None:
    """Create a configured verifier; ``heuristic`` uses ClaimVerifier itself."""

    normalized = name.lower().strip()
    if normalized == "heuristic":
        return None
    if normalized == "ollama":
        return OllamaVerifier()
    if normalized == "openai":
        return OpenAIResponsesVerifier()
    if normalized == "lora":
        return LoRAVerifier()
    raise ValueError(f"Unknown verifier {name!r}. Use heuristic, ollama, openai, or lora.")


class OllamaVerifier:
    """Verify claims with a local model served by Ollama."""

    name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    def verify(self, claim: str, evidence: list[EvidencePassage]) -> BackendVerdict:
        started = time.perf_counter()
        schema = _verdict_schema()
        payload = {
            "model": self.model,
            "prompt": _verification_prompt(claim, evidence),
            "format": schema,
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            response = _post_json(f"{self.base_url}/api/generate", payload, timeout=120)
        except Exception as exc:
            raise ModelVerifierUnavailable(
                f"Ollama is unavailable or model {self.model!r} is not installed: {exc}"
            ) from exc
        parsed = _parse_verdict(str(response.get("response", "")))
        return BackendVerdict(
            **parsed,
            backend=self.name,
            model=self.model,
            latency_ms=_elapsed_ms(started),
            metadata={
                "prompt_eval_count": response.get("prompt_eval_count"),
                "eval_count": response.get("eval_count"),
            },
        )


class OpenAIResponsesVerifier:
    """Verify claims through OpenAI's Responses API with structured output."""

    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.project_id = os.getenv("OPENAI_PROJECT_ID") or os.getenv("OPENAI_PROJECT")
        self.organization_id = os.getenv("OPENAI_ORGANIZATION_ID") or os.getenv(
            "OPENAI_ORGANIZATION"
        )

    def verify(self, claim: str, evidence: list[EvidencePassage]) -> BackendVerdict:
        return self._request_verdict(
            instructions=(
                "You are a scientific claim verifier. Judge only from the supplied evidence. "
                "Return the requested JSON and do not use outside knowledge."
            ),
            input_text=_verification_prompt(claim, evidence),
            backend=self.name,
        )

    def verify_without_evidence(self, claim: str) -> BackendVerdict:
        """Diagnostic ablation using parametric knowledge and no retrieved evidence."""

        return self._request_verdict(
            instructions=(
                "You are a scientific claim classifier in a no-retrieval diagnostic. "
                "No source evidence is available. Use only parametric knowledge, acknowledge "
                "uncertainty, and return the requested JSON."
            ),
            input_text=_no_rag_prompt(claim),
            backend="openai_no_rag",
        )

    def _request_verdict(
        self,
        instructions: str,
        input_text: str,
        backend: str,
    ) -> BackendVerdict:
        if not self.api_key:
            raise ModelVerifierUnavailable("OPENAI_API_KEY is not configured")
        started = time.perf_counter()
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "claim_verdict",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": list(LABELS)},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "rationale": {"type": "string"},
                        },
                        "required": ["status", "confidence", "rationale"],
                        "additionalProperties": False,
                    },
                }
            },
            "max_output_tokens": 350,
            "store": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ClaimGuard/0.2",
        }
        if self.project_id:
            headers["OpenAI-Project"] = self.project_id
        if self.organization_id:
            headers["OpenAI-Organization"] = self.organization_id
        request = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:  # nosec - configured API endpoint
                result = json.loads(response.read().decode("utf-8"))
                response_headers = {
                    "request_id": _response_header(response, "x-request-id"),
                    "organization": _response_header(response, "openai-organization"),
                    "project": _response_header(response, "openai-project"),
                    "processing_ms": _response_header(response, "openai-processing-ms"),
                }
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ModelVerifierUnavailable(f"OpenAI API returned HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise ModelVerifierUnavailable(f"OpenAI API unavailable: {exc}") from exc
        parsed = _parse_verdict(_response_output_text(result))
        usage = result.get("usage", {})
        LOGGER.info(
            "OpenAI API request completed: response_id=%s request_id=%s model=%s "
            "input_tokens=%s output_tokens=%s total_tokens=%s project=%s organization=%s",
            result.get("id"),
            response_headers.get("request_id"),
            result.get("model") or self.model,
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("total_tokens"),
            response_headers.get("project") or self.project_id or "key-default",
            response_headers.get("organization") or self.organization_id or "key-default",
        )
        return BackendVerdict(
            **parsed,
            backend=backend,
            model=self.model,
            latency_ms=_elapsed_ms(started),
            metadata={
                "response_id": result.get("id"),
                "request_id": response_headers.get("request_id"),
                "response_organization": response_headers.get("organization"),
                "response_project": response_headers.get("project"),
                "configured_project": self.project_id,
                "configured_organization": self.organization_id,
                "processing_ms": response_headers.get("processing_ms"),
                "usage": usage,
            },
        )


class LoRAVerifier:
    """Run a locally fine-tuned SciFact sequence-classification adapter."""

    name = "lora"

    def __init__(self, model_path: str | None = None) -> None:
        self.model = model_path or os.getenv(
            "CLAIMGUARD_LORA_MODEL", "outputs/models/scifact-lora"
        )
        self._tokenizer = None
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from peft import AutoPeftModelForSequenceClassification
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model)
            id2label = {0: "SUPPORT", 1: "CONTRADICT", 2: "NOT_ENOUGH_INFO"}
            self._model = AutoPeftModelForSequenceClassification.from_pretrained(
                self.model,
                num_labels=3,
                id2label=id2label,
                label2id={label: index for index, label in id2label.items()},
            )
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self._model.to(self._device)
            self._model.eval()
            self._torch = torch
        except Exception as exc:
            raise ModelVerifierUnavailable(
                f"LoRA adapter at {self.model!r} could not be loaded: {exc}"
            ) from exc

    def verify(self, claim: str, evidence: list[EvidencePassage]) -> BackendVerdict:
        self._load()
        started = time.perf_counter()
        evidence_text = " ".join(item.text for item in evidence[:5])
        inputs = self._tokenizer(
            claim,
            evidence_text,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        with self._torch.no_grad():
            logits = self._model(**inputs).logits[0]
            probabilities = self._torch.softmax(logits, dim=-1)
        index = int(probabilities.argmax().item())
        label_map = getattr(self._model.config, "id2label", {})
        raw_label = str(label_map.get(index, label_map.get(str(index), index))).lower()
        status = {
            "support": "supported",
            "supports": "supported",
            "contradict": "contradicted",
            "contradicts": "contradicted",
            "not_enough_info": "insufficient_evidence",
            "insufficient_evidence": "insufficient_evidence",
        }.get(raw_label, "insufficient_evidence")
        return BackendVerdict(
            status=status,
            confidence=round(float(probabilities[index].item()), 3),
            rationale="Prediction from the locally fine-tuned SciFact LoRA classifier.",
            backend=self.name,
            model=self.model,
            latency_ms=_elapsed_ms(started),
            metadata={"device": str(self._device)},
        )


def _verification_prompt(claim: str, evidence: list[EvidencePassage]) -> str:
    snippets = "\n".join(
        f"[{index}] {item.text}" for index, item in enumerate(evidence[:5], start=1)
    )


def _no_rag_prompt(claim: str) -> str:
    return (
        "Classify the claim using exactly one status: supported, partially_supported, "
        "not_supported, contradicted, or insufficient_evidence. In this no-retrieval "
        "ablation, supported means known to be true from parametric knowledge; contradicted "
        "means known to be false; partially_supported means only part is known true; "
        "not_supported means implausible without a known direct opposite; and "
        "insufficient_evidence means you cannot judge reliably. Return JSON with status, "
        "confidence (0..1), and a concise rationale.\n\n"
        f"CLAIM:\n{claim}\n\nRETRIEVED EVIDENCE:\n[none]"
    )
    return (
        "Classify the claim using exactly one status: supported, partially_supported, "
        "not_supported, contradicted, or insufficient_evidence.\n"
        "supported means the evidence directly establishes the full claim; contradicted means "
        "it explicitly establishes the opposite. Use insufficient_evidence when the evidence is "
        "too weak or irrelevant. Return JSON with status, confidence (0..1), and a concise rationale.\n\n"
        f"CLAIM:\n{claim}\n\nEVIDENCE:\n{snippets or '[none]'}"
    )


def _verdict_schema() -> dict[str, Any]:
    """Return the JSON schema enforced by Ollama's structured-output API."""

    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": list(LABELS)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
        },
        "required": ["status", "confidence", "rationale"],
        "additionalProperties": False,
    }


def _parse_verdict(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.S)
    if fenced:
        cleaned = fenced.group(1)
    if not cleaned.startswith("{"):
        object_match = re.search(r"\{.*\}", cleaned, flags=re.S)
        cleaned = object_match.group(0) if object_match else cleaned
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ModelVerifierUnavailable(f"Model returned invalid JSON: {text[:300]}") from exc
    status = str(payload.get("status", "")).lower().strip()
    if status not in LABELS:
        raise ModelVerifierUnavailable(f"Model returned unsupported status {status!r}")
    confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.0))))
    return {
        "status": status,
        "confidence": round(confidence, 3),
        "rationale": str(payload.get("rationale", "")).strip() or "No rationale returned.",
    }


def _response_output_text(payload: dict[str, Any]) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"])
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"])
    raise ModelVerifierUnavailable("Model response contained no output text")


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "ClaimGuard/0.2"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:  # nosec - configured local endpoint
        return json.loads(response.read().decode("utf-8"))


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _response_header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    value = headers.get(name)
    return str(value) if value else None
