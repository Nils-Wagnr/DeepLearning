from claimguard.validation.fuzzy import fuzzy_score, normalize_text


def test_fuzzy_score_handles_minor_title_variation() -> None:
    score = fuzzy_score(
        "Deep Learning Improves Medical Image Classification",
        "Deep learning improved medical image classification",
    )

    assert score > 0.75


def test_fuzzy_score_handles_word_order_and_noise() -> None:
    score = fuzzy_score(
        "https://doi.org/10.1234/x Deep-Learning for Medical Image Classification",
        "Medical image classification using deep learning",
    )

    assert score > 0.7
    assert normalize_text("DOI:10.1234/X") == "10 1234 x"


def test_fuzzy_score_keeps_unrelated_titles_low() -> None:
    score = fuzzy_score(
        "Attention is all you need",
        "Soil moisture measurements in alpine forests",
    )

    assert score < 0.45
