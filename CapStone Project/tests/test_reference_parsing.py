from claimguard.models import Reference
from claimguard.validation.references import (
    ReferenceParser,
    ReferenceValidator,
    _reference_match_score,
)


def test_reference_parser_extracts_core_fields() -> None:
    text = (
        "[1] Smith, A., Lee, R. (2021). Deep Learning Improves Medical Image "
        "Classification. Journal of Applied AI. doi:10.5555/example.2021.001"
    )

    references = ReferenceParser().parse(text)

    assert len(references) == 1
    reference = references[0]
    assert reference.index == "1"
    assert reference.year == 2021
    assert reference.doi == "10.5555/example.2021.001"
    assert reference.title == "Deep Learning Improves Medical Image Classification"
    assert "Smith" in reference.authors


def test_reference_parser_handles_wrapped_apa_and_doi_url() -> None:
    text = """
Smith, A. B., & Lee, R. (2021). Deep learning improves medical image
classification. Journal of Applied AI, 4(2), 10-20.
https://doi.org/10.5555/Example.2021.001

Vaswani, A., Shazeer, N., Parmar, N. (2017). Attention is all you need.
Advances in Neural Information Processing Systems.
"""

    references = ReferenceParser().parse(text)

    assert len(references) == 2
    assert references[0].title == "Deep learning improves medical image classification"
    assert references[0].doi == "10.5555/example.2021.001"
    assert references[0].authors == ["Smith", "Lee"]
    assert references[1].year == 2017
    assert "Vaswani" in references[1].authors


def test_reference_parser_handles_ieee_quoted_title() -> None:
    text = (
        '[3] A. Smith and R. Lee, "A robust approach to citation checking," '
        "Proceedings of the Demo Conference, 2022, doi:10.1234/demo.2022.7."
    )

    reference = ReferenceParser().parse(text)[0]

    assert reference.index == "3"
    assert reference.authors == ["Smith", "Lee"]
    assert reference.title == "A robust approach to citation checking"
    assert reference.year == 2022
    assert reference.doi == "10.1234/demo.2022.7"


def test_reference_validator_offline_and_api_failures_are_graceful() -> None:
    reference = ReferenceParser().parse(
        "[1] Smith, A. (2021). A useful paper. Journal. doi:10.1234/useful.1"
    )[0]

    offline = ReferenceValidator(enable_apis=False).validate(reference)
    assert offline.status == "api_unavailable"
    assert offline.source == "local"

    validator = ReferenceValidator(enable_apis=True, timeout_seconds=1)

    def fail_lookup(_reference):
        raise TimeoutError("simulated timeout")

    validator._query_crossref = fail_lookup
    validator._query_semantic_scholar = fail_lookup
    validator._query_openalex = fail_lookup

    failed = validator.validate(reference)

    assert failed.status == "api_unavailable"
    assert "timeout" in failed.details


def test_reference_parser_handles_unquoted_ieee_author_lists() -> None:
    text = (
        "[1] P. Lewis, E. Perez, A. Piktus, and D. Kiela. "
        "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. "
        "InAdvances in Neural Information Processing Systems, 33:9459-9474, 2020."
    )

    reference = ReferenceParser().parse(text)[0]

    assert reference.title == "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
    assert reference.year == 2020
    assert reference.venue.startswith("In Advances")


def test_reference_parser_does_not_treat_year_as_inline_index() -> None:
    text = (
        "[21] Y. LeCun, Y. Bengio, and G. Hinton. Deep Learning. Nature, 2015. "
        "doi:10.1038/nature14539"
    )

    references = ReferenceParser().parse(text)

    assert len(references) == 1
    assert references[0].year == 2015
    assert references[0].doi == "10.1038/nature14539"


def test_reference_parser_extracts_comma_style_ieee_title() -> None:
    text = (
        "[2] Y. LeCun, L. Bottou, Y. Bengio, and P. Haffner, "
        "Gradient-based learning applied to document recognition, "
        "Proceedings of the IEEE, 1998."
    )

    reference = ReferenceParser().parse(text)[0]

    assert reference.title == "Gradient-based learning applied to document recognition"


def test_reference_parser_extracts_et_al_period_style_title() -> None:
    text = (
        "[5] T. B. Brown et al. Language Models are Few-Shot Learners. "
        "Advances in Neural Information Processing Systems, 2020."
    )

    reference = ReferenceParser().parse(text)[0]

    assert reference.title == "Language Models are Few-Shot Learners"


def test_matching_doi_does_not_override_conflicting_title_and_year() -> None:
    reference = Reference(
        raw_text="Dropout citation with a chimeric DOI",
        title="Dropout: A Simple Way to Prevent Neural Networks from Overfitting",
        authors=["Srivastava"],
        year=2014,
        doi="10.1038/nature14539",
    )

    score = _reference_match_score(
        reference,
        title="Deep learning",
        year=2015,
        doi="10.1038/nature14539",
        candidate_authors=["LeCun", "Bengio", "Hinton"],
        candidate_venue="Nature",
    )

    assert score < 0.65
