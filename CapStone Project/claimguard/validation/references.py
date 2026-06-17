"""Reference extraction, parsing, and optional scholarly API validation."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from claimguard.models import Reference, ReferenceValidation
from claimguard.validation.fuzzy import fuzzy_score, normalize_text

LOGGER = logging.getLogger(__name__)

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
ENTRY_START_RE = re.compile(r"^\s*(?:\[(?P<bracket>\d+)\]|(?P<number>\d+)[\.)])\s+")


class ReferenceParser:
    """Extract and parse bibliography entries."""

    def parse(self, references_text: str) -> list[Reference]:
        """Parse a references section into Reference objects."""

        entries = self._split_entries(references_text)
        return [self._parse_entry(entry) for entry in entries if entry.strip()]

    def _split_entries(self, references_text: str) -> list[str]:
        lines = [line.strip() for line in references_text.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            return []

        entries: list[str] = []
        current: list[str] = []
        for line in lines:
            starts_entry = bool(ENTRY_START_RE.match(line))
            starts_entry = starts_entry or bool(
                current
                and YEAR_RE.search(line)
                and re.match(r"^[A-Z][A-Za-z'-]+,\s*[A-Z]", line)
            )
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
        return entries

    def _parse_entry(self, entry: str) -> Reference:
        clean = re.sub(r"\s+", " ", entry).strip()
        index_match = ENTRY_START_RE.match(clean)
        index = None
        if index_match:
            index = index_match.group("bracket") or index_match.group("number")
            clean_without_index = clean[index_match.end() :].strip()
        else:
            clean_without_index = clean

        doi_match = DOI_RE.search(clean_without_index)
        doi = doi_match.group(1).rstrip(".,") if doi_match else None

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

    def __init__(self, enable_apis: bool | None = None, timeout_seconds: int = 8) -> None:
        if enable_apis is None:
            enable_apis = os.getenv("CLAIMGUARD_ENABLE_APIS", "").lower() in {
                "1",
                "true",
                "yes",
            }
        self.enable_apis = enable_apis
        self.timeout_seconds = timeout_seconds

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
            except Exception as exc:  # pragma: no cover - network dependent
                LOGGER.warning("%s lookup failed for %s: %s", source, reference.title, exc)
                failures.append(f"{source}: {exc}")

        if not candidates:
            return ReferenceValidation(
                reference_index=reference.index,
                status="api_unavailable",
                confidence=0.0,
                source="apis",
                doi=reference.doi,
                details="No API result returned. " + "; ".join(failures),
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
        if reference.doi:
            url = f"https://api.crossref.org/works/{quote(reference.doi)}"
            payload = _get_json(url, self.timeout_seconds)
            item = payload.get("message", {})
        else:
            query = quote(reference.title or reference.raw_text)
            mailto = os.getenv("CROSSREF_MAILTO", "")
            mailto_query = f"&mailto={quote(mailto)}" if mailto else ""
            url = f"https://api.crossref.org/works?rows=1&query.bibliographic={query}{mailto_query}"
            payload = _get_json(url, self.timeout_seconds)
            items = payload.get("message", {}).get("items", [])
            item = items[0] if items else {}

        if not item:
            return None
        title = _first(item.get("title"))
        year = _year_from_crossref(item)
        score = _reference_match_score(reference, title, year, item.get("DOI"))
        return {
            "title": title,
            "year": year,
            "doi": item.get("DOI"),
            "score": score,
            "is_retracted": _crossref_problematic(item),
            "details": "CrossRef bibliographic match.",
            "raw": item,
        }

    def _query_semantic_scholar(self, reference: Reference) -> dict[str, Any] | None:
        fields = "title,year,externalIds,abstract,isOpenAccess"
        api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        headers = {"User-Agent": "ClaimGuard/0.1"}
        if api_key:
            headers["x-api-key"] = api_key

        if reference.doi:
            url = (
                "https://api.semanticscholar.org/graph/v1/paper/"
                f"DOI:{quote(reference.doi)}?fields={fields}"
            )
            item = _get_json(url, self.timeout_seconds, headers=headers)
        else:
            query = quote(reference.title or reference.raw_text)
            url = (
                "https://api.semanticscholar.org/graph/v1/paper/search"
                f"?query={query}&limit=1&fields={fields}"
            )
            payload = _get_json(url, self.timeout_seconds, headers=headers)
            data = payload.get("data", [])
            item = data[0] if data else {}

        if not item:
            return None
        external_ids = item.get("externalIds") or {}
        title = item.get("title")
        year = item.get("year")
        score = _reference_match_score(reference, title, year, external_ids.get("DOI"))
        return {
            "title": title,
            "year": year,
            "doi": external_ids.get("DOI"),
            "score": score,
            "abstract": item.get("abstract"),
            "is_retracted": False,
            "details": "Semantic Scholar paper match.",
            "raw": item,
        }

    def _query_openalex(self, reference: Reference) -> dict[str, Any] | None:
        if reference.doi:
            url = f"https://api.openalex.org/works/doi:{quote(reference.doi)}"
            item = _get_json(url, self.timeout_seconds)
        else:
            query = quote(reference.title or reference.raw_text)
            url = f"https://api.openalex.org/works?search={query}&per-page=1"
            payload = _get_json(url, self.timeout_seconds)
            results = payload.get("results", [])
            item = results[0] if results else {}

        if not item:
            return None
        title = item.get("display_name")
        year = item.get("publication_year")
        doi = (item.get("doi") or "").replace("https://doi.org/", "") or None
        score = _reference_match_score(reference, title, year, doi)
        return {
            "title": title,
            "year": year,
            "doi": doi,
            "score": score,
            "is_retracted": bool(item.get("is_retracted")),
            "details": "OpenAlex work match.",
            "raw": item,
        }


def _extract_title(entry: str, year: int | None) -> str | None:
    quoted = re.search(r"[\"']([^\"']{8,220})[\"']", entry)
    if quoted:
        return quoted.group(1).strip()

    work = DOI_RE.sub("", entry)
    if year:
        year_match = re.search(str(year), work)
        if year_match:
            work = work[year_match.end() :]
            work = re.sub(r"^[)\].,\s]+", "", work)

    parts = [part.strip(" .") for part in work.split(".") if part.strip(" .")]
    for part in parts:
        if 3 <= len(part.split()) <= 28 and not _looks_like_venue(part):
            return part
    return parts[0] if parts else None


def _extract_authors(entry: str, year_match: re.Match[str] | None) -> list[str]:
    if not year_match:
        return []
    author_blob = entry[: year_match.start()].strip(" .([")
    last_names = re.findall(r"\b([A-Z][A-Za-z'-]+),\s*(?:[A-Z]\.?)", author_blob)
    if last_names:
        return last_names
    author_blob = author_blob.replace("&", " and ")
    pieces = re.split(r"\s+and\s+|;", author_blob)
    return [piece.strip(" .,") for piece in pieces if piece.strip(" .,")]


def _looks_like_venue(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("journal", "conference", "proceedings", "arxiv", "doi", "volume")
    )


def _get_json(url: str, timeout_seconds: int, headers: dict[str, str] | None = None) -> Any:
    request = Request(url, headers=headers or {"User-Agent": "ClaimGuard/0.1"})
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec - user enabled
        return json.loads(response.read().decode("utf-8"))


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


def _reference_match_score(reference: Reference, title: str | None, year: int | None, doi: str | None) -> float:
    title_score = fuzzy_score(reference.title or reference.raw_text, title or "")
    year_score = 1.0 if reference.year and year and reference.year == year else 0.0
    doi_score = 1.0 if reference.doi and doi and normalize_text(reference.doi) == normalize_text(doi) else 0.0
    return max(title_score * 0.75 + year_score * 0.15 + doi_score * 0.10, doi_score)


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

