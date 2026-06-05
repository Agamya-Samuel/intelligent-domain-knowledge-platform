"""Fine-tuning Pydantic schemas — job creation, status, and history."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FineTuneStatus(StrEnum):
    """Fine-tuning job status values."""

    QUEUED = "queued"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Request Schemas ─────────────────────────────────────────────────


class FineTuneCreateRequest(BaseModel):
    """POST /api/fine-tune — trigger a new fine-tuning job."""

    model_id: str = Field(..., description="MODEL_CATALOG identifier (e.g. qwen2.5-14b)")
    dataset_id: str = Field(..., description="UUID of the dataset to fine-tune on")


# ── Response Schemas ────────────────────────────────────────────────


class FineTuneCreateResponse(BaseModel):
    """Response after triggering a fine-tune job (HTTP 202)."""

    job_id: str
    status: str
    queue_position: int | None = None
    estimated_cost: float | None = None


class FineTuneStatusResponse(BaseModel):
    """GET /api/fine-tune/status/{job_id} — job status and metrics."""

    id: str
    user_id: str
    model_id: str
    dataset_id: str
    dataset_version: int
    status: str
    queue_position: int | None = None
    training_metrics: dict | None = None
    eval_report: dict | None = None
    cost: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FineTuneHistoryResponse(BaseModel):
    """GET /api/fine-tune/history — list of user's past jobs."""

    jobs: list[FineTuneStatusResponse]
