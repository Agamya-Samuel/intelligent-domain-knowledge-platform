"""
Document chunker — splits parsed text into retrieval-ready segments.

Supports:
  - Fixed-size character chunking with overlap
  - Paragraph-aware chunking (splits on double newlines first)
  - Token count estimation (approx. 1 token ≈ 4 characters)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.services.document_parser import ParsedDocument

# ── Default chunking parameters ───────────────────────────────────

DEFAULT_CHUNK_SIZE: int = 1000  # characters
DEFAULT_CHUNK_OVERLAP: int = 200  # characters overlap between chunks
MIN_CHUNK_SIZE: int = 100  # minimum useful chunk size
CHARS_PER_TOKEN: int = 4  # rough approximation


@dataclass
class TextChunk:
    """A single text segment ready for embedding."""

    index: int
    content: str
    token_count: int
    content_hash: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(cls, index: int, content: str, metadata: dict | None = None) -> TextChunk:
        """Create a TextChunk with auto-computed hash and token count."""
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        token_count = max(1, len(content) // CHARS_PER_TOKEN)
        return cls(
            index=index,
            content=content,
            token_count=token_count,
            content_hash=content_hash,
            metadata=metadata or {},
        )


def _split_by_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (separated by double newlines or more)."""
    # Split on 2+ newlines
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _split_by_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Split on sentence-ending punctuation followed by space or newline
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _merge_small_chunks(
    segments: list[str],
    min_size: int = MIN_CHUNK_SIZE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> list[str]:
    """
    Merge segments that are too small with adjacent ones.

    Small segments are joined together up to the target chunk_size.
    """
    if not segments:
        return []

    merged: list[str] = []
    buffer: list[str] = []
    buffer_len: int = 0

    for segment in segments:
        # If buffer + segment fits within chunk_size, add to buffer
        if buffer_len + len(segment) + 1 <= chunk_size or not buffer:
            buffer.append(segment)
            buffer_len += len(segment) + 1  # +1 for space
        else:
            # Flush buffer
            if buffer:
                merged.append(" ".join(buffer))
            # Start new buffer with this segment
            buffer = [segment]
            buffer_len = len(segment) + 1

    # Flush remaining buffer
    if buffer:
        merged.append(" ".join(buffer))

    return merged


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Add overlapping text from the end of the previous chunk."""
    if not chunks or overlap <= 0:
        return chunks

    overlapped: list[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        # Take the tail of the previous chunk as prefix
        prev_tail = overlapped[-1][-overlap:] if len(overlapped[-1]) > overlap else overlapped[-1]
        overlapped.append(prev_tail + chunks[i])
    return overlapped


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """
    Split text into chunks suitable for embedding and retrieval.

    Strategy:
      1. Split text by paragraphs
      2. For paragraphs larger than chunk_size, split by sentences
      3. Merge small segments into chunks up to chunk_size
      4. Add overlap between consecutive chunks

    Args:
        text: The full text to chunk.
        chunk_size: Maximum characters per chunk (default 1000).
        chunk_overlap: Character overlap between consecutive chunks (default 200).

    Returns:
        List of TextChunk objects with content, hash, and token count.
    """
    if not text.strip():
        return []

    # Step 1: Split by paragraphs
    paragraphs = _split_by_paragraphs(text)
    segments: list[str] = []

    for para in paragraphs:
        if len(para) <= chunk_size:
            segments.append(para)
        else:
            # Paragraph is too large — split by sentences and merge
            sentences = _split_by_sentences(para)
            segments.extend(
                _merge_small_chunks(sentences, min_size=MIN_CHUNK_SIZE, chunk_size=chunk_size)
            )

    # Step 2: Merge any remaining small segments
    segments = _merge_small_chunks(segments, min_size=MIN_CHUNK_SIZE // 2, chunk_size=chunk_size)

    # Step 3: Add overlap
    segments = _add_overlap(segments, chunk_overlap)

    # Step 4: Create TextChunk objects
    chunks: list[TextChunk] = []
    for i, content in enumerate(segments):
        chunks.append(TextChunk.create(index=i, content=content))

    return chunks


def chunk_document(
    parsed: ParsedDocument,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """
    Chunk a parsed document into text segments.

    Adds page number metadata to chunks when available (PDF documents).

    Args:
        parsed: A ParsedDocument from the document parser.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Character overlap between chunks.

    Returns:
        List of TextChunk objects.
    """
    chunks = chunk_text(parsed.text, chunk_size, chunk_overlap)

    # Enrich chunks with document-level metadata
    for chunk in chunks:
        chunk.metadata = {
            "source_page_count": parsed.page_count,
            **parsed.metadata,
        }

    return chunks
