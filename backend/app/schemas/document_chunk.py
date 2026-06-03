"""DocumentChunk Pydantic schemas — request/response models for the DocumentChunk model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentChunkResponse(BaseModel):
    """Schema for returning a document chunk in API responses."""

    id: str
    document_id: str
    chunk_index: int
    content: str
    token_count: int
    metadata_: dict

    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
