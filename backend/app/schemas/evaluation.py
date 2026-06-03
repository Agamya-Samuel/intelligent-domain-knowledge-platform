"""Evaluation Pydantic schemas — RAGAS evaluation runs, benchmarks, and metrics."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvalRunType(StrEnum):
    """Evaluation run type values."""

    BASELINE = "baseline"
    POST_TRAINING = "post_training"
    WEEKLY_REGRESSION = "weekly_regression"
    COMPARISON = "comparison"
    BENCHMARK = "benchmark"


class EvalRunStatus(StrEnum):
    """Evaluation run status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Request Schemas ─────────────────────────────────────────────────


class EvaluationCreateRequest(BaseModel):
    """POST /api/evaluations — trigger an evaluation run."""

    run_type: EvalRunType = Field(..., description="Type of evaluation to run")
    model_id: str | None = Field(None, description="Model to evaluate (defaults to base)")
    model_variant: str = Field("base", description="base or finetuned")
    job_id: str | None = Field(None, description="Link to a fine-tuning job (for post_training)")


class BenchmarkRequest(BaseModel):
    """POST /api/evaluations/benchmark — trigger a model benchmark."""

    model_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of MODEL_CATALOG IDs to benchmark (1-5 models)",
    )
    model_variant: str = Field(
        "base",
        description="Model variant to evaluate (base or finetuned)",
    )
    job_id: str | None = Field(
        None,
        description="Fine-tuning job ID when benchmarking a finetuned variant",
    )


class ComparisonRequest(BaseModel):
    """POST /api/evaluations/compare — A/B comparison between two runs."""

    base_eval_id: str = Field(..., description="Evaluation run ID for the baseline")
    candidate_eval_id: str = Field(..., description="Evaluation run ID for the candidate")


# ── Response Schemas ────────────────────────────────────────────────


class EvaluationMetricsResponse(BaseModel):
    """RAGAS metrics from an evaluation run."""

    faithfulness: float | None = None
    context_relevance: float | None = None
    answer_relevance: float | None = None
    context_recall: float | None = None


class PerSampleScore(BaseModel):
    """RAGAS scores for a single eval question."""

    question: str
    faithfulness: float | None = None
    context_relevance: float | None = None
    answer_relevance: float | None = None
    context_recall: float | None = None


class EvaluationRunResponse(BaseModel):
    """Single evaluation run result."""

    id: str
    run_type: str
    status: str
    model_id: str | None = None
    model_variant: str | None = None
    job_id: str | None = None
    metrics: dict
    per_sample_scores: list[PerSampleScore] | None = None
    benchmark_config: dict | None = None
    dataset_size: int | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationHistoryResponse(BaseModel):
    """GET /api/evaluations — list of evaluation runs."""

    evaluations: list[EvaluationRunResponse]
    total: int = Field(description="Total number of evaluation runs returned")


class BenchmarkResult(BaseModel):
    """Result for a single model within a benchmark run."""

    model_id: str
    model_name: str | None = None
    eval_run_id: str
    metrics: EvaluationMetricsResponse
    duration_seconds: float | None = None
    status: str


class BenchmarkResponse(BaseModel):
    """Response for a benchmark run across multiple models."""

    benchmark_id: str = Field(description="Shared benchmark identifier")
    results: list[BenchmarkResult]
    total_models: int
    created_at: datetime


class MetricDelta(BaseModel):
    """Delta between two metric values (candidate - base)."""

    faithfulness_delta: float | None = None
    context_relevance_delta: float | None = None
    answer_relevance_delta: float | None = None
    context_recall_delta: float | None = None


class ComparisonResponse(BaseModel):
    """A/B comparison result between two evaluation runs."""

    base_eval_id: str
    candidate_eval_id: str
    base_metrics: EvaluationMetricsResponse
    candidate_metrics: EvaluationMetricsResponse
    deltas: MetricDelta
    winner: str | None = Field(
        None,
        description="Model ID or variant that scored higher on average across all metrics",
    )
