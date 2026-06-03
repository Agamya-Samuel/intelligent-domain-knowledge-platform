"""
Document endpoints — upload, list, detail, update, delete, process, chunks.

All endpoints require authentication (except future public ones).
Documents are scoped to the authenticated user.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.schemas.document import (
    DocumentCreateResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentProcessResponse,
    DocumentUpdateRequest,
)
from app.schemas.document_chunk import DocumentChunkResponse
from app.services.document_parser import DocumentParseError
from app.services.document_service import (
    create_document_record,
    delete_document,
    get_document,
    get_document_chunks,
    list_documents,
    process_document,
    update_document,
    validate_upload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


# ── Upload ───────────────────────────────────────────────────────


@router.post(
    "/upload",
    response_model=DocumentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new document",
    description=(
        "Upload a document file (PDF, TXT, MD, DOCX). "
        "The document is stored with status='pending' until processing is triggered."
    ),
)
async def upload_document(
    file: UploadFile = File(..., description="Document file (PDF, TXT, MD, DOCX)"),
    description: str | None = Query(default=None, description="Optional document description"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentCreateResponse:
    """Upload a new document and create a database record."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload",
        )

    # Read file bytes
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Validate upload constraints
    try:
        await validate_upload(file.filename, file_size)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Derive title from filename (strip extension)
    title = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename

    # Create database record
    doc = await create_document_record(
        db,
        user_id=user.user_id,
        title=title,
        file_name=file.filename,
        file_size=file_size,
        description=description,
    )

    logger.info("Document uploaded: %s (%s, %d bytes)", doc.id, doc.file_name, doc.file_size)
    return doc


# ── List ─────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[DocumentListResponse],
    summary="List user's documents",
    description="List all documents for the authenticated user with pagination.",
)
async def list_user_documents(
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    doc_status: str | None = Query(default=None, alias="status", description="Filter by status"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentListResponse]:
    """List documents for the authenticated user."""
    documents, _ = await list_documents(
        db,
        user.user_id,
        offset=offset,
        limit=limit,
        status=doc_status,
    )
    return documents


# ── Detail ────────────────────────────────────────────────────────


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details",
    description="Get full metadata for a specific document.",
)
async def get_document_detail(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """Retrieve a single document by ID."""
    doc = await get_document(db, document_id, user.user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )
    return doc


# ── Update ───────────────────────────────────────────────────────


@router.patch(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Update document metadata",
    description="Update title and/or description of a document.",
)
async def update_document_metadata(
    document_id: str,
    body: DocumentUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """Update document metadata."""
    doc = await get_document(db, document_id, user.user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    updated = await update_document(
        db,
        doc,
        title=body.title,
        description=body.description,
    )
    return updated


# ── Delete ────────────────────────────────────────────────────────


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
    description="Delete a document and all its associated chunks.",
)
async def delete_user_document(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a document by ID."""
    doc = await get_document(db, document_id, user.user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    await delete_document(db, doc)
    logger.info("Document deleted: %s", document_id)


# ── Process ───────────────────────────────────────────────────────


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    summary="Process a document",
    description=(
        "Trigger document processing: parse, chunk, and persist text segments. "
        "The document must be in 'pending' or 'failed' status."
    ),
)
async def trigger_document_processing(
    document_id: str,
    file: UploadFile = File(..., description="Document file content for processing"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentProcessResponse:
    """
    Trigger document processing.

    The uploaded file content is parsed, chunked, and stored as DocumentChunk records.
    """
    doc = await get_document(db, document_id, user.user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    # Read file bytes
    file_bytes = await file.read()

    try:
        processed_doc = await process_document(db, doc, file_bytes)
        return DocumentProcessResponse(
            id=processed_doc.id,
            status=processed_doc.status,  # type: ignore[arg-type]
            chunk_count=processed_doc.chunk_count,
            message=f"Successfully processed into {processed_doc.chunk_count} chunks",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DocumentParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ── Chunks ────────────────────────────────────────────────────────


@router.get(
    "/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
    summary="Get document chunks",
    description="Retrieve text chunks for a processed document.",
)
async def get_chunks(
    document_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentChunkResponse]:
    """Get text chunks for a document."""
    doc = await get_document(db, document_id, user.user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    chunks = await get_document_chunks(db, document_id, user.user_id, offset=offset, limit=limit)
    return chunks
