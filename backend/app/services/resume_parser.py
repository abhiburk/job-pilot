
from io import BytesIO

from docx import Document
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5 MB


def extract_resume_text(
    filename: str,
    content: bytes,
) -> str:
    """Extract text from a PDF or DOCX resume."""

    if not content:
        raise ValueError("The uploaded resume is empty")

    if len(content) > MAX_RESUME_SIZE:
        raise ValueError("Resume must not exceed 5 MB")

    extension = "." + filename.rsplit(".", 1)[-1].lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only PDF and DOCX resumes are supported")

    if extension == ".pdf":
        reader = PdfReader(BytesIO(content))

        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported")

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    else:
        document = Document(BytesIO(content))
        paragraphs = [
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]
        text = "\n".join(paragraphs)

    text = text.strip()

    if not text:
        raise ValueError(
            "No readable text found. The resume may be scanned or image-based."
        )

    return text
