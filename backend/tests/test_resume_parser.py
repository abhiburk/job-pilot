
from io import BytesIO

import pytest
from docx import Document
from docx.shared import Inches
from pypdf import PdfWriter

from backend.app.services.resume_parser import extract_resume_text


def make_docx(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def make_pdf() -> bytes:
    # Create a valid blank PDF. The parser should reject it
    # because it contains no extractable text.
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_extract_text_from_docx():
    content = make_docx("Python developer with FastAPI experience")

    text = extract_resume_text("resume.docx", content)

    assert "Python developer" in text
    assert "FastAPI" in text


def test_reject_empty_file():
    with pytest.raises(ValueError, match="empty"):
        extract_resume_text("resume.pdf", b"")


def test_reject_unsupported_extension():
    with pytest.raises(ValueError, match="Only PDF and DOCX"):
        extract_resume_text("resume.txt", b"some text")


def test_reject_file_over_5mb():
    content = b"x" * (5 * 1024 * 1024 + 1)

    with pytest.raises(ValueError, match="5 MB"):
        extract_resume_text("resume.pdf", content)


def test_reject_pdf_without_extractable_text():
    with pytest.raises(ValueError, match="No readable text"):
        extract_resume_text("resume.pdf", make_pdf())
