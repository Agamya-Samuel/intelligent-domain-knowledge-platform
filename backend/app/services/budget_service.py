"""Budget tracking service — aggregates spending and enforces the $30/month hard block."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.budget_tracking import BudgetTracking

logger = logging.getLogger(__name__)


async def get_monthly_spend(db: AsyncSession) -> Decimal:
    """Sum all completed/running costs for the current calendar month."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(func.coalesce(func.sum(BudgetTracking.cost), 0.00)).where(
            extract("year", BudgetTracking.created_at) == now.year,
            extract("month", BudgetTracking.created_at) == now.month,
            BudgetTracking.status.in_(["completed", "running"]),
        )
    )
    return result.scalar_one()


async def record_spend(
    db: AsyncSession,
    job_id: str,
    cost: float,
    *,
    status: str = "completed",
) -> None:
    """
    Record a fine-tuning job's cost in the budget_tracking table.

    Called after a job completes (or fails with partial cost).
    If a record already exists for this job, it is updated.
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy import update as sa_update

    existing_result = await db.execute(
        sa_select(BudgetTracking).where(BudgetTracking.job_id == job_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        await db.execute(
            sa_update(BudgetTracking)
            .where(BudgetTracking.job_id == job_id)
            .values(cost=Decimal(str(cost)), status=status)
        )
    else:
        entry = BudgetTracking(
            job_id=job_id,
            cost=Decimal(str(cost)),
            status=status,
        )
        db.add(entry)

    await db.flush()
    logger.info("Recorded spend: job=%s cost=$%.4f status=%s", job_id, cost, status)


async def get_budget_summary(db: AsyncSession) -> dict:
    """
    Build the budget summary for the current month.

    Returns a dict matching BudgetSummaryResponse schema.
    """
    now = datetime.now(UTC)
    total_spend = float(await get_monthly_spend(db))
    remaining = max(0.0, settings.BUDGET_MONTHLY_LIMIT - total_spend)

    # Count runs this month
    runs_result = await db.execute(
        select(func.count(BudgetTracking.id)).where(
            extract("year", BudgetTracking.created_at) == now.year,
            extract("month", BudgetTracking.created_at) == now.month,
        )
    )
    runs_this_month = runs_result.scalar_one()

    # Estimate remaining runs based on average cost per completed run
    avg_cost_result = await db.execute(
        select(func.avg(BudgetTracking.cost)).where(
            extract("year", BudgetTracking.created_at) == now.year,
            extract("month", BudgetTracking.created_at) == now.month,
            BudgetTracking.status == "completed",
        )
    )
    avg_cost = avg_cost_result.scalar_one()
    
    # Fallback: if no completed runs, use cheapest model cost from catalog
    if not avg_cost or avg_cost <= 0:
        from app.config import MODEL_CATALOG
        cheapest_cost = min((m["est_cost"] for m in MODEL_CATALOG if m.get("available")), default=None)
        avg_cost = cheapest_cost if cheapest_cost else 5.0  # Default to $5 if catalog empty
    
    estimated_runs_left = int(remaining / avg_cost) if avg_cost > 0 else 0

    # Period boundaries
    period_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        period_end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        period_end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)

    return {
        "total_spend": round(total_spend, 4),
        "remaining": round(remaining, 4),
        "budget_limit": settings.BUDGET_MONTHLY_LIMIT,
        "runs_this_month": runs_this_month,
        "estimated_runs_left": estimated_runs_left,
        "period_start": period_start,
        "period_end": period_end,
    }
