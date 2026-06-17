from claimguard.validation.fuzzy import fuzzy_score


def test_fuzzy_score_handles_minor_title_variation() -> None:
    score = fuzzy_score(
        "Deep Learning Improves Medical Image Classification",
        "Deep learning improved medical image classification",
    )

    assert score > 0.75

