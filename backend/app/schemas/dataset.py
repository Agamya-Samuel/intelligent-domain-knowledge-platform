"""Dataset Pydantic schemas — request/response models for dataset management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Request Schemas ─────────────────────────────────────────────────


class DatasetCreateRequest(BaseModel):
    """POST /api/datasets — create a new dataset."""

    name: str = Field(..., min_length=1, max_length=255, description="Dataset name")
    description: str | None = Field(None, max_length=5000, description="Optional description")


class DatasetArchiveRequest(BaseModel):
    """POST /api/datasets/{id}/archive — soft-delete a dataset."""

    pass  # No body required; the endpoint uses the path param


# ── Response Schemas ────────────────────────────────────────────────


class DatasetResponse(BaseModel):
    """Summary view of a dataset (list and create response)."""

    id: str
    name: str
    description: str | None = None
    version: int
    status: str
    source_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetSourceResponse(BaseModel):
    """Metadata for a single dataset source."""

    id: str
    dataset_id: str
    dataset_version: int
    source_type: str
    source_path: str
    file_name: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    content_hash: str | None = None
    processed: bool = False
    processing_error: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetSourceCreateResponse(BaseModel):
    """Response after adding a source to a dataset."""

    source_id: str
    dataset_version: int
    file_name: str | None = None
    status: str = "processing"


class DatasetVersionResponse(BaseModel):
    """Version history entry."""

    id: str
    dataset_id: str
    version: int
    change_description: str | None = None
    source_count: int | None = None
    sources_added: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetDetailResponse(BaseModel):
    """Full dataset detail with sources and version history."""

    id: str
    name: str
    description: str | None = None
    version: int
    status: str
    domain_tags: list[str] | None = None
    sources: list[DatasetSourceResponse] = []
    version_history: list[DatasetVersionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
