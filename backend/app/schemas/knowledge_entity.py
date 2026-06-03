"""KnowledgeEntity Pydantic schemas — request/response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeEntityCreateRequest(BaseModel):
    """Schema for creating a new knowledge entity."""

    name: str = Field(max_length=500)
    entity_type: str = Field(max_length=100)
    description: str | None = None
    source_doc_ids: list[str] | None = None
    metadata_: dict | None = Field(default=None, alias="metadata")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class KnowledgeEntityResponse(BaseModel):
    """Schema for returning a knowledge entity in API responses."""

    id: str
    user_id: str
    name: str
    entity_type: str
    description: str | None
    source_doc_ids: list[str] | None
    metadata_: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
