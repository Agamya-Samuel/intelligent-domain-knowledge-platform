"""Evaluation Pydantic schemas — RAGAS evaluation runs and metrics."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvalRunType(StrEnum):
    """Evaluation run type values."""

    BASELINE = "baseline"
    POST_TRAINING = "post_training"
    WEEKLY_REGRESSION = "weekly_regression"
    COMPARISON = "comparison"


# ── Request Schemas ─────────────────────────────────────────────────


class EvaluationCreateRequest(BaseModel):
    """POST /api/evaluations — trigger an evaluation run."""

    run_type: EvalRunType = Field(..., description="Type of evaluation to run")
    model_id: str | None = Field(None, description="Model to evaluate (defaults to base)")
    model_variant: str = Field("base", description="base or finetuned")
    job_id: str | None = Field(None, description="Link to a fine-tuning job (for post_training)")


# ── Response Schemas ────────────────────────────────────────────────


class EvaluationMetricsResponse(BaseModel):
    """RAGAS metrics from an evaluation run."""

    faithfulness: float | None = None
    context_relevance: float | None = None
    answer_relevance: float | None = None
    context_recall: float | None = None


class EvaluationRunResponse(BaseModel):
    """Single evaluation run result."""

    id: str
    run_type: str
    model_id: str | None = None
    model_variant: str | None = None
    job_id: str | None = None
    metrics: dict
    dataset_size: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationHistoryResponse(BaseModel):
    """GET /api/evaluations — list of evaluation runs."""

    evaluations: list[EvaluationRunResponse]
