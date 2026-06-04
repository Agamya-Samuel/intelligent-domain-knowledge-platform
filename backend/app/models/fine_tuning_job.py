"""FineTuningJob model — FIFO-queued QLoRA training jobs via Modal."""

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class FineTuningJob(Base, TimestampMixin):
    """
    A fine-tuning job submitted by a user.

    Lifecycle:
        queued → training → evaluating → completed
        queued → training → evaluating → completed (with eval report)
        queued → training → failed
        queued → failed (budget / dataset validation)

    Only one job runs at a time (FIFO enforced by queue_position).
    Training is offloaded to Modal.com using QLoRA on the selected base model.
    """

    __tablename__ = "fine_tuning_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who submitted this job",
    )
    model_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MODEL_CATALOG identifier (e.g. phi-3-mini-4k)",
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("datasets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Dataset snapshot used for training",
    )
    dataset_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Dataset version locked at submission time",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        index=True,
        comment="queued, training, evaluating, completed, failed",
    )
    queue_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="FIFO position (NULL when not queued)",
    )
    modal_function_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Modal function call ID for the running job",
    )
    lora_adapter_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 path to the LoRA adapter checkpoint",
    )
    checkpoint_s3_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 path to full checkpoint (if exported)",
    )
    training_metrics: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Training telemetry: loss_curve, eval_scores, epochs_completed",
    )
    eval_report: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Post-training evaluation: ragas_metrics, domain_benchmark",
    )
    cost: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="Total cost of this job in USD",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if the job failed",
    )
    started_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When training actually started on Modal",
    )
    completed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the job reached terminal state",
    )

    # ── Relationships ─────────────────────────────────────────────
    dataset: Mapped["Dataset"] = relationship(  # noqa: F821
        "Dataset",
    )
    budget_entries: Mapped[list["BudgetTracking"]] = relationship(  # noqa: F821
        "BudgetTracking",
        back_populates="job",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<FineTuningJob id={self.id!r} model={self.model_id!r} status={self.status!r}>"
