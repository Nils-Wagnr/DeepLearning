from claimguard.evaluation import evaluate_benchmark


def test_evaluation_reports_precision_recall_f1_and_examples() -> None:
    report = evaluate_benchmark("data/benchmark/claimguard_benchmark.csv")

    assert report["total"] == 15
    assert "metrics" in report
    assert report["metrics"]["macro_f1"] >= 0.0
    assert set(report["metrics"]["labels_evaluated"]) == {
        "supported",
        "partially_supported",
        "not_supported",
        "contradicted",
        "insufficient_evidence",
    }
    assert "precision" in report["metrics"]["per_label"]["supported"]
    assert "qualitative_examples" in report
    assert report["qualitative_examples"]["examples_by_expected_label"]["contradicted"]
    assert report["caveats"]

