"""Document Pydantic schemas — request/response models for the Document model."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatus(StrEnum):
    """Document processing lifecycle statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCreateResponse(BaseModel):
    """Schema returned immediately after document upload."""

    id: str
    user_id: str
    title: str
    file_name: str
    file_type: str
    file_size: int
    status: DocumentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """Schema for listing documents (summary view)."""

    id: str
    title: str
    file_name: str
    file_type: str
    file_size: int
    status: DocumentStatus
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(BaseModel):
    """Schema for a single document with full metadata."""

    id: str
    user_id: str
    title: str
    description: str | None
    file_name: str
    file_type: str
    file_size: int
    s3_key: str | None
    status: DocumentStatus
    processing_error: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdateRequest(BaseModel):
    """Schema for updating document metadata."""

    title: str | None = Field(default=None, max_length=500)
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class DocumentProcessResponse(BaseModel):
    """Schema returned after triggering document processing."""

    id: str
    status: DocumentStatus
    chunk_count: int
    message: str

    model_config = ConfigDict(from_attributes=True)
