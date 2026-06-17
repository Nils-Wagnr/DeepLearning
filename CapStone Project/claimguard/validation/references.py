"""Reference extraction, parsing, and optional scholarly API validation."""

from __future__ import annotations

import json
import logging
import os
import re
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from claimguard.models import Reference, ReferenceValidation
from claimguard.validation.fuzzy import fuzzy_score, meaningful_tokens, normalize_text

LOGGER = logging.getLogger(__name__)

DOI_RE = re.compile(
    r"(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
ENTRY_START_RE = re.compile(r"^\s*(?:\[(?P<bracket>\d+)\]|(?P<number>\d+)[\.)])\s+")
AUTHOR_YEAR_START_RE = re.compile(
    r"^[A-Z][A-Za-z'-]+,\s*(?:[A-Z]\.|[A-Z][a-z]+|[A-Z][A-Za-z'-]+)",
)
INITIAL_AUTHOR_START_RE = re.compile(r"^(?:[A-Z]\.\s*)+[A-Z][A-Za-z'-]+")


class ApiLookupError(RuntimeError):
    """Network/API lookup failed in a way that should not stop the pipeline."""


class ReferenceParser:
    """Extract and parse bibliography entries."""

    def parse(self, references_text: str) -> list[Reference]:
        """Parse a references section into Reference objects."""

        entries = self._split_entries(references_text)
        return [self._parse_entry(entry) for entry in entries if entry.strip()]

    def _split_entries(self, references_text: str) -> list[str]:
        normalized_text = _normalize_reference_block(references_text)
        lines = [line.strip() for line in normalized_text.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            return []

        entries: list[str] = []
        current: list[str] = []
        for line in lines:
            starts_entry = _looks_like_entry_start(line)
            if starts_entry and current:
                entries.append(" ".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            entries.append(" ".join(current))

        if len(entries) == 1:
            blank_split = [
                item.strip()
                for item in re.split(r"\n\s*\n", references_text)
                if item.strip()
            ]
            if len(blank_split) > 1:
                return blank_split
            inline_split = _split_inline_entries(entries[0])
            if len(inline_split) > 1:
                return inline_split
        return [entry for entry in entries if _looks_like_reference_entry(entry)]

    def _parse_entry(self, entry: str) -> Reference:
        clean = re.sub(r"\s+", " ", entry).strip()
        index_match = ENTRY_START_RE.match(clean)
        index = None
        if index_match:
            index = index_match.group("bracket") or index_match.group("number")
            clean_without_index = clean[index_match.end() :].strip()
        else:
            clean_without_index = clean

        doi = _extract_doi(clean_without_index)

        year_match = YEAR_RE.search(clean_without_index)
        year = int(year_match.group(1)) if year_match else None

        title = _extract_title(clean_without_index, year)
        authors = _extract_authors(clean_without_index, year_match)

        return Reference(
            raw_text=clean,
            index=index,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
        )


class ReferenceValidator:
    """Validate parsed references with optional CrossRef, Semantic Scholar, and OpenAlex."""

    def __init__(
        self,
        enable_apis: bool | None = None,
        timeout_seconds: int = 6,
        max_results: int = 3,
    ) -> None:
        if enable_apis is None:
            enable_apis = os.getenv("CLAIMGUARD_ENABLE_APIS", "").lower() in {
                "1",
                "true",
                "yes",
            }
        self.enable_apis = enable_apis
        self.timeout_seconds = max(1, timeout_seconds)
        self.max_results = max(1, max_results)

    def validate_all(self, references: list[Reference]) -> list[ReferenceValidation]:
        """Validate many references."""

        return [self.validate(reference) for reference in references]

    def validate(self, reference: Reference) -> ReferenceValidation:
        """Validate a single reference and return the best available result."""

        if not self.enable_apis:
            return ReferenceValidation(
                reference_index=reference.index,
                status="api_unavailable",
                confidence=0.0,
                source="local",
                doi=reference.doi,
                details="External APIs are disabled; parsed metadata is available only.",
            )

        candidates: list[dict[str, Any]] = []
        failures: list[str] = []
        no_match_sources: list[str] = []
        for source, query_fn in (
            ("crossref", self._query_crossref),
            ("semantic_scholar", self._query_semantic_scholar),
            ("openalex", self._query_openalex),
        ):
            try:
                result = query_fn(reference)
                if result:
                    result["source"] = source
                    candidates.append(result)
                else:
                    no_match_sources.append(source)
            except ApiLookupError as exc:
                LOGGER.warning("%s lookup unavailable for %s: %s", source, reference.title, exc)
                failures.append(f"{source}: {exc}")
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.warning("%s lookup failed for %s: %s", source, reference.title, exc)
                failures.append(f"{source}: {exc}")

        if not candidates:
            if failures and not no_match_sources:
                return ReferenceValidation(
                    reference_index=reference.index,
                    status="api_unavailable",
                    confidence=0.0,
                    source="apis",
                    doi=reference.doi,
                    details="All API lookups were unavailable. " + "; ".join(failures),
                )
            return ReferenceValidation(
                reference_index=reference.index,
                status="unverified",
                confidence=0.0,
                source="apis",
                doi=reference.doi,
                details=(
                    "APIs responded but no plausible bibliographic match was found."
                    if no_match_sources
                    else "No API result returned."
                )
                + (" " + "; ".join(failures) if failures else ""),
            )

        best = max(candidates, key=lambda item: item.get("score", 0.0))
        status = _status_from_candidate(reference, best)
        return ReferenceValidation(
            reference_index=reference.index,
            status=status,
            confidence=round(float(best.get("score", 0.0)), 3),
            source=str(best.get("source", "unknown")),
            matched_title=best.get("title"),
            matched_year=best.get("year"),
            doi=best.get("doi") or reference.doi,
            details=best.get("details", ""),
            metadata=best,
        )

    def _query_crossref(self, reference: Reference) -> dict[str, Any] | None:
        items: list[dict[str, Any]] = []
        if reference.doi:
            url = f"https://api.crossref.org/works/{quote(reference.doi)}"
            payload = _get_json(url, self.timeout_seconds)
            if payload:
                message = payload.get("message", {})
                if message:
                    items.append(message)

        if not items:
            params = {
                "rows": str(self.max_results),
                "query.bibliographic": reference.title or reference.raw_text,
            }
            mailto = os.getenv("CROSSREF_MAILTO", "")
            if mailto:
                params["mailto"] = mailto
            url = f"https://api.crossref.org/works?{urlencode(params)}"
            payload = _get_json(url, self.timeout_seconds)
            if payload:
                items.extend(payload.get("message", {}).get("items", [])[: self.max_results])

        if not items:
            return None
        candidates = [_crossref_candidate(reference, item) for item in items]
        return _best_candidate(candidates)

    def _query_semantic_scholar(self, reference: Reference) -> dict[str, Any] | None:
        fields = "title,year,externalIds,abstract,isOpenAccess,authors"
        api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        headers = {"User-Agent": "ClaimGuard/0.1"}
        if api_key:
            headers["x-api-key"] = api_key

        items: list[dict[str, Any]] = []
        if reference.doi:
            url = (
                "https://api.semanticscholar.org/graph/v1/paper/"
                f"DOI:{quote(reference.doi)}?fields={fields}"
            )
            item = _get_json(url, self.timeout_seconds, headers=headers)
            if item:
                items.append(item)

        if not items:
            query = quote(reference.title or reference.raw_text)
            url = (
                "https://api.semanticscholar.org/graph/v1/paper/search"
                f"?query={query}&limit={self.max_results}&fields={fields}"
            )
            payload = _get_json(url, self.timeout_seconds, headers=headers)
            if payload:
                items.extend(payload.get("data", [])[: self.max_results])

        if not items:
            return None
        candidates = [_semantic_scholar_candidate(reference, item) for item in items]
        return _best_candidate(candidates)

    def _query_openalex(self, reference: Reference) -> dict[str, Any] | None:
        items: list[dict[str, Any]] = []
        if reference.doi:
            url = f"https://api.openalex.org/works/doi:{quote(reference.doi)}"
            item = _get_json(url, self.timeout_seconds)
            if item:
                items.append(item)

        if not items:
            params = {
                "search": reference.title or reference.raw_text,
                "per-page": str(self.max_results),
            }
            mailto = os.getenv("OPENALEX_MAILTO", "")
            if mailto:
                params["mailto"] = mailto
            url = f"https://api.openalex.org/works?{urlencode(params)}"
            payload = _get_json(url, self.timeout_seconds)
            if payload:
                items.extend(payload.get("results", [])[: self.max_results])

        if not items:
            return None
        candidates = [_openalex_candidate(reference, item) for item in items]
        return _best_candidate(candidates)


def _extract_title(entry: str, year: int | None) -> str | None:
    quoted = re.search(r"[\"']([^\"']{8,220})[\"']", entry)
    if quoted:
        return _clean_title(quoted.group(1))

    work = DOI_RE.sub("", entry)
    if year:
        apa_match = re.search(rf"\(?{year}\)?[a-z]?\s*[.)]?\s*", work)
        if apa_match:
            after_year = re.sub(r"^[)\].,\s]+", "", work[apa_match.end() :])
            for sentence in _split_reference_sentences(after_year):
                if _looks_like_title_candidate(sentence):
                    return _clean_title(sentence)

    parts = [part.strip(" .") for part in work.split(".") if part.strip(" .")]
    for part in parts:
        if _looks_like_title_candidate(part):
            return _clean_title(part)
    return _clean_title(parts[0]) if parts else None


def _extract_authors(entry: str, year_match: re.Match[str] | None) -> list[str]:
    author_blob = entry
    quoted_title = re.search(r"[\"']", author_blob)
    if quoted_title:
        author_blob = author_blob[: quoted_title.start()]
    elif year_match:
        author_blob = author_blob[: year_match.start()]
    else:
        author_blob = author_blob.split(".", 1)[0]

    author_blob = ENTRY_START_RE.sub("", author_blob).strip(" .([")
    author_blob = re.sub(r"\bet\s+al\.?", "", author_blob, flags=re.IGNORECASE)
    last_names = re.findall(r"\b([A-Z][A-Za-z'-]+),\s*(?:[A-Z]\.?|[A-Z][a-z]+)", author_blob)
    if last_names:
        return _dedupe(last_names)

    ieee_names = re.findall(r"(?:\b[A-Z]\.\s*)+([A-Z][A-Za-z'-]+)", author_blob)
    if ieee_names:
        return _dedupe(ieee_names)

    author_blob = author_blob.replace("&", " and ")
    pieces = re.split(r"\s+and\s+|;", author_blob)
    cleaned = [piece.strip(" .,") for piece in pieces if piece.strip(" .,")]
    return _dedupe([_last_author_token(piece) for piece in cleaned if _last_author_token(piece)])


def _normalize_reference_block(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _looks_like_entry_start(line: str) -> bool:
    if ENTRY_START_RE.match(line):
        return True
    if not YEAR_RE.search(line[:260]):
        return False
    return bool(AUTHOR_YEAR_START_RE.match(line) or INITIAL_AUTHOR_START_RE.match(line))


def _looks_like_reference_entry(entry: str) -> bool:
    return bool(YEAR_RE.search(entry) or DOI_RE.search(entry) or ENTRY_START_RE.match(entry))


def _split_inline_entries(entry: str) -> list[str]:
    numbered = [
        part.strip()
        for part in re.split(r"(?=\s*(?:\[\d+\]|\d+[\.)])\s+)", entry)
        if part.strip()
    ]
    numbered = [part for part in numbered if _looks_like_reference_entry(part)]
    if len(numbered) > 1:
        return numbered

    parts = [
        part.strip()
        for part in re.split(
            r"(?<=\.)\s+(?=[A-Z][A-Za-z'-]+,\s*(?:[A-Z]\.|[A-Z][a-z]+).{0,220}?\((?:19|20)\d{2})",
            entry,
        )
        if part.strip()
    ]
    return parts if len(parts) > 1 else [entry]


def _extract_doi(entry: str) -> str | None:
    match = DOI_RE.search(entry)
    if not match:
        return None
    doi = match.group(1).strip()
    return doi.rstrip(".,;:)])").lower()


def _split_reference_sentences(text: str) -> list[str]:
    protected = re.sub(r"\b([A-Z])\.", r"\1<dot>", text)
    parts = re.split(r"\.\s+", protected)
    return [part.replace("<dot>", ".").strip(" .") for part in parts if part.strip(" .")]


def _looks_like_title_candidate(text: str) -> bool:
    cleaned = _clean_title(text)
    if not cleaned:
        return False
    words = cleaned.split()
    if len(words) < 2 or len(words) > 32:
        return False
    if _looks_like_venue(cleaned):
        return False
    if YEAR_RE.fullmatch(cleaned):
        return False
    if DOI_RE.search(cleaned):
        return False
    return True


def _clean_title(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" ,.;:\"'")
    text = re.sub(r"\s*,\s*$", "", text)
    return text or None


def _last_author_token(text: str) -> str | None:
    match = re.search(r"([A-Z][A-Za-z'-]+)\s*$", text)
    return match.group(1) if match else None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = normalize_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _looks_like_venue(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("journal", "conference", "proceedings", "arxiv", "doi", "volume")
    )


def _get_json(url: str, timeout_seconds: int, headers: dict[str, str] | None = None) -> Any:
    request_headers = {"User-Agent": "ClaimGuard/0.1"}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # nosec - user enabled
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise ApiLookupError(f"HTTP {exc.code} for {url}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ApiLookupError(f"timeout after {timeout_seconds}s") from exc
    except URLError as exc:
        raise ApiLookupError(f"network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ApiLookupError("invalid JSON response") from exc


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _year_from_crossref(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            return int(parts[0][0])
    return None


def _reference_match_score(
    reference: Reference,
    title: str | None,
    year: int | None,
    doi: str | None,
    candidate_authors: list[str] | None = None,
) -> float:
    title_score = fuzzy_score(reference.title or reference.raw_text, title or "")
    year_score = 1.0 if reference.year and year and reference.year == year else 0.0
    if reference.year and year and reference.year != year:
        year_score = -0.25
    doi_score = 1.0 if reference.doi and doi and normalize_text(reference.doi) == normalize_text(doi) else 0.0
    author_score = _author_match_score(reference.authors, candidate_authors or [])
    weighted = (title_score * 0.72) + (year_score * 0.12) + (doi_score * 0.12) + (author_score * 0.04)
    if doi_score == 1.0:
        weighted = max(weighted, 0.96)
    return round(max(0.0, min(1.0, weighted)), 3)


def _author_match_score(reference_authors: list[str], candidate_authors: list[str]) -> float:
    if not reference_authors or not candidate_authors:
        return 0.0
    left = {token for author in reference_authors for token in meaningful_tokens(author)}
    right = {token for author in candidate_authors for token in meaningful_tokens(author)}
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def _best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    filtered = [candidate for candidate in candidates if candidate.get("title") or candidate.get("doi")]
    if not filtered:
        return None
    return max(filtered, key=lambda item: float(item.get("score", 0.0)))


def _crossref_candidate(reference: Reference, item: dict[str, Any]) -> dict[str, Any]:
    title = _first(item.get("title"))
    year = _year_from_crossref(item)
    authors = [
        author.get("family")
        for author in item.get("author", [])
        if isinstance(author, dict) and author.get("family")
    ]
    doi = item.get("DOI")
    score = _reference_match_score(reference, title, year, doi, authors)
    return {
        "title": title,
        "year": year,
        "doi": doi,
        "authors": authors,
        "score": score,
        "is_retracted": _crossref_problematic(item),
        "details": "CrossRef bibliographic match.",
        "raw": item,
    }


def _semantic_scholar_candidate(reference: Reference, item: dict[str, Any]) -> dict[str, Any]:
    external_ids = item.get("externalIds") or {}
    authors = [
        author.get("name")
        for author in item.get("authors", [])
        if isinstance(author, dict) and author.get("name")
    ]
    title = item.get("title")
    year = item.get("year")
    doi = external_ids.get("DOI")
    score = _reference_match_score(reference, title, year, doi, authors)
    return {
        "title": title,
        "year": year,
        "doi": doi,
        "authors": authors,
        "score": score,
        "abstract": item.get("abstract"),
        "is_retracted": False,
        "details": "Semantic Scholar paper match.",
        "raw": item,
    }


def _openalex_candidate(reference: Reference, item: dict[str, Any]) -> dict[str, Any]:
    authors = [
        authorship.get("author", {}).get("display_name")
        for authorship in item.get("authorships", [])
        if isinstance(authorship, dict)
    ]
    authors = [author for author in authors if author]
    title = item.get("display_name")
    year = item.get("publication_year")
    doi = _normalize_doi(item.get("doi"))
    score = _reference_match_score(reference, title, year, doi, authors)
    return {
        "title": title,
        "year": year,
        "doi": doi,
        "authors": authors,
        "score": score,
        "is_retracted": bool(item.get("is_retracted")),
        "details": "OpenAlex work match.",
        "raw": item,
    }


def _normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return value.strip().lower() or None


def _crossref_problematic(item: dict[str, Any]) -> bool:
    relation = item.get("relation") or {}
    update_to = item.get("update-to") or []
    subtype = str(item.get("subtype") or "").lower()
    return bool(update_to or "retraction" in subtype or relation.get("is-retracted-by"))


def _status_from_candidate(reference: Reference, candidate: dict[str, Any]) -> str:
    if candidate.get("is_retracted"):
        return "retracted_or_problematic"
    score = float(candidate.get("score", 0.0))
    if score >= 0.88:
        return "verified"
    if score >= 0.65:
        return "partially_matched"
    return "unverified"
