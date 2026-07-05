from claimguard.comparison import compare_reports


def _report(statuses, *, error_at=None):
    claims = [
        {"sentence_index": index, "sentence": f"Claim {index}"}
        for index in range(len(statuses))
    ]
    verifications = []
    for index, status in enumerate(statuses):
        metadata = {"backend_error": "offline"} if index == error_at else {}
        verifications.append(
            {
                "claim_index": index,
                "status": status,
                "confidence": 0.8,
                "rationale": "test",
                "model": "demo",
                "latency_ms": 10,
                "metadata": metadata,
            }
        )
    return {"claims": claims, "claim_verification": verifications}


def test_compare_reports_finds_agreements_and_disagreements() -> None:
    result = compare_reports(
        {
            "heuristic": _report(["supported", "contradicted"]),
            "ollama": _report(["supported", "not_supported"]),
        }
    )

    assert result["summary"]["agreements"] == 1
    assert result["summary"]["disagreements"] == 1
    assert result["rows"][1]["agreement"] == "disagreement"


def test_backend_errors_are_not_counted_as_model_verdicts() -> None:
    result = compare_reports(
        {
            "heuristic": _report(["supported"]),
            "ollama": _report(["insufficient_evidence"], error_at=0),
        }
    )

    assert result["summary"]["incomplete"] == 1
    assert result["summary"]["backend_errors"] == 1
    assert result["backend_summary"]["ollama"]["errors"] == 1
