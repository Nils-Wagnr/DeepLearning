from pathlib import Path
from tempfile import TemporaryDirectory

from claimguard.pipeline import analyze_document, write_claims_csv


def test_smoke_sample_bad_paper_runs() -> None:
    path = Path("data/sample_input/sample_bad_paper.txt")

    report = analyze_document(path)

    assert report["summary"]["factual_claims"] >= 2
    assert report["summary"]["references"] == 2
    statuses = {
        item["status"]
        for item in report["claim_verification"]
        if item["claim_index"] in {0, 1}
    }
    assert "contradicted" in statuses
    assert report["module_1"]["summary"]["factual_claims_missing_citations"] >= 1


def test_module_1_csv_export_writes_claim_rows() -> None:
    report = analyze_document(Path("data/sample_input/sample_bad_paper.txt"))

    with TemporaryDirectory() as directory:
        output = Path(directory) / "claims.csv"
        write_claims_csv(report, output)
        csv_text = output.read_text(encoding="utf-8")

    assert "sentence_index,claim_type,missing_citation" in csv_text
    assert "factual_claim" in csv_text
    assert "Large language models" in csv_text
