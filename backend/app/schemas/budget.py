"""Budget Pydantic schemas — budget tracking and summary responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BudgetSummaryResponse(BaseModel):
    """GET /api/budget — current month budget summary."""

    total_spend: float
    remaining: float
    budget_limit: float = 30.00
    runs_this_month: int
    estimated_runs_left: int
    period_start: datetime
    period_end: datetime


class BudgetEntryResponse(BaseModel):
    """Individual budget tracking record."""

    id: str
    job_id: str
    model_id: str
    model_tier: int
    gpu_type: str
    cost: float
    estimated_cost: float | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
