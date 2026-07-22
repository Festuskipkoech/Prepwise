import io
import logging
from typing import Literal

import pypdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)

SupportedFileType = Literal["pdf", "docx"]

def _extract_pdf(data: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)

def _extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    parts = []
    for block in doc.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                parts.append(text)
        elif isinstance(block, Table):
            for row in block.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append("  |  ".join(cells))
    return "\n\n".join(parts)

def detect_file_type(filename: str, content_type: str) -> SupportedFileType:
    lower = filename.lower()
    if lower.endswith(".pdf") or content_type == "application/pdf":
        return "pdf"
    if lower.endswith(".docx") or content_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return "docx"
    raise ValueError(
        f"Unsupported file type: {filename!r} ({content_type}). "
        "Only PDF and DOCX files are supported."
    )

def extract_text(data: bytes, file_type: SupportedFileType) -> str:
    if file_type == "pdf":
        text = _extract_pdf(data)
    elif file_type == "docx":
        text = _extract_docx(data)
    else:
        raise ValueError(f"Unsupported file type: {file_type!r}")

    text = text.strip()
    if not text:
        raise ValueError(
            "No text could be extracted from the uploaded file. "
            "Please ensure the file is not empty or image-only."
        )
    logger.debug("Extracted %d characters from %s file", len(text), file_type)
    return text