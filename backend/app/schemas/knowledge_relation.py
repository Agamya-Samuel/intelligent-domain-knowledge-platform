"""KnowledgeRelation Pydantic schemas — request/response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeRelationCreateRequest(BaseModel):
    """Schema for creating a new knowledge relation."""

    source_entity_id: str
    target_entity_id: str
    relation_type: str = Field(max_length=100)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    source_document_id: str | None = None
    metadata_: dict | None = Field(default=None, alias="metadata")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class KnowledgeRelationResponse(BaseModel):
    """Schema for returning a knowledge relation in API responses."""

    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    weight: float
    source_document_id: str | None
    metadata_: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
