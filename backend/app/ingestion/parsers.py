"""
Document ingestion parsers (Section 5).

Supports PDF, DOCX, TXT. Each parser returns a ParsedDocument that keeps
page-level text separate (needed for evidence page numbers, Section 7) and
records which extraction method was used, so downstream code/audits know
whether OCR was invoked.

Parsing strategy per format:
  PDF  -> pdfplumber (handles both single- and two-column layouts reasonably
          well via word-position-aware extraction) first; if a page yields
          empty/near-empty text (common for scanned/image PDFs), fall back
          to OCR (pytesseract + pdf2image) for that page specifically,
          rather than assuming the whole document needs OCR.
  DOCX -> python-docx, walking paragraphs AND tables (table-based resumes,
          Section 5) so table cells aren't silently dropped.
  TXT  -> read as-is, one "page".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.exceptions import ProcessingError, UnsupportedFileError

logger = logging.getLogger("app.ingestion.parsers")

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_MIME = "text/plain"

SUPPORTED_MIME_TYPES = {PDF_MIME, DOCX_MIME, TXT_MIME}


@dataclass
class ParsedPage:
    page_number: int
    text: str
    used_ocr: bool = False


@dataclass
class ParsedDocument:
    full_text: str
    pages: list[ParsedPage] = field(default_factory=list)
    extraction_method: str = "unknown"
    used_ocr: bool = False
    page_count: int = 0


def parse_document(file_bytes: bytes, mime_type: str, filename: str) -> ParsedDocument:
    if mime_type == PDF_MIME:
        return _parse_pdf(file_bytes)
    if mime_type == DOCX_MIME:
        return _parse_docx(file_bytes)
    if mime_type == TXT_MIME:
        return _parse_txt(file_bytes)
    raise UnsupportedFileError(f"Unsupported file type '{mime_type}' for '{filename}'. Supported: PDF, DOCX, TXT.")


def _parse_txt(file_bytes: bytes) -> ParsedDocument:
    try:
        text = file_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        raise ProcessingError(f"Could not decode text file: {exc}")
    return ParsedDocument(
        full_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
        extraction_method="txt",
        page_count=1,
    )


def _parse_docx(file_bytes: bytes) -> ParsedDocument:
    import io

    try:
        import docx  # python-docx
    except ImportError as exc:
        raise ProcessingError(f"python-docx not available: {exc}")

    try:
        document = docx.Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ProcessingError(f"Corrupt or unreadable DOCX file: {exc}")

    parts: list[str] = []

    # Paragraphs, in document order.
    for para in document.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())

    # Tables -- table-based resumes (Section 5) store real content in cells
    # that .paragraphs alone would miss.
    for table in document.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)

    full_text = "\n".join(parts)
    if not full_text.strip():
        raise ProcessingError("DOCX file contained no extractable text.")

    return ParsedDocument(
        full_text=full_text,
        pages=[ParsedPage(page_number=1, text=full_text)],  # DOCX has no reliable page boundaries pre-render
        extraction_method="docx",
        page_count=1,
    )


def _parse_pdf(file_bytes: bytes) -> ParsedDocument:
    import io

    try:
        import pdfplumber
    except ImportError as exc:
        raise ProcessingError(f"pdfplumber not available: {exc}")

    pages: list[ParsedPage] = []
    any_ocr = False

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                page_used_ocr = False

                # Two-column layouts: pdfplumber's default extract_text can
                # interleave columns. Detect a likely two-column page (words
                # cluster into two distinct x-position bands) and re-extract
                # by sorting words into left/right bands, top-to-bottom.
                text = _reflow_if_two_column(page, text)

                if len(text) < 20:
                    # Likely a scanned/image page -- try OCR for this page only.
                    ocr_text = _ocr_pdf_page(file_bytes, i)
                    if ocr_text:
                        text = ocr_text
                        any_ocr = True
                        page_used_ocr = True

                pages.append(ParsedPage(page_number=i, text=text, used_ocr=page_used_ocr))
    except Exception as exc:
        raise ProcessingError(f"Corrupt or unreadable PDF file: {exc}")

    full_text = "\n".join(p.text for p in pages if p.text)
    if not full_text.strip():
        raise ProcessingError("PDF file contained no extractable text, including after OCR fallback.")

    return ParsedDocument(
        full_text=full_text,
        pages=pages,
        extraction_method="pdf_ocr" if any_ocr else "pdf_text",
        used_ocr=any_ocr,
        page_count=len(pages),
    )


def _reflow_if_two_column(page, fallback_text: str) -> str:
    """Best-effort two-column reflow: cluster words by x0 into left/right
    halves of the page and read left column top-to-bottom, then right
    column top-to-bottom. Falls back to pdfplumber's default text if word
    extraction isn't available or the page doesn't look two-column.
    """
    try:
        words = page.extract_words()
    except Exception:
        return fallback_text

    if not words:
        return fallback_text

    page_width = page.width
    mid = page_width / 2
    left_words = [w for w in words if w["x0"] < mid]
    right_words = [w for w in words if w["x0"] >= mid]

    # Heuristic: only treat as two-column if both halves have a meaningful,
    # comparable share of the words (otherwise this is just a normal page
    # with some right-aligned dates/headers).
    if len(left_words) < 10 or len(right_words) < 10:
        return fallback_text
    ratio = min(len(left_words), len(right_words)) / max(len(left_words), len(right_words))
    if ratio < 0.25:
        return fallback_text

    def _to_lines(word_list):
        word_list = sorted(word_list, key=lambda w: (round(w["top"]), w["x0"]))
        lines: list[str] = []
        current_top = None
        current_line: list[str] = []
        for w in word_list:
            top = round(w["top"] / 3) * 3  # bucket to tolerate small jitter
            if current_top is None or top == current_top:
                current_line.append(w["text"])
                current_top = top
            else:
                lines.append(" ".join(current_line))
                current_line = [w["text"]]
                current_top = top
        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)

    reflowed = _to_lines(left_words) + "\n" + _to_lines(right_words)
    return reflowed if len(reflowed.strip()) > len(fallback_text.strip()) * 0.5 else fallback_text


def _ocr_pdf_page(file_bytes: bytes, page_number: int) -> str:
    """OCR a single PDF page. Requires `pdf2image` (needs poppler) and
    `pytesseract` (needs the tesseract binary) to be installed on the host.
    If either is missing, this returns "" and the page is simply recorded
    with empty/partial text rather than crashing the whole ingestion job --
    Section 5 asks for OCR "where practical", not as a hard requirement.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        logger.info("ocr_skipped_dependencies_missing", extra={"extra_fields": {"page": page_number}})
        return ""

    try:
        images = convert_from_bytes(file_bytes, first_page=page_number, last_page=page_number, dpi=200)
        if not images:
            return ""
        return pytesseract.image_to_string(images[0]) or ""
    except Exception as exc:
        logger.warning("ocr_failed", extra={"extra_fields": {"page": page_number, "error": str(exc)}})
        return ""
