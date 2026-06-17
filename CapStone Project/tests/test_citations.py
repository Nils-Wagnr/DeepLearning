from claimguard.claims.citations import extract_citations, strip_citations


def test_extract_author_year_and_numeric_citations() -> None:
    sentence = "Prior work improved accuracy (Smith et al., 2023) and reduced cost [1, 2]."

    citations = extract_citations(sentence, sentence_index=0)

    markers = {citation.marker for citation in citations}
    assert "smith et al 2023" in markers
    assert "1" in markers
    assert "2" in markers
    assert any(citation.year == 2023 for citation in citations)


def test_extracts_ranges_multiple_parenthetical_and_narrative_citations() -> None:
    sentence = (
        "Smith et al. (2020, 2021) reported gains, while later reviews "
        "confirmed limits (see Lee & Kim, 2022; Patel, 2023) [3-5; 8]."
    )

    citations = extract_citations(sentence, sentence_index=2)

    markers = {citation.marker for citation in citations}
    numeric_markers = {
        citation.marker for citation in citations if citation.citation_type == "numeric"
    }
    assert {"3", "4", "5", "8"} <= numeric_markers
    assert "smith et al 2020" in markers
    assert "smith et al 2021" in markers
    assert "lee and kim 2022" in markers
    assert "patel 2023" in markers
    assert all(citation.start_char is not None for citation in citations)
    assert all(citation.group_id for citation in citations)


def test_strip_citations_removes_markers_without_dropping_narrative_author() -> None:
    sentence = "Smith et al. (2023) showed improvements [1]."

    stripped = strip_citations(sentence)

    assert stripped == "Smith et al. showed improvements."
