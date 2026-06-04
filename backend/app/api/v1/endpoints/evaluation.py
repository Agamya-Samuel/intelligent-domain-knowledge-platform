"""Evaluation API endpoints — RAGAS evaluation runs, benchmarks, and comparisons."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MODEL_CATALOG
from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.models.evaluation_run import EvaluationRun
from app.schemas.evaluation import (
    BenchmarkRequest,
    BenchmarkResponse,
    BenchmarkResult,
    ComparisonRequest,
    ComparisonResponse,
    EvaluationCreateRequest,
    EvaluationHistoryResponse,
    EvaluationMetricsResponse,
    EvaluationRunResponse,
)
from app.services.evaluation_service import (
    compare_evaluations,
    run_benchmark,
    run_evaluation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


# ── Helpers ──────────────────────────────────────────────────────────


def _model_name(model_id: str | None) -> str | None:
    """Look up the human-readable model name from the MODEL_CATALOG."""
    if not model_id:
        return None
    for entry in MODEL_CATALOG:
        if entry["id"] == model_id:
            return entry["name"]
    return model_id


# ── CRUD Endpoints ───────────────────────────────────────────────────


@router.post(
    "",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an evaluation run",
)
async def create_evaluation(
    body: EvaluationCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationRunResponse:
    """
    Trigger a RAGAS evaluation run.

    The evaluation runs synchronously and returns the completed result.
    For large eval datasets, expect longer response times.
    """
    eval_run = await run_evaluation(
        db,
        run_type=body.run_type,
        model_id=body.model_id,
        model_variant=body.model_variant,
        job_id=body.job_id,
        user_id=user.user_id,
    )
    await db.commit()
    return EvaluationRunResponse.model_validate(eval_run)


@router.get(
    "",
    response_model=EvaluationHistoryResponse,
    summary="Get evaluation run history",
)
async def list_evaluations(
    run_type: str | None = Query(default=None, description="Filter by run type"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationHistoryResponse:
    """List evaluation runs, most recent first. Supports filtering by type and status."""
    stmt = select(EvaluationRun).where(EvaluationRun.user_id == user.user_id)

    if run_type:
        stmt = stmt.where(EvaluationRun.run_type == run_type)
    if status_filter:
        stmt = stmt.where(EvaluationRun.status == status_filter)

    stmt = stmt.order_by(EvaluationRun.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    evaluations = result.scalars().all()
    return EvaluationHistoryResponse(
        evaluations=[EvaluationRunResponse.model_validate(e) for e in evaluations],
        total=len(evaluations),
    )


@router.get(
    "/{eval_id}",
    response_model=EvaluationRunResponse,
    summary="Get evaluation run details",
)
async def get_evaluation(
    eval_id: str,
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationRunResponse:
    """Get details of a specific evaluation run, including per-sample scores."""
    result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == eval_id))
    eval_run = result.scalar_one_or_none()
    if not eval_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run '{eval_id}' not found",
        )
    return EvaluationRunResponse.model_validate(eval_run)


# ── Benchmark Endpoints ─────────────────────────────────────────────


@router.post(
    "/benchmark",
    response_model=BenchmarkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a model benchmark",
)
async def create_benchmark(
    body: BenchmarkRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkResponse:
    """
    Run a benchmark evaluation across multiple models from the MODEL_CATALOG.

    Each model is evaluated against the full eval dataset. Models are processed
    sequentially to avoid overloading the LLM endpoint.
    """
    # Validate that all model_ids exist in the catalog
    valid_ids = {m["id"] for m in MODEL_CATALOG}
    invalid = [mid for mid in body.model_ids if mid not in valid_ids]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown model IDs: {invalid}. Valid IDs: {sorted(valid_ids)}",
        )

    runs = await run_benchmark(
        db,
        model_ids=body.model_ids,
        model_variant=body.model_variant,
        job_id=body.job_id,
        user_id=user.user_id,
    )
    await db.commit()

    # Build the response
    benchmark_id = runs[0].benchmark_config.get("benchmark_id", "unknown") if runs else "unknown"

    results = []
    for run in runs:
        m = run.metrics or {}
        results.append(
            BenchmarkResult(
                model_id=run.model_id or "unknown",
                model_name=_model_name(run.model_id),
                eval_run_id=run.id,
                metrics=EvaluationMetricsResponse(
                    faithfulness=m.get("faithfulness"),
                    context_relevance=m.get("context_relevance"),
                    answer_relevance=m.get("answer_relevance"),
                    context_recall=m.get("context_recall"),
                ),
                duration_seconds=run.duration_seconds,
                status=run.status,
            )
        )

    return BenchmarkResponse(
        benchmark_id=benchmark_id,
        results=results,
        total_models=len(results),
        created_at=runs[0].created_at if runs else None,
    )


# ── Comparison Endpoint ─────────────────────────────────────────────


@router.post(
    "/compare",
    response_model=ComparisonResponse,
    summary="Compare two evaluation runs",
)
async def compare_runs(
    body: ComparisonRequest,
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComparisonResponse:
    """
    A/B comparison between two completed evaluation runs.

    Computes metric deltas and determines a winner based on
    average performance across all RAGAS metrics.
    """
    try:
        result = await compare_evaluations(
            db,
            base_eval_id=body.base_eval_id,
            candidate_eval_id=body.candidate_eval_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ComparisonResponse(**result)
