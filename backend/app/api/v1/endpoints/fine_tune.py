"""Fine-tuning API endpoints — trigger, status, history, cost estimation, and training data.

POST /api/fine-tune follows the validation flow from TRD §6.4:
  1. Validate auth
  2. Validate dataset exists + active
  3. Budget check: total_spend + est_cost <= $30?
  4. Check queue: any running job? → Enqueue or start immediately
  5. Response: 202 {job_id, status, queue_position, estimated_cost}

GET  /api/fine-tune/estimate — pre-flight cost estimation for the UI preview.
GET  /api/fine-tune/training-data/preview — preview instruction-tuning samples.
POST /api/fine-tune/training-data/export — full export as JSON for S3 upload.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MODEL_CATALOG, settings
from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.models.dataset import Dataset
from app.models.fine_tuning_job import FineTuningJob
from app.schemas.fine_tuning import (
    FineTuneCreateRequest,
    FineTuneCreateResponse,
    FineTuneHistoryResponse,
    FineTuneStatusResponse,
)
from app.schemas.training_data import (
    CostEstimateResponse,
    TrainingDataExportResponse,
    TrainingDataPreviewResponse,
    TrainingSampleResponse,
)
from app.services.budget_service import get_monthly_spend
from app.services.training_data_service import (
    estimate_training_cost,
    prepare_training_data,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fine-tune", tags=["fine-tune"])


def _find_model_in_catalog(model_id: str) -> dict | None:
    """Look up a model by ID in the static catalog."""
    for m in MODEL_CATALOG:
        if m["id"] == model_id:
            return m
    return None


@router.post(
    "",
    response_model=FineTuneCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a fine-tuning job",
)
async def trigger_fine_tune(
    body: FineTuneCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FineTuneCreateResponse:
    """
    Trigger a fine-tuning job with dataset, budget, and queue validation.

    Returns 202 with job_id, status, queue_position, and estimated_cost.
    Returns 403 if budget exceeded.
    Returns 404 if model or dataset not found.
    """
    # 1. Validate model exists in catalog
    model = _find_model_in_catalog(body.model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{body.model_id}' not found in MODEL_CATALOG",
        )

    # 2. Validate dataset exists and is active
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == body.dataset_id, Dataset.status == "active")
    )
    dataset = dataset_result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active dataset '{body.dataset_id}' not found",
        )

    estimated_cost = model["est_cost"]

    # 3. Budget check: total_spend + est_cost <= $30?
    current_spend = float(await get_monthly_spend(db))
    if current_spend + estimated_cost > settings.BUDGET_MONTHLY_LIMIT:
        remaining = round(settings.BUDGET_MONTHLY_LIMIT - current_spend, 4)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Monthly budget exceeded",
                "remaining": remaining,
                "estimated_cost": estimated_cost,
                "budget_limit": settings.BUDGET_MONTHLY_LIMIT,
            },
        )

    # 4. Check if any job is currently running/training/evaluating
    running_result = await db.execute(
        select(func.count(FineTuningJob.id)).where(
            FineTuningJob.status.in_(["queued", "training", "evaluating"])
        )
    )
    jobs_in_progress = running_result.scalar_one()

    queue_position = None
    if jobs_in_progress > 0:
        # FIFO: assign next position
        max_pos_result = await db.execute(
            select(func.coalesce(func.max(FineTuningJob.queue_position), 0)).where(
                FineTuningJob.status == "queued"
            )
        )
        queue_position = max_pos_result.scalar_one() + 1
        job_status = "queued"
    else:
        job_status = "queued"  # Ready to be picked up by worker

    # 5. Create the job record
    job = FineTuningJob(
        user_id=user.user_id,
        model_id=body.model_id,
        dataset_id=body.dataset_id,
        dataset_version=dataset.version,
        status=job_status,
        queue_position=queue_position,
    )
    db.add(job)
    await db.flush()

    logger.info(
        "Fine-tune job created: id=%s model=%s dataset=%s queue_pos=%s",
        job.id,
        body.model_id,
        body.dataset_id,
        queue_position,
    )

    return FineTuneCreateResponse(
        job_id=job.id,
        status=job.status,
        queue_position=queue_position,
        estimated_cost=estimated_cost,
    )


@router.get(
    "/status/{job_id}",
    response_model=FineTuneStatusResponse,
    summary="Get fine-tune job status",
)
async def get_fine_tune_status(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FineTuneStatusResponse:
    """Get the current status, metrics, and details of a fine-tuning job."""
    result = await db.execute(
        select(FineTuningJob).where(
            FineTuningJob.id == job_id,
            FineTuningJob.user_id == user.user_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fine-tuning job '{job_id}' not found",
        )
    return FineTuneStatusResponse.model_validate(job)


@router.get(
    "/history",
    response_model=FineTuneHistoryResponse,
    summary="Get fine-tune job history",
)
async def list_fine_tune_history(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FineTuneHistoryResponse:
    """List the authenticated user's fine-tuning job history."""
    result = await db.execute(
        select(FineTuningJob)
        .where(FineTuningJob.user_id == user.user_id)
        .order_by(FineTuningJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    jobs = result.scalars().all()
    return FineTuneHistoryResponse(jobs=[FineTuneStatusResponse.model_validate(j) for j in jobs])


# ── Cost Estimation ──────────────────────────────────────────────────────


@router.get(
    "/estimate",
    response_model=CostEstimateResponse,
    summary="Estimate fine-tuning cost (pre-flight check)",
)
async def estimate_cost(
    model_id: str = Query(..., description="Model catalog ID"),
    dataset_id: str = Query(..., description="Dataset UUID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CostEstimateResponse:
    """
    Return an estimated cost, time, and budget check without triggering a job.

    Used by the frontend cost-preview step before the user confirms the fine-tune.
    """
    try:
        result = await estimate_training_cost(model_id, dataset_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return CostEstimateResponse(**result)


# ── Training Data Preview / Export ─────────────────────────────────────────


@router.get(
    "/training-data/preview",
    response_model=TrainingDataPreviewResponse,
    summary="Preview instruction-tuning samples",
)
async def preview_training_data(
    dataset_id: str = Query(..., description="Dataset UUID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingDataPreviewResponse:
    """
    Generate a preview of the instruction-tuning dataset.

    Returns metadata counts and the first 10 samples so the user can
    verify data quality before triggering a fine-tune.
    """
    try:
        data = await prepare_training_data(db, dataset_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    preview = data["samples"][:10]
    return TrainingDataPreviewResponse(
        dataset_id=data["dataset_id"],
        dataset_version=data["dataset_version"],
        total_samples=data["total_samples"],
        domain_samples=data["domain_samples"],
        general_samples=data["general_samples"],
        by_type=data["by_type"],
        preview_samples=[TrainingSampleResponse(**s) for s in preview],
    )


@router.post(
    "/training-data/export",
    response_model=TrainingDataExportResponse,
    summary="Export full instruction-tuning dataset",
)
async def export_training_data(
    dataset_id: str = Query(..., description="Dataset UUID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingDataExportResponse:
    """
    Generate and return the full instruction-tuning dataset for S3 upload.

    The response body contains all samples in the training format expected
    by the QLoRA training pipeline.
    """
    try:
        data = await prepare_training_data(db, dataset_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return TrainingDataExportResponse(
        dataset_id=data["dataset_id"],
        dataset_version=data["dataset_version"],
        total_samples=data["total_samples"],
        domain_samples=data["domain_samples"],
        general_samples=data["general_samples"],
        by_type=data["by_type"],
        samples=[TrainingSampleResponse(**s) for s in data["samples"]],
    )
