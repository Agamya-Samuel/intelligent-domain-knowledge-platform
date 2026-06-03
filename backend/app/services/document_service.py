"""
Document service — CRUD operations and processing orchestration.

Handles the full document lifecycle:
  1. Upload validation
  2. Document parsing (via document_parser)
  3. Text chunking (via document_chunker)
  4. Chunk persistence to PostgreSQL
  5. Status management
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import generate_uuid
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.document_chunker import chunk_document
from app.services.document_parser import (
    DocumentParseError,
    get_file_extension,
    parse_document,
    validate_file_type,
)

logger = logging.getLogger(__name__)


# ── Upload Validation ────────────────────────────────────────────


async def validate_upload(
    file_name: str,
    file_size: int,
    max_size_mb: int = 50,
) -> None:
    """
    Validate file upload constraints.

    Args:
        file_name: Original file name.
        file_size: File size in bytes.
        max_size_mb: Maximum allowed file size in megabytes.

    Raises:
        ValueError: If validation fails.
    """
    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise ValueError(f"File too large: {file_size} bytes. Maximum allowed: {max_size_mb}MB")

    if file_size == 0:
        raise ValueError("Empty file uploaded")

    validate_file_type(file_name)


# ── Document CRUD ─────────────────────────────────────────────────


async def create_document_record(
    db: AsyncSession,
    *,
    user_id: str,
    title: str,
    file_name: str,
    file_size: int,
    description: str | None = None,
) -> Document:
    """
    Create a new document record in the database.

    The document starts with status='pending' until processing is triggered.
    """
    file_type = get_file_extension(file_name).lstrip(".")

    doc = Document(
        id=generate_uuid(),
        user_id=user_id,
        title=title,
        file_name=file_name,
        file_type=file_type,
        file_size=file_size,
        description=description,
        status="pending",
        chunk_count=0,
    )
    db.add(doc)
    await db.flush()
    return doc


async def get_document(
    db: AsyncSession,
    document_id: str,
    user_id: str,
) -> Document | None:
    """Fetch a single document by ID, scoped to a specific user."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_documents(
    db: AsyncSession,
    user_id: str,
    *,
    offset: int = 0,
    limit: int = 20,
    status: str | None = None,
) -> tuple[list[Document], int]:
    """
    List documents for a user with pagination and optional status filter.

    Returns:
        Tuple of (documents, total_count).
    """
    # Base query with count
    count_stmt = select(Document).where(Document.user_id == user_id)
    data_stmt = select(Document).where(Document.user_id == user_id)

    if status:
        count_stmt = count_stmt.where(Document.status == status)
        data_stmt = data_stmt.where(Document.status == status)

    # Get total count
    from sqlalchemy import func

    count_query = select(func.count()).select_from(count_stmt.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Get paginated results
    data_stmt = data_stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(data_stmt)
    documents = list(result.scalars().all())

    return documents, total


async def update_document(
    db: AsyncSession,
    document: Document,
    *,
    title: str | None = None,
    description: str | None = None,
) -> Document:
    """Update document metadata fields."""
    if title is not None:
        document.title = title
    if description is not None:
        document.description = description

    await db.flush()
    return document


async def delete_document(
    db: AsyncSession,
    document: Document,
) -> None:
    """
    Delete a document and all its chunks.

    Chunks are cascade-deleted via the FK relationship.
    """
    await db.delete(document)
    await db.flush()


# ── Document Processing ──────────────────────────────────────────


async def process_document(
    db: AsyncSession,
    document: Document,
    file_bytes: bytes,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Document:
    """
    Process an uploaded document: parse, chunk, and persist chunks.

    Lifecycle transition: pending → processing → completed
                                  processing → failed (on error)

    Args:
        db: Async database session.
        document: The document ORM record (must have status='pending').
        file_bytes: Raw file bytes.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        The updated document record.

    Raises:
        ValueError: If document is not in 'pending' status.
        DocumentParseError: If parsing fails.
    """
    if document.status not in ("pending", "failed"):
        raise ValueError(
            f"Cannot process document in '{document.status}' status. Must be 'pending' or 'failed'."
        )

    # Mark as processing
    document.status = "processing"
    document.processing_error = None
    await db.flush()

    try:
        # Step 1: Parse the document
        logger.info(
            "Parsing document %s (%s, %d bytes)",
            document.id,
            document.file_name,
            len(file_bytes),
        )
        parsed = parse_document(file_bytes, document.file_name)

        if not parsed.text.strip():
            raise DocumentParseError(
                document.file_name,
                "Document contains no extractable text content",
            )

        # Step 2: Chunk the text
        logger.info(
            "Chunking document %s (chars=%d, pages=%d)",
            document.id,
            len(parsed.text),
            parsed.page_count,
        )
        chunks = chunk_document(parsed, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        if not chunks:
            raise DocumentParseError(
                document.file_name,
                "Text chunking produced no chunks",
            )

        # Step 3: Delete existing chunks (if reprocessing)
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

        # Step 4: Persist new chunks
        for chunk in chunks:
            db_chunk = DocumentChunk(
                id=generate_uuid(),
                document_id=document.id,
                chunk_index=chunk.index,
                content=chunk.content,
                content_hash=chunk.content_hash,
                token_count=chunk.token_count,
                metadata_=chunk.metadata,
            )
            db.add(db_chunk)

        # Step 5: Update document status
        document.status = "completed"
        document.chunk_count = len(chunks)
        document.processing_error = None

        await db.flush()

        logger.info(
            "Document %s processed successfully: %d chunks created",
            document.id,
            len(chunks),
        )

        return document

    except DocumentParseError:
        document.status = "failed"
        document.processing_error = f"Parse error: {document.file_name} — parsing failed"
        await db.flush()
        raise

    except Exception as exc:
        document.status = "failed"
        document.processing_error = f"Processing error: {exc}"
        await db.flush()
        logger.exception("Failed to process document %s", document.id)
        raise


async def get_document_chunks(
    db: AsyncSession,
    document_id: str,
    user_id: str,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[DocumentChunk]:
    """
    Get chunks for a document, scoped to the document owner.

    Includes a user_id check via the document relationship for authorization.
    """
    # First verify the document belongs to the user
    doc_check = select(Document.id).where(
        Document.id == document_id,
        Document.user_id == user_id,
    )
    doc_result = await db.execute(doc_check)
    if not doc_result.scalar_one_or_none():
        return []

    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
