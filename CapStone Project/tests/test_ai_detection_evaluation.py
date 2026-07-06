from scripts.run_ai_detection_evaluation import _auroc, _binary_metrics


def test_ai_detection_metrics_and_auroc() -> None:
    rows = [
        {"expected": "ai", "predicted": "ai", "score": 0.9},
        {"expected": "ai", "predicted": "human", "score": 0.4},
        {"expected": "human", "predicted": "human", "score": 0.2},
        {"expected": "human", "predicted": "ai", "score": 0.6},
    ]

    metrics = _binary_metrics(rows)

    assert metrics["accuracy"] == 0.5
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert _auroc(rows) == 0.75
