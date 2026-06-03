"""Comparison API endpoints — model comparison and dataset staleness detection.

POST /api/v1/compare                — compare base vs. fine-tuned model responses
GET  /api/v1/datasets/{id}/staleness — check if dataset has new sources since last FT
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.schemas.comparison import (
    CompareRequest,
    CompareResponse,
    StalenessResponse,
)
from app.services.comparison_service import compare_models, detect_staleness

logger = logging.getLogger(__name__)

router = APIRouter(tags=["comparison"])


@router.post(
    "/api/v1/compare",
    response_model=CompareResponse,
    summary="Compare base vs. fine-tuned model responses",
)
async def compare(
    body: CompareRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompareResponse:
    """
    Run the same query through both base and fine-tuned models.

    Returns side-by-side responses with latency, token count, and
    citation overlap metrics.
    """
    try:
        result = await compare_models(
            db,
            query=body.query,
            base_model_id=body.base_model_id,
            finetuned_model_id=body.finetuned_model_id,
        )
    except Exception as exc:
        logger.exception("Comparison failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {exc}",
        )

    return CompareResponse(**result)


@router.get(
    "/api/v1/datasets/{dataset_id}/staleness",
    response_model=StalenessResponse,
    summary="Check dataset staleness vs. last fine-tune",
)
async def check_staleness(
    dataset_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StalenessResponse:
    """
    Check whether a dataset has new sources since the last completed
    fine-tuning job. Returns staleness flag and message.
    """
    result = await detect_staleness(db, dataset_id)
    return StalenessResponse(**result)
