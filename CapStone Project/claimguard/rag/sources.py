"""Optional retrieval of open-access source PDFs for RAG evidence."""

from __future__ import annotations

import io
import json
import logging
import os
from urllib.parse import quote
from urllib.request import Request, urlopen

from claimguard.models import EvidencePassage, Reference, ReferenceValidation
from claimguard.rag.retriever import chunk_text

LOGGER = logging.getLogger(__name__)


def fetch_open_access_passages(
    references: list[Reference],
    validations: list[ReferenceValidation],
    timeout_seconds: int = 12,
) -> list[EvidencePassage]:
    """Fetch explicitly enabled OA PDFs and return chunked evidence passages.

    The feature is off by default because it performs network requests and can be
    slow. Set ``CLAIMGUARD_FETCH_FULL_TEXT=true`` and provide ``UNPAYWALL_EMAIL``.
    """

    if os.getenv("CLAIMGUARD_FETCH_FULL_TEXT", "false").lower() not in {"1", "true", "yes"}:
        return []

    max_sources = max(1, int(os.getenv("CLAIMGUARD_MAX_FULL_TEXT_SOURCES", "3")))
    by_index = {item.reference_index: item for item in validations}
    passages: list[EvidencePassage] = []
    fetched = 0
    for position, reference in enumerate(references):
        if fetched >= max_sources:
            break
        validation = by_index.get(reference.index)
        pdf_url = _pdf_url_from_validation(validation)
        if not pdf_url and reference.doi:
            pdf_url = _unpaywall_pdf_url(reference.doi, timeout_seconds)
        if not pdf_url:
            continue
        try:
            text = _download_and_extract_pdf(pdf_url, timeout_seconds)
        except Exception as exc:  # pragma: no cover - network and PDF dependent
            LOGGER.warning("Could not fetch full text for reference %s: %s", reference.index, exc)
            continue
        for chunk_index, chunk in enumerate(chunk_text(text, max_words=140, overlap_words=30)):
            passages.append(
                EvidencePassage(
                    text=chunk,
                    source=f"open_access_pdf:{reference.index or position}",
                    reference_index=reference.index,
                    chunk_id=f"fulltext:{reference.index or position}:{chunk_index}",
                    metadata={"url": pdf_url, "kind": "full_text"},
                )
            )
        fetched += 1
    return passages


def _pdf_url_from_validation(validation: ReferenceValidation | None) -> str | None:
    if not validation:
        return None
    metadata = validation.metadata or {}
    value = metadata.get("open_access_pdf")
    return str(value) if value else None


def _unpaywall_pdf_url(doi: str, timeout_seconds: int) -> str | None:
    email = os.getenv("UNPAYWALL_EMAIL") or os.getenv("CROSSREF_MAILTO")
    if not email:
        return None
    url = f"https://api.unpaywall.org/v2/{quote(doi)}?email={quote(email)}"
    request = Request(url, headers={"User-Agent": "ClaimGuard/0.2"})
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec - explicit opt-in
        payload = json.loads(response.read().decode("utf-8"))
    location = payload.get("best_oa_location") or {}
    return location.get("url_for_pdf")


def _download_and_extract_pdf(url: str, timeout_seconds: int) -> str:
    if not url.lower().startswith(("https://", "http://")):
        raise ValueError("Only HTTP(S) PDF URLs are supported")
    request = Request(url, headers={"User-Agent": "ClaimGuard/0.2"})
    max_bytes = 20 * 1024 * 1024
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec - explicit opt-in
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("PDF exceeds the 20 MB safety limit")
    if not data.startswith(b"%PDF"):
        raise ValueError("Downloaded source is not a PDF")
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
