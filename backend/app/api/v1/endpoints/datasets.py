"""Dataset CRUD endpoints — manage versioned datasets and their sources.

GET  /api/v1/datasets              — list user's datasets
POST /api/v1/datasets              — create a new dataset
GET  /api/v1/datasets/{id}         — get dataset detail with sources
PATCH /api/v1/datasets/{id}        — update dataset metadata
POST /api/v1/datasets/{id}/archive — soft-archive a dataset
POST /api/v1/datasets/{id}/sources — add a source (upload/text/s3/url)
GET  /api/v1/datasets/{id}/sources — list dataset sources
DELETE /api/v1/datasets/{id}/sources/{source_id} — remove a source
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.schemas.dataset import (
    DatasetCreateRequest,
    DatasetDetailResponse,
    DatasetResponse,
    DatasetSourceCreateResponse,
    DatasetSourceResponse,
)
from app.services.dataset_service import (
    add_source,
    archive_dataset,
    compute_content_hash,
    create_dataset,
    delete_source,
    get_dataset,
    list_datasets,
    list_sources,
    update_dataset,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


# ── List ─────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[DatasetResponse],
    summary="List user's datasets",
)
async def list_user_datasets(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ds_status: str | None = Query(default=None, alias="status"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DatasetResponse]:
    """List all datasets for the authenticated user."""
    datasets, _ = await list_datasets(
        db, user.user_id, status_filter=ds_status, offset=offset, limit=limit
    )
    # Compute source count for each dataset
    result = []
    for ds in datasets:
        ds_dict = DatasetResponse.model_validate(ds).model_dump()
        ds_dict["source_count"] = len(ds.sources) if ds.sources else 0
        result.append(DatasetResponse(**ds_dict))
    return result


# ── Create ───────────────────────────────────────────────────────


@router.post(
    "",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new dataset",
)
async def create_user_dataset(
    body: DatasetCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    """Create a new versioned dataset for fine-tuning."""
    ds = await create_dataset(
        db,
        user_id=user.user_id,
        name=body.name,
        description=body.description,
    )
    return DatasetResponse.model_validate(ds)


# ── Detail ───────────────────────────────────────────────────────


@router.get(
    "/{dataset_id}",
    response_model=DatasetDetailResponse,
    summary="Get dataset details",
)
async def get_dataset_detail(
    dataset_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetDetailResponse:
    """Get full dataset detail with sources and version history."""
    ds = await get_dataset(db, dataset_id, user.user_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found",
        )
    return DatasetDetailResponse.model_validate(ds)


# ── Update ───────────────────────────────────────────────────────


class DatasetUpdateRequest(BaseModel):
    """PATCH /api/v1/datasets/{id} — update body."""

    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=5000)
    domain_tags: list[str] | None = None


@router.patch(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Update dataset metadata",
)
async def update_dataset_metadata(
    dataset_id: str,
    body: DatasetUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    """Update dataset name, description, or domain tags."""
    ds = await get_dataset(db, dataset_id, user.user_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found",
        )
    updated = await update_dataset(
        db,
        ds,
        name=body.name,
        description=body.description,
        domain_tags=body.domain_tags,
    )
    return DatasetResponse.model_validate(updated)


# ── Archive ───────────────────────────────────────────────────────


@router.post(
    "/{dataset_id}/archive",
    response_model=DatasetResponse,
    summary="Archive a dataset",
    description="Soft-archive a dataset. No hard delete allowed per project constraints.",
)
async def archive_user_dataset(
    dataset_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    """Archive a dataset (soft-delete)."""
    ds = await get_dataset(db, dataset_id, user.user_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found",
        )
    archived = await archive_dataset(db, ds)
    return DatasetResponse.model_validate(archived)


# ── Sources: Add ──────────────────────────────────────────────────


@router.post(
    "/{dataset_id}/sources",
    response_model=DatasetSourceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a source to a dataset",
)
async def add_dataset_source(
    dataset_id: str,
    file: UploadFile | None = File(default=None),
    source_type: str | None = None,
    source_path: str | None = None,
    text_content: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetSourceCreateResponse:
    """
    Add a source to a dataset. Supports:
      - upload: Provide a file (multipart/form-data)
      - text: Provide text_content parameter
      - s3: Provide source_type='s3' and source_path
      - url: Provide source_type='url' and source_path
    """
    ds = await get_dataset(db, dataset_id, user.user_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found",
        )
    if ds.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add sources to an archived dataset",
        )

    # Determine source type and build metadata
    stype: str
    spath: str
    fname: str | None = None
    fsize: int | None = None
    content_hash: str | None = None

    if file and file.filename:
        stype = "upload"
        file_bytes = await file.read()
        fsize = len(file_bytes)
        spath = f"uploads/{dataset_id}/{file.filename}"
        fname = file.filename
        content_hash = compute_content_hash(file_bytes)
    elif text_content:
        stype = "text"
        spath = f"text/{dataset_id}/{compute_content_hash(text_content.encode())[:12]}"
        fname = None
        fsize = len(text_content.encode())
        content_hash = compute_content_hash(text_content.encode())
    elif source_type in ("s3", "url") and source_path:
        stype = source_type
        spath = source_path
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a file, text_content, or source_type+source_path",
        )

    try:
        source = await add_source(
            db,
            ds,
            source_type=stype,
            source_path=spath,
            file_name=fname,
            file_size=fsize,
            content_hash=content_hash,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return DatasetSourceCreateResponse(
        source_id=source.id,
        dataset_version=ds.version,
        file_name=fname,
        status="processing",
    )


# ── Sources: List ────────────────────────────────────────────────


@router.get(
    "/{dataset_id}/sources",
    response_model=list[DatasetSourceResponse],
    summary="List dataset sources",
)
async def list_dataset_sources(
    dataset_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DatasetSourceResponse]:
    """List all sources in a dataset."""
    ds = await get_dataset(db, dataset_id, user.user_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found",
        )
    sources = await list_sources(db, dataset_id, offset=offset, limit=limit)
    return [DatasetSourceResponse.model_validate(s) for s in sources]


# ── Sources: Remove ─────────────────────────────────────────────


@router.delete(
    "/{dataset_id}/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a source from a dataset",
)
async def remove_dataset_source(
    dataset_id: str,
    source_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a source from a dataset."""
    ds = await get_dataset(db, dataset_id, user.user_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found",
        )
    try:
        await delete_source(db, ds, source_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
