"""Budget API endpoints — current spend and remaining budget."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.schemas.budget import BudgetSummaryResponse
from app.services.budget_service import get_budget_summary

router = APIRouter(prefix="/api/v1/budget", tags=["budget"])


@router.get("", response_model=BudgetSummaryResponse, summary="Get budget summary")
async def budget_summary(
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BudgetSummaryResponse:
    """Return the current month's budget usage, remaining balance, and estimated runs left."""
    summary = await get_budget_summary(db)
    return BudgetSummaryResponse(**summary)
