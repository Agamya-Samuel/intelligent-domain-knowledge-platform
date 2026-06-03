"""Comparison and staleness Pydantic schemas."""

from typing import Any

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    """POST /api/compare — request body."""

    query: str = Field(..., min_length=1, max_length=4096, description="User query to compare")
    base_model_id: str | None = Field(None, description="Base model catalog ID")
    finetuned_model_id: str | None = Field(None, description="Fine-tuned model catalog ID")


class VariantResponse(BaseModel):
    """Response from a single model variant."""

    variant: str
    response: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int
    token_count: int


class ComparisonMetrics(BaseModel):
    """Computed deltas between base and fine-tuned responses."""

    latency_delta_ms: int
    token_count_delta: int
    citation_overlap: float
    response_length_delta: int


class CompareResponse(BaseModel):
    """POST /api/compare — full comparison result."""

    query: str
    base: VariantResponse
    finetuned: VariantResponse
    comparison: ComparisonMetrics


class StalenessResponse(BaseModel):
    """GET /api/datasets/{id}/staleness — staleness check result."""

    dataset_id: str
    current_version: int
    last_ft_version: int | None = None
    sources_since_ft: int
    is_stale: bool
    message: str | None = None
