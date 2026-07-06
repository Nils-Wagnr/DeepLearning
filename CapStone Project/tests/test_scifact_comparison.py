from pathlib import Path

from scripts.run_scifact_model_comparison import LABELS, _metrics, load_balanced_scifact_examples


def test_scifact_subset_is_balanced_and_reproducible() -> None:
    archive = Path("data/cache/scifact-data.tar.gz")
    first = load_balanced_scifact_examples(archive, per_label=2, seed=42)
    second = load_balanced_scifact_examples(archive, per_label=2, seed=42)

    assert first == second
    assert len(first) == 6
    assert {label: sum(row["expected"] == label for row in first) for label in LABELS} == {
        label: 2 for label in LABELS
    }


def test_scifact_metrics_compute_macro_f1() -> None:
    rows = [
        {"expected": "SUPPORT", "predicted": "SUPPORT", "correct": True, "latency_ms": 1},
        {
            "expected": "CONTRADICT",
            "predicted": "CONTRADICT",
            "correct": True,
            "latency_ms": 1,
        },
        {
            "expected": "NOT_ENOUGH_INFO",
            "predicted": "NOT_ENOUGH_INFO",
            "correct": True,
            "latency_ms": 1,
        },
    ]

    metrics = _metrics(rows)

    assert metrics["accuracy"] == 1.0
    assert metrics["macro_f1"] == 1.0
