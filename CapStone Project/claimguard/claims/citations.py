"""Citation marker extraction."""

from __future__ import annotations

import re

from claimguard.models import Citation

PARENTHETICAL_RE = re.compile(r"\((?P<body>[^()]*?\b(?:19|20)\d{2}[a-z]?[^()]*)\)")
NARRATIVE_RE = re.compile(
    r"(?P<authors>[A-Z][A-Za-z'’-]+"
    r"(?:\s+(?:et\s+al\.?|and|&)\s+[A-Z][A-Za-z'’-]+|"
    r"\s+et\s+al\.?)?)\s*"
    r"\((?P<years>(?:19|20)\d{2}[a-z]?(?:\s*,\s*(?:19|20)\d{2}[a-z]?)*)\)"
)
NUMERIC_RE = re.compile(r"\[(?P<body>\d+(?:\s*(?:,|;|-|–|—)\s*\d+)*)\]")
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})[a-z]?\b")
LEADING_CUE_RE = re.compile(
    r"^(?:see|e\.g\.|cf\.|for example|for review|reviewed in)\s+",
    flags=re.IGNORECASE,
)


def extract_citations(sentence: str, sentence_index: int) -> list[Citation]:
    """Extract numeric, parenthetical, and narrative author-year citations."""

    citations: list[Citation] = []
    occupied_spans: list[tuple[int, int]] = []

    for match in NARRATIVE_RE.finditer(sentence):
        author_text = match.group("authors").strip()
        group_id = _group_id(sentence_index, match.start())
        for year_text in YEAR_RE.findall(match.group("years")):
            citations.append(
                Citation(
                    raw_text=match.group(0),
                    marker=_normalize_marker(f"{author_text} {year_text}"),
                    citation_type="author_year_narrative",
                    sentence_index=sentence_index,
                    year=int(year_text),
                    author_hint=_extract_author_hint(author_text),
                    start_char=match.start(),
                    end_char=match.end(),
                    group_id=group_id,
                )
            )
        occupied_spans.append(match.span())

    for match in PARENTHETICAL_RE.finditer(sentence):
        if _inside_existing_span(match.span(), occupied_spans):
            continue
        group_id = _group_id(sentence_index, match.start())
        parsed = _parse_parenthetical_citations(match, sentence_index, group_id)
        citations.extend(parsed)
        if parsed:
            occupied_spans.append(match.span())

    for match in NUMERIC_RE.finditer(sentence):
        if _inside_existing_span(match.span(), occupied_spans):
            continue
        group_id = _group_id(sentence_index, match.start())
        for number in _expand_numeric_markers(match.group("body")):
            citations.append(
                Citation(
                    raw_text=match.group(0),
                    marker=str(number),
                    citation_type="numeric",
                    sentence_index=sentence_index,
                    start_char=match.start(),
                    end_char=match.end(),
                    group_id=group_id,
                )
            )

    return sorted(citations, key=lambda citation: (citation.start_char or 0, citation.marker))


def strip_citations(sentence: str) -> str:
    """Remove citation markers from a sentence for retrieval/classification."""

    sentence = NARRATIVE_RE.sub(lambda match: match.group("authors"), sentence)
    sentence = PARENTHETICAL_RE.sub("", sentence)
    sentence = NUMERIC_RE.sub("", sentence)
    sentence = re.sub(r"\s+([.,;:!?])", r"\1", sentence)
    return re.sub(r"\s+", " ", sentence).strip()


def _parse_parenthetical_citations(
    match: re.Match[str], sentence_index: int, group_id: str
) -> list[Citation]:
    body = match.group("body").strip()
    if not _looks_like_author_year_citation(body):
        return []

    citations: list[Citation] = []
    inherited_author: str | None = None
    for item in _split_parenthetical_items(body):
        cleaned = LEADING_CUE_RE.sub("", item).strip(" ,")
        if not cleaned:
            continue
        years = [int(year) for year in YEAR_RE.findall(cleaned)]
        if not years:
            continue

        author_text = _author_text_before_first_year(cleaned) or inherited_author
        if not author_text:
            continue
        inherited_author = author_text
        author_hint = _extract_author_hint(author_text)
        for year in years:
            citations.append(
                Citation(
                    raw_text=match.group(0),
                    marker=_normalize_marker(f"{author_text} {year}"),
                    citation_type="author_year",
                    sentence_index=sentence_index,
                    year=year,
                    author_hint=author_hint,
                    start_char=match.start(),
                    end_char=match.end(),
                    group_id=group_id,
                )
            )
    return citations


def _split_parenthetical_items(body: str) -> list[str]:
    return [item.strip() for item in re.split(r"\s*;\s*", body) if item.strip()]


def _looks_like_author_year_citation(body: str) -> bool:
    if not YEAR_RE.search(body):
        return False
    if re.fullmatch(r"(?:19|20)\d{2}[a-z]?(?:\s*,\s*(?:19|20)\d{2}[a-z]?)*", body.strip()):
        return False
    authorish = _author_text_before_first_year(LEADING_CUE_RE.sub("", body).strip())
    return bool(authorish and re.search(r"[A-Z][A-Za-z'’-]+", authorish))


def _author_text_before_first_year(text: str) -> str | None:
    year_match = YEAR_RE.search(text)
    if not year_match:
        return None
    before_year = text[: year_match.start()].strip(" ,")
    before_year = re.sub(r"\s*,\s*$", "", before_year)
    before_year = re.sub(r"\s+(?:and|&)\s+", " and ", before_year)
    if not before_year:
        return None
    return before_year


def _expand_numeric_markers(body: str) -> list[int]:
    numbers: list[int] = []
    for part in re.split(r"\s*(?:,|;)\s*", body.strip()):
        if not part:
            continue
        range_match = re.fullmatch(r"(\d+)\s*(?:-|–|—)\s*(\d+)", part)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start <= end and end - start <= 50:
                numbers.extend(range(start, end + 1))
            else:
                numbers.extend([start, end])
            continue
        number_match = re.fullmatch(r"\d+", part)
        if number_match:
            numbers.append(int(part))
    return _dedupe_preserving_order(numbers)


def _dedupe_preserving_order(values: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _inside_existing_span(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(start <= span[0] and span[1] <= end for start, end in spans)


def _extract_author_hint(body: str) -> str | None:
    before_year = YEAR_RE.split(body, maxsplit=1)[0]
    before_year = before_year.split(";")[-1]
    before_year = re.sub(r"\bet\s+al\.?\b", "", before_year, flags=re.IGNORECASE)
    candidates = re.findall(r"[A-Z][A-Za-z'-]+", before_year)
    return candidates[-1] if candidates else None


def _normalize_marker(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _group_id(sentence_index: int, start_char: int) -> str:
    return f"s{sentence_index}:c{start_char}"
