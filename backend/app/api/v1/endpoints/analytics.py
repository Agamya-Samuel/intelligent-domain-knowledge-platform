"""Analytics API endpoints — aggregated dashboard data for the frontend.

Provides data for the analytics/evaluation dashboard (TRD §4.8, §6.8):
  - RAGAS metrics over time
  - Fine-tuning job statistics
  - Budget usage breakdown
  - Chat usage summary
  - Retrieval performance metrics
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.dependencies import get_current_user, get_db
from app.models.budget_tracking import BudgetTracking
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.evaluation_run import EvaluationRun
from app.models.fine_tuning_job import FineTuningJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ── Response Schemas ──────────────────────────────────────────────────


class MetricsTrendPoint(BaseModel):
    """A single point in the RAGAS metrics time series."""

    date: str
    run_type: str
    faithfulness: float | None = None
    context_relevance: float | None = None
    answer_relevance: float | None = None
    context_recall: float | None = None


class MetricsTrendResponse(BaseModel):
    """RAGAS metrics over time for charting."""

    points: list[MetricsTrendPoint]
    latest: dict | None = None


class JobStatsResponse(BaseModel):
    """Aggregated fine-tuning job statistics."""

    total_jobs: int
    completed: int
    failed: int
    queued: int
    total_cost: float
    avg_cost_per_job: float | None = None
    avg_duration_minutes: float | None = None


class ChatStatsResponse(BaseModel):
    """Chat usage statistics."""

    total_sessions: int
    total_messages: int
    user_messages: int
    assistant_messages: int
    avg_latency_ms: float | None = None


class BudgetTrendPoint(BaseModel):
    """A single point in budget usage time series."""

    month: str
    total_spend: float
    job_count: int


class BudgetTrendResponse(BaseModel):
    """Budget usage over time."""

    points: list[BudgetTrendPoint]
    current_spend: float
    budget_limit: float


class AnalyticsOverviewResponse(BaseModel):
    """High-level overview of all system metrics."""

    metrics_trend: MetricsTrendResponse
    job_stats: JobStatsResponse
    chat_stats: ChatStatsResponse
    budget_trend: BudgetTrendResponse


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get(
    "/metrics/trend",
    response_model=MetricsTrendResponse,
    summary="Get RAGAS metrics over time",
)
async def get_metrics_trend(
    limit: int = Query(default=20, ge=1, le=100),
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MetricsTrendResponse:
    """Return RAGAS metrics time series from completed evaluation runs."""
    stmt = (
        select(EvaluationRun)
        .where(EvaluationRun.status == "completed")
        .order_by(EvaluationRun.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    runs = list(result.scalars().all())

    points: list[MetricsTrendPoint] = []
    for run in reversed(runs):
        m = run.metrics or {}
        points.append(
            MetricsTrendPoint(
                date=run.created_at.isoformat() if run.created_at else "",
                run_type=run.run_type,
                faithfulness=m.get("faithfulness"),
                context_relevance=m.get("context_relevance"),
                answer_relevance=m.get("answer_relevance"),
                context_recall=m.get("context_recall"),
            )
        )

    latest = None
    if runs:
        m = runs[0].metrics or {}
        latest = {
            "faithfulness": m.get("faithfulness"),
            "context_relevance": m.get("context_relevance"),
            "answer_relevance": m.get("answer_relevance"),
            "context_recall": m.get("context_recall"),
            "run_type": runs[0].run_type,
            "date": runs[0].created_at.isoformat() if runs[0].created_at else None,
        }

    return MetricsTrendResponse(points=points, latest=latest)


@router.get(
    "/jobs/stats",
    response_model=JobStatsResponse,
    summary="Get fine-tuning job statistics",
)
async def get_job_stats(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStatsResponse:
    """Return aggregated statistics for the user's fine-tuning jobs."""
    # Count by status
    status_counts = await db.execute(
        select(FineTuningJob.status, func.count(FineTuningJob.id))
        .where(FineTuningJob.user_id == user.user_id)
        .group_by(FineTuningJob.status)
    )
    counts = dict(status_counts.all())

    # Total cost from budget tracking
    cost_result = await db.execute(
        select(func.coalesce(func.sum(BudgetTracking.cost), 0.0))
        .join(FineTuningJob, BudgetTracking.job_id == FineTuningJob.id)
        .where(FineTuningJob.user_id == user.user_id)
    )
    total_cost = float(cost_result.scalar_one())

    total_jobs = sum(counts.values())
    avg_cost = total_cost / total_jobs if total_jobs > 0 else None

    # Average duration for completed jobs
    duration_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", FineTuningJob.completed_at)
                - func.extract("epoch", FineTuningJob.created_at)
            )
        ).where(
            FineTuningJob.user_id == user.user_id,
            FineTuningJob.status == "completed",
            FineTuningJob.completed_at.isnot(None),
        )
    )
    avg_duration_secs = duration_result.scalar_one()
    avg_duration_min = float(avg_duration_secs) / 60.0 if avg_duration_secs else None

    return JobStatsResponse(
        total_jobs=total_jobs,
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        queued=counts.get("queued", 0),
        total_cost=round(total_cost, 4),
        avg_cost_per_job=round(avg_cost, 4) if avg_cost else None,
        avg_duration_minutes=round(avg_duration_min, 1) if avg_duration_min else None,
    )


@router.get(
    "/chat/stats",
    response_model=ChatStatsResponse,
    summary="Get chat usage statistics",
)
async def get_chat_stats(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatStatsResponse:
    """Return chat usage statistics for the authenticated user."""
    # Total sessions
    session_count = await db.execute(
        select(func.count(ChatSession.id)).where(ChatSession.user_id == user.user_id)
    )
    total_sessions = session_count.scalar_one()

    # Message counts by role
    msg_counts = await db.execute(
        select(ChatMessage.role, func.count(ChatMessage.id))
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user.user_id)
        .group_by(ChatMessage.role)
    )
    counts = dict(msg_counts.all())

    # Average latency
    avg_latency = await db.execute(
        select(func.avg(ChatMessage.latency_ms))
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(
            ChatSession.user_id == user.user_id,
            ChatMessage.role == "assistant",
            ChatMessage.latency_ms.isnot(None),
        )
    )
    avg_lat = avg_latency.scalar_one()

    return ChatStatsResponse(
        total_sessions=total_sessions,
        total_messages=sum(counts.values()),
        user_messages=counts.get("user", 0),
        assistant_messages=counts.get("assistant", 0),
        avg_latency_ms=round(float(avg_lat), 0) if avg_lat else None,
    )


@router.get(
    "/budget/trend",
    response_model=BudgetTrendResponse,
    summary="Get budget usage trend",
)
async def get_budget_trend(
    months: int = Query(default=6, ge=1, le=12),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BudgetTrendResponse:
    """Return monthly budget usage for the past N months."""
    from app.config import settings
    from app.services.budget_service import get_monthly_spend

    # Get current month spend
    current_spend = float(await get_monthly_spend(db))

    # Get historical spend grouped by month
    stmt = (
        select(
            func.date_trunc("month", BudgetTracking.created_at).label("month"),
            func.sum(BudgetTracking.cost).label("total_spend"),
            func.count(BudgetTracking.id).label("job_count"),
        )
        .group_by("month")
        .order_by(func.date_trunc("month", BudgetTracking.created_at).desc())
        .limit(months)
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    points = []
    for row in reversed(rows):
        month_date = row.month
        month_str = (
            month_date.strftime("%Y-%m") if hasattr(month_date, "strftime") else str(month_date)
        )
        points.append(
            BudgetTrendPoint(
                month=month_str,
                total_spend=round(float(row.total_spend or 0), 4),
                job_count=row.job_count,
            )
        )

    return BudgetTrendResponse(
        points=points,
        current_spend=round(current_spend, 4),
        budget_limit=settings.BUDGET_MONTHLY_LIMIT,
    )


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Get full analytics overview",
)
async def get_analytics_overview(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsOverviewResponse:
    """Return a combined overview of all analytics data."""
    # Fetch all sub-metrics
    metrics = await get_metrics_trend(limit=20, _user=user, db=db)
    jobs = await get_job_stats(user=user, db=db)
    chat = await get_chat_stats(user=user, db=db)
    budget = await get_budget_trend(months=6, user=user, db=db)

    return AnalyticsOverviewResponse(
        metrics_trend=metrics,
        job_stats=jobs,
        chat_stats=chat,
        budget_trend=budget,
    )
