import csv
import json

import claimguard.rag.model_verifiers as model_verifiers
from claimguard.ai_detection import AIDetector
from claimguard.claims.classifier import ClaimClassifier
from claimguard.evaluation.tool_comparison import compare_tools
from claimguard.evaluation.reference_evaluator import evaluate_reference_parsing
from claimguard.pipeline import analyze_document, write_markdown_report
from claimguard.rag.model_verifiers import _parse_verdict
from claimguard.models import EvidencePassage
from claimguard.validation.references import ReferenceParser


def test_section_aware_flags_and_previous_sentence_citation() -> None:
    claims = ClaimClassifier().classify_many(
        [
            "Prior studies reported improved accuracy [1].",
            "This finding improved accuracy on a second benchmark.",
            "2 Methods.",
            "The experiments use 100 training examples.",
        ]
    )
    assert claims[1].citation_context == "previous_sentence"
    assert claims[1].missing_citation is False
    assert claims[3].section == "method"
    assert claims[3].missing_citation is False


def test_reference_parser_extracts_venue() -> None:
    reference = ReferenceParser().parse(
        "[1] Smith, J. (2024). A robust citation checker. Journal of Testing. doi:10.1000/test"
    )[0]
    assert reference.venue == "Journal of Testing"


def test_reference_parsing_benchmark_covers_all_fields() -> None:
    report = evaluate_reference_parsing("data/benchmark/reference_parsing_benchmark.csv")
    assert report["total"] == 5
    assert set(report["field_accuracy"]) == {"index", "title", "authors", "year", "doi", "venue"}


def test_model_verdict_parser_enforces_shared_schema() -> None:
    verdict = _parse_verdict(
        '{"status":"supported","confidence":0.91,"rationale":"Direct evidence."}'
    )
    assert verdict["status"] == "supported"
    assert verdict["confidence"] == 0.91


def test_ollama_backend_uses_shared_verdict(monkeypatch) -> None:
    captured = {}

    def fake_post_json(url, payload, timeout):
        captured.update({"url": url, "payload": payload, "timeout": timeout})
        return {
            "response": '{"status":"supported","confidence":0.8,"rationale":"Matched."}',
            "eval_count": 12,
        }

    monkeypatch.setattr(
        model_verifiers,
        "_post_json",
        fake_post_json,
    )
    verdict = model_verifiers.OllamaVerifier(model="demo").verify(
        "Claim", [EvidencePassage(text="Evidence", source="test")]
    )
    assert verdict.backend == "ollama"
    assert verdict.status == "supported"
    assert captured["payload"]["format"]["properties"]["status"]["enum"] == list(
        model_verifiers.LABELS
    )
    assert captured["payload"]["format"]["required"] == ["status", "confidence", "rationale"]


def test_openai_backend_parses_responses_api_output(monkeypatch) -> None:
    payload = {
        "id": "resp_test",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"status":"contradicted","confidence":0.9,"rationale":"Opposite."}',
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 20, "output_tokens": 10},
    }

    class FakeResponse:
        headers = {
            "x-request-id": "req_test",
            "openai-organization": "org_test",
            "openai-project": "proj_test",
        }

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(model_verifiers, "urlopen", lambda *args, **kwargs: FakeResponse())
    verdict = model_verifiers.OpenAIResponsesVerifier(model="demo", api_key="test").verify(
        "Claim", [EvidencePassage(text="Evidence", source="test")]
    )
    assert verdict.status == "contradicted"
    assert verdict.metadata["usage"]["input_tokens"] == 20
    assert verdict.metadata["request_id"] == "req_test"
    assert verdict.metadata["response_project"] == "proj_test"


def test_ai_detection_short_text_is_not_overclaimed() -> None:
    result = AIDetector("heuristic").detect("This paragraph is too short.")
    assert result.label == "insufficient_text"
    assert result.confidence == 0.0


def test_external_tool_comparison_uses_shared_case_ids(tmp_path) -> None:
    benchmark = tmp_path / "benchmark.csv"
    predictions = tmp_path / "tool.csv"
    with benchmark.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "expected_label"])
        writer.writeheader()
        writer.writerow({"case_id": "A", "expected_label": "supported"})
    with predictions.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "predicted"])
        writer.writeheader()
        writer.writerow({"case_id": "A", "predicted": "supported"})
    report = compare_tools(benchmark, {"demo": predictions})
    assert report["tools"]["demo"]["accuracy"] == 1.0


def test_markdown_report_is_human_readable(tmp_path) -> None:
    report = analyze_document("data/sample_input/sample_bad_paper.txt")
    target = tmp_path / "report.md"
    write_markdown_report(report, target)
    text = target.read_text(encoding="utf-8")
    assert "# ClaimGuard integrity report" in text
    assert "Interpretation warning" in text
    assert "Backend: `heuristic`" in text
    assert "Confidence:" in text
    assert json.loads(json.dumps(report))["module_3"]["name"] == "rag_claim_source_verification"
