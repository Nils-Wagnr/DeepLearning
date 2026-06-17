from claimguard.validation.references import ReferenceParser


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

