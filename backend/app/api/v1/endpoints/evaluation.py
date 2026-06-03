"""Evaluation API endpoints — RAGAS evaluation runs and history."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.models.evaluation_run import EvaluationRun
from app.schemas.evaluation import (
    EvaluationCreateRequest,
    EvaluationHistoryResponse,
    EvaluationRunResponse,
)
from app.services.evaluation_service import run_evaluation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.post(
    "",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an evaluation run",
)
async def create_evaluation(
    body: EvaluationCreateRequest,
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationRunResponse:
    """
    Trigger a RAGAS evaluation run.

    Week 4: Creates a skeleton evaluation with placeholder metrics.
    Full RAGAS integration in Week 6+.
    """
    eval_run = await run_evaluation(
        db,
        run_type=body.run_type,
        model_id=body.model_id,
        model_variant=body.model_variant,
        job_id=body.job_id,
    )
    return EvaluationRunResponse.model_validate(eval_run)


@router.get(
    "",
    response_model=EvaluationHistoryResponse,
    summary="Get evaluation run history",
)
async def list_evaluations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationHistoryResponse:
    """List evaluation runs, most recent first."""
    result = await db.execute(
        select(EvaluationRun)
        .order_by(EvaluationRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    evaluations = result.scalars().all()
    return EvaluationHistoryResponse(
        evaluations=[EvaluationRunResponse.model_validate(e) for e in evaluations]
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
    """Get details of a specific evaluation run."""
    result = await db.execute(
        select(EvaluationRun).where(EvaluationRun.id == eval_id)
    )
    eval_run = result.scalar_one_or_none()
    if not eval_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run '{eval_id}' not found",
        )
    return EvaluationRunResponse.model_validate(eval_run)
