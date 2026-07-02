"""Input document parsing for TXT and PDF files."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from claimguard.models import DocumentSections

LOGGER = logging.getLogger(__name__)


class DocumentParser:
    """Parse supported academic document formats into plain text."""

    def parse(self, path: str | Path) -> str:
        """Return extracted text for a .txt or .pdf document."""

        input_path = Path(path)
        suffix = input_path.suffix.lower()
        if suffix == ".txt":
            return self._parse_txt(input_path)
        if suffix == ".pdf":
            return self._parse_pdf(input_path)
        raise ValueError(f"Unsupported input type: {suffix}. Use .txt or .pdf")

    def _parse_txt(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            LOGGER.warning("UTF-8 failed for %s; falling back to cp1252", path)
            return path.read_text(encoding="cp1252")

    def _parse_pdf(self, path: Path) -> str:
        errors: list[str] = []

        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return _clean_pdf_pages([page.extract_text() or "" for page in reader.pages])
        except Exception as exc:  # pragma: no cover - depends on optional package
            errors.append(f"pypdf: {exc}")

        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return _clean_pdf_pages([page.extract_text() or "" for page in reader.pages])
        except Exception as exc:  # pragma: no cover - depends on optional package
            errors.append(f"PyPDF2: {exc}")

        try:
            from pdfminer.high_level import extract_text  # type: ignore

            return _clean_pdf_pages([extract_text(str(path))])
        except Exception as exc:  # pragma: no cover - depends on optional package
            errors.append(f"pdfminer.six: {exc}")

        fallback_text = _parse_pdf_minimal(path)
        if fallback_text.strip():
            LOGGER.warning("Using minimal built-in PDF extractor for %s", path)
            return fallback_text

        joined = "; ".join(errors) or "no PDF parser installed"
        raise RuntimeError(
            "Could not extract PDF text. Install pypdf or pdfminer.six. "
            f"Parser errors: {joined}"
        )


SECTION_RE = re.compile(
    r"(?im)^\s*(references|bibliography|works cited|evidence passages?|sample evidence)\s*:?\s*$"
)


def split_document_sections(text: str) -> DocumentSections:
    """Split text into main, references, and evidence sections when headings exist."""

    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return DocumentSections(main_text=text)

    chunks: dict[str, str] = {}
    main_text = text[: matches[0].start()].strip()
    for index, match in enumerate(matches):
        heading = match.group(1).lower()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        if heading in {"references", "bibliography", "works cited"}:
            chunks["references"] = body
        else:
            chunks["evidence"] = body

    return DocumentSections(
        main_text=main_text,
        references_text=chunks.get("references", ""),
        evidence_text=chunks.get("evidence", ""),
    )


def _parse_pdf_minimal(path: Path) -> str:
    """Extract text from simple PDF content streams without external packages.

    This fallback is intentionally small. It handles common Flate-compressed
    text streams and PDF literal strings, which is enough for many generated
    academic reports. Full PDF support should still use pypdf or pdfminer.six.
    """

    import zlib

    data = path.read_bytes()
    texts: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, flags=re.S):
        stream = match.group(1)
        try:
            decoded = zlib.decompress(stream)
        except Exception:
            decoded = stream
        if b"BT" not in decoded:
            continue
        text = _extract_pdf_text_operators(decoded.decode("latin-1", errors="ignore"))
        if text.strip():
            texts.append(text)
    return "\n".join(texts)


def _extract_pdf_text_operators(content: str) -> str:
    blocks = re.findall(r"BT(.*?)ET", content, flags=re.S)
    lines: list[str] = []
    for block in blocks:
        for array_match in re.finditer(r"\[(.*?)\]\s*TJ", block, flags=re.S):
            parsed = _parse_pdf_tj_array(array_match.group(1))
            if parsed:
                lines.append(parsed)
        for literal in _literal_strings_before_operator(block, "Tj"):
            parsed = _decode_pdf_literal(literal)
            if parsed:
                lines.append(parsed)
        for literal in _literal_strings_before_operator(block, "'"):
            parsed = _decode_pdf_literal(literal)
            if parsed:
                lines.append(parsed)
    return "\n".join(_clean_pdf_text(line) for line in lines if _clean_pdf_text(line))


def _literal_strings_before_operator(block: str, operator: str) -> list[str]:
    values: list[str] = []
    index = 0
    while index < len(block):
        if block[index] != "(":
            index += 1
            continue
        literal, next_index = _read_pdf_literal(block, index)
        tail = block[next_index : next_index + 8]
        if re.match(rf"\s*{re.escape(operator)}", tail):
            values.append(literal)
        index = next_index
    return values


def _parse_pdf_tj_array(array_body: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(array_body):
        char = array_body[index]
        if char == "(":
            literal, index = _read_pdf_literal(array_body, index)
            parts.append(_decode_pdf_literal(literal))
            continue
        number_match = re.match(r"[-+]?\d+(?:\.\d+)?", array_body[index:])
        if number_match:
            value = float(number_match.group(0))
            if value < -120:
                parts.append(" ")
            index += len(number_match.group(0))
            continue
        index += 1
    return _clean_pdf_text("".join(parts))


def _read_pdf_literal(text: str, start: int) -> tuple[str, int]:
    depth = 1
    escaped = False
    index = start + 1
    chars: list[str] = []
    while index < len(text):
        char = text[index]
        if escaped:
            chars.append("\\" + char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "(":
            depth += 1
            chars.append(char)
        elif char == ")":
            depth -= 1
            if depth == 0:
                return "".join(chars), index + 1
            chars.append(char)
        else:
            chars.append(char)
        index += 1
    return "".join(chars), index


def _decode_pdf_literal(value: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            output.append(char)
            index += 1
            continue
        index += 1
        if index >= len(value):
            break
        escaped = value[index]
        if escaped in {"n", "r"}:
            output.append("\n")
            index += 1
        elif escaped == "t":
            output.append("\t")
            index += 1
        elif escaped in {"b", "f"}:
            index += 1
        elif escaped in {"\\", "(", ")"}:
            output.append(escaped)
            index += 1
        elif escaped in {"\n", "\r"}:
            index += 1
        elif escaped.isdigit():
            octal = escaped
            index += 1
            while index < len(value) and len(octal) < 3 and value[index].isdigit():
                octal += value[index]
                index += 1
            output.append(chr(int(octal, 8)))
        else:
            output.append(escaped)
            index += 1
    return "".join(_map_pdf_glyph(char) for char in output)


def _map_pdf_glyph(char: str) -> str:
    glyph_map = {
        "\x1c": "fi",
        "\x1d": "fl",
        "\x84": "",
        "\x86": "",
    }
    if char in glyph_map:
        return glyph_map[char]
    if ord(char) < 32 and char not in {"\n", "\t"}:
        return ""
    return char


def _clean_pdf_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    return text.strip()


def _clean_pdf_pages(pages: list[str]) -> str:
    """Repair common extraction artifacts and remove repeated headers/footers."""

    normalized_pages: list[list[str]] = []
    line_counts: dict[str, int] = {}
    for page in pages:
        lines = [re.sub(r"\s+", " ", line).strip() for line in page.splitlines()]
        lines = [line for line in lines if line]
        normalized_pages.append(lines)
        for line in set(lines):
            if len(line) <= 120:
                line_counts[line] = line_counts.get(line, 0) + 1

    repeated_threshold = max(2, (len(pages) + 1) // 2)
    repeated = {
        line
        for line, count in line_counts.items()
        if count >= repeated_threshold and (re.fullmatch(r"\d+", line) or len(line.split()) <= 12)
    }
    cleaned_pages = ["\n".join(line for line in lines if line not in repeated) for lines in normalized_pages]
    text = "\n\n".join(cleaned_pages)
    replacements = {
        "â€“": "–",
        "â€”": "—",
        "âˆ’": "−",
        "âˆ—": "∗",
        "Ã—": "×",
        "Î»": "λ",
        "â‰ˆ": "≈",
        "â‰¤": "≤",
        "â‰¥": "≥",
        "â€™": "’",
        "â€œ": "“",
        "â€": "”",
    }
    for broken, repaired in replacements.items():
        text = text.replace(broken, repaired)
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=[a-z])", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
