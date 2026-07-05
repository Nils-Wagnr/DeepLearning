from claimguard.interpretation import (
    claim_recommendation,
    confidence_label,
    interpret_report,
    interpret_verification,
)


def test_confidence_is_described_as_signal() -> None:
    assert confidence_label(0.85) == "starkes Modellsignal"
    assert confidence_label(0.6) == "mittleres Modellsignal"
    assert confidence_label(0.1) == "sehr schwaches Modellsignal"


def test_contradiction_creates_elevated_review_priority() -> None:
    report = {
        "claims": [{"sentence_index": 0, "missing_citation": False}],
        "claim_verification": [{"claim_index": 0, "status": "contradicted"}],
    }

    result = interpret_report(report)

    assert result["level"] == "Erhöhter Prüfbedarf"
    assert result["counts"]["conflicts"] == 1
    assert "Originalquelle" in result["summary"]


def test_missing_citation_takes_priority_in_claim_recommendation() -> None:
    claim = {"missing_citation": True, "claim_type": "factual_claim"}
    verification = {"status": "supported", "confidence": 0.9}

    recommendation = claim_recommendation(claim, verification)

    assert "Zitation ergänzen" in recommendation


def test_verification_interpretation_is_cautious() -> None:
    result = interpret_verification({"status": "supported", "confidence": 0.9})

    assert result["label"] == "Gestützt"
    assert "kein Wahrheitsbeweis" in result["recommendation"]
