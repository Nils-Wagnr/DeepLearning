"""Make one minimal, sanitized OpenAI request and print attribution metadata."""

from __future__ import annotations

import json

from claimguard.config import load_environment
from claimguard.models import EvidencePassage
from claimguard.rag.model_verifiers import OpenAIResponsesVerifier


def main() -> None:
    load_environment()
    verifier = OpenAIResponsesVerifier()
    verdict = verifier.verify(
        "The diagnostic evidence states that the connection works.",
        [
            EvidencePassage(
                text="The diagnostic evidence states that the connection works.",
                source="diagnostic",
                score=1.0,
            )
        ],
    )
    safe_result = {
        "success": True,
        "backend": verdict.backend,
        "model": verdict.model,
        "status": verdict.status,
        "latency_ms": verdict.latency_ms,
        "response_id": verdict.metadata.get("response_id"),
        "request_id": verdict.metadata.get("request_id"),
        "configured_project": verdict.metadata.get("configured_project"),
        "response_project": verdict.metadata.get("response_project"),
        "configured_organization": verdict.metadata.get("configured_organization"),
        "response_organization": verdict.metadata.get("response_organization"),
        "usage": verdict.metadata.get("usage", {}),
    }
    print(json.dumps(safe_result, indent=2))


if __name__ == "__main__":
    main()
