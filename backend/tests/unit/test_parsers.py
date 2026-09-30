from __future__ import annotations

import io
from types import SimpleNamespace

import docx
from PIL import Image, ImageDraw
import pytest

from app.core.exceptions import ProcessingError
from app.ingestion.parsers import DOCX_MIME, PDF_MIME, TXT_MIME, parse_document


def _mock_pdf(monkeypatch, pages):
    import pdfplumber

    class FakePdf:
        def __enter__(self):
            return SimpleNamespace(pages=pages)

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(pdfplumber, "open", lambda _file: FakePdf())


def _make_pdf(objects: list[tuple[int, bytes]]) -> bytes:
    output = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for number, body in objects:
        offsets[number] = len(output)
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    highest = max(offsets)
    output.extend(f"xref\n0 {highest + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for number in range(1, highest + 1):
        output.extend(f"{offsets[number]:010d} 00000 n \n".encode() if number in offsets else b"0000000000 00000 f \n")
    output.extend(f"trailer\n<< /Size {highest + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(output)


def _text_pdf() -> bytes:
    content = b"BT /F1 12 Tf 20 70 Td (Actual PDF fixture with Python and SQL.) Tj ET"
    return _make_pdf(
        [
            (1, b"<< /Type /Catalog /Pages 2 0 R >>"),
            (2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            (
                3,
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 100] "
                b"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> "
                b"/Contents 4 0 R >>",
            ),
            (4, f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"),
        ]
    )


def _scanned_pdf() -> bytes:
    image = Image.new("RGB", (600, 120), "white")
    ImageDraw.Draw(image).text((20, 40), "Scanned resume image", fill="black")
    jpeg = io.BytesIO()
    image.save(jpeg, format="JPEG")
    image_bytes = jpeg.getvalue()
    content = b"q 600 0 0 120 0 0 cm /Im1 Do Q"
    return _make_pdf(
        [
            (1, b"<< /Type /Catalog /Pages 2 0 R >>"),
            (2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
            (
                3,
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 120] "
                b"/Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R >>",
            ),
            (4, f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"),
            (
                5,
                f"<< /Type /XObject /Subtype /Image /Width 600 /Height 120 /ColorSpace /DeviceRGB "
                f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(image_bytes)} >>\nstream\n".encode()
                + image_bytes
                + b"\nendstream",
            ),
        ]
    )


def test_txt_parser_preserves_text_and_page():
    parsed = parse_document(b"Jane Doe\nPython engineer", TXT_MIME, "resume.txt")
    assert parsed.full_text == "Jane Doe\nPython engineer"
    assert parsed.pages[0].page_number == 1
    assert parsed.pages[0].used_ocr is False


def test_docx_parser_includes_table_cells():
    document = docx.Document()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Python"
    table.cell(0, 1).text = "SQL"
    buffer = io.BytesIO()
    document.save(buffer)
    parsed = parse_document(buffer.getvalue(), DOCX_MIME, "resume.docx")
    assert "Python | SQL" in parsed.full_text


def test_malformed_docx_is_rejected():
    with pytest.raises(ProcessingError):
        parse_document(b"not a docx archive", DOCX_MIME, "broken.docx")


def test_malformed_pdf_is_rejected():
    with pytest.raises(ProcessingError):
        parse_document(b"not a pdf", PDF_MIME, "broken.pdf")


def test_scanned_pdf_page_is_marked_as_ocr(monkeypatch):
    page = SimpleNamespace(extract_text=lambda: "", extract_words=lambda: [], width=600)
    _mock_pdf(monkeypatch, [page])
    monkeypatch.setattr("app.ingestion.parsers._ocr_pdf_page", lambda _data, _page: "OCR extracted resume content.")

    parsed = parse_document(b"pdf bytes", PDF_MIME, "scan.pdf")
    assert parsed.used_ocr is True
    assert parsed.extraction_method == "pdf_ocr"
    assert parsed.pages[0].used_ocr is True
    assert parsed.pages[0].page_number == 1


def test_real_text_pdf_extracts_without_ocr(monkeypatch):
    monkeypatch.setattr("app.ingestion.parsers._ocr_pdf_page", lambda *_args: pytest.fail("OCR should not run"))
    parsed = parse_document(_text_pdf(), PDF_MIME, "actual-text.pdf")
    assert "Python and SQL" in parsed.full_text
    assert parsed.pages[0].used_ocr is False


def test_real_scanned_pdf_runs_ocr_and_marks_source_page(monkeypatch):
    monkeypatch.setattr("app.ingestion.parsers._ocr_pdf_page", lambda _data, page: f"OCR page {page}: Python resume content.")
    parsed = parse_document(_scanned_pdf(), PDF_MIME, "actual-scan.pdf")
    assert parsed.full_text.startswith("OCR page 1:")
    assert parsed.used_ocr is True
    assert parsed.pages[0].used_ocr is True
    assert parsed.pages[0].page_number == 1


def test_text_pdf_page_is_not_marked_as_ocr(monkeypatch):
    text = "A digitally searchable resume page with enough normal text content."
    page = SimpleNamespace(extract_text=lambda: text, extract_words=lambda: [], width=600)
    _mock_pdf(monkeypatch, [page])
    monkeypatch.setattr("app.ingestion.parsers._ocr_pdf_page", lambda *_args: pytest.fail("OCR should not run"))

    parsed = parse_document(b"pdf bytes", PDF_MIME, "text.pdf")
    assert parsed.pages[0].used_ocr is False


def test_two_column_reflow_reads_left_then_right(monkeypatch):
    words = []
    for i in range(10):
        words.append({"x0": 40, "top": i * 12, "text": f"LEFT{i}"})
        words.append({"x0": 340, "top": i * 12, "text": f"RIGHT{i}"})
    page = SimpleNamespace(
        extract_text=lambda: "Default interleaved two-column text extraction with enough characters.",
        extract_words=lambda: words,
        width=600,
    )
    _mock_pdf(monkeypatch, [page])
    monkeypatch.setattr("app.ingestion.parsers._ocr_pdf_page", lambda *_args: pytest.fail("OCR should not run"))

    parsed = parse_document(b"pdf bytes", PDF_MIME, "columns.pdf")
    assert parsed.full_text.index("LEFT9") < parsed.full_text.index("RIGHT0")
