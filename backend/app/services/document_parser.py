"""
Document parser — extracts raw text from uploaded files.

Supports: PDF, plain text, Markdown, DOCX.
Each parser returns the extracted text content as a string.
"""

import io
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

# ── Supported file extensions ─────────────────────────────────────

SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".txt", ".md", ".docx"}

# ── File extension → MIME type mapping ───────────────────────────

EXTENSION_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass(frozen=True)
class ParsedDocument:
    """Result of parsing a document file."""

    text: str
    page_count: int
    metadata: dict = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


class DocumentParseError(Exception):
    """Raised when document parsing fails."""

    def __init__(self, file_name: str, reason: str) -> None:
        self.file_name = file_name
        self.reason = reason
        super().__init__(f"Failed to parse {file_name}: {reason}")


def get_file_extension(file_name: str) -> str:
    """Extract and normalize the file extension."""
    return Path(file_name).suffix.lower()


def validate_file_type(file_name: str) -> str:
    """
    Validate that the file type is supported.

    Returns the normalized extension (e.g. '.pdf').
    Raises DocumentParseError for unsupported types.
    """
    ext = get_file_extension(file_name)
    if ext not in SUPPORTED_EXTENSIONS:
        raise DocumentParseError(
            file_name,
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )
    return ext


# ── PDF Parser ────────────────────────────────────────────────────


def _parse_pdf(file_bytes: bytes, file_name: str) -> ParsedDocument:
    """Extract text from a PDF file using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages: list[str] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                # Clean up excessive whitespace
                text = re.sub(r"\s+", " ", text).strip()
                pages.append(text)

        full_text = "\n\n".join(pages)
        return ParsedDocument(
            text=full_text,
            page_count=len(reader.pages),
            metadata={"total_pages": len(reader.pages)},
        )
    except Exception as exc:
        raise DocumentParseError(file_name, f"PDF parsing error: {exc}") from exc


# ── Plain Text / Markdown Parser ───────────────────────────────


def _parse_text(file_bytes: bytes, file_name: str) -> ParsedDocument:
    """Read a plain text or Markdown file."""
    try:
        # Try UTF-8 first, fall back to latin-1
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")

        # Normalize line endings and clean up
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

        # Count approximate "pages" based on line count (3000 chars per page)
        page_count = max(1, len(text) // 3000)
        return ParsedDocument(
            text=text,
            page_count=page_count,
            metadata={"encoding": "utf-8"},
        )
    except Exception as exc:
        raise DocumentParseError(file_name, f"Text parsing error: {exc}") from exc


# ── DOCX Parser ─────────────────────────────────────────────────


def _parse_docx(file_bytes: bytes, file_name: str) -> ParsedDocument:
    """Extract text from a DOCX file using python-docx."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(file_bytes))
        paragraphs: list[str] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)

        full_text = "\n\n".join(paragraphs)

        # Extract table text as well
        table_texts: list[str] = []
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                row_text = " | ".join(cells)
                if any(cells):
                    table_texts.append(row_text)

        if table_texts:
            full_text += "\n\n--- Tables ---\n" + "\n".join(table_texts)

        page_count = max(1, len(paragraphs) // 20)
        return ParsedDocument(
            text=full_text,
            page_count=page_count,
            metadata={"paragraph_count": len(doc.paragraphs), "table_count": len(doc.tables)},
        )
    except ImportError:
        raise DocumentParseError(
            file_name,
            "python-docx not installed. Run: uv add python-docx",
        )
    except Exception as exc:
        raise DocumentParseError(file_name, f"DOCX parsing error: {exc}") from exc


# ── Main Parser Dispatcher ─────────────────────────────────────


def parse_document(file_bytes: bytes, file_name: str) -> ParsedDocument:
    """
    Parse a document file and return extracted text.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        file_name: Original file name (used to determine file type).

    Returns:
        ParsedDocument with extracted text and metadata.

    Raises:
        DocumentParseError: If the file type is unsupported or parsing fails.
    """
    ext = validate_file_type(file_name)

    parsers = {
        ".pdf": _parse_pdf,
        ".txt": _parse_text,
        ".md": _parse_text,
        ".docx": _parse_docx,
    }

    parser = parsers[ext]
    return parser(file_bytes, file_name)
