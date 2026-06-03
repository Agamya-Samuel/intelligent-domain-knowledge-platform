"""BudgetTracking model — per-job cost tracking for the $30/month hard block."""

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class BudgetTracking(Base, TimestampMixin):
    """
    Records cost data for every fine-tuning / inference job.

    The budget service aggregates rows by month and enforces the
    $30 hard-block limit before dispatching new jobs.
    """

    __tablename__ = "budget_tracking"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("fine_tuning_jobs.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="FK to the fine-tuning job this row tracks",
    )
    model_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Identifier from MODEL_CATALOG (e.g. phi-3-mini-4k)",
    )
    model_tier: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Tier level: 1=Compact, 2=Standard, 3=Enhanced, 4=Maximum",
    )
    gpu_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="GPU assigned by Modal (e.g. T4, A10G, A100)",
    )
    cost: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        comment="Actual cost incurred by this job in USD",
    )
    estimated_cost: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="Pre-job cost estimate based on model tier and dataset size",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        index=True,
        comment="Job status: queued, running, completed, failed",
    )
    started_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the job actually started on Modal",
    )
    completed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the job finished (success or failure)",
    )

    # ── Relationships ─────────────────────────────────────────────
    job: Mapped["FineTuningJob | None"] = relationship(  # noqa: F821
        "FineTuningJob",
        back_populates="budget_entries",
    )

    def __repr__(self) -> str:
        return (
            f"<BudgetTracking id={self.id!r} job={self.job_id!r} "
            f"cost={self.cost!r} status={self.status!r}>"
        )
