"""EvaluationRun model — RAGAS evaluation results for the RAG pipeline."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class EvaluationRun(Base, TimestampMixin):
    """
    Stores results from a RAGAS evaluation run.

    Run types:
        baseline             — Initial evaluation before any fine-tuning
        post_training        — After a fine-tuning job completes
        weekly_regression    — Scheduled regression check
        comparison           — A/B comparison between model variants

    Metrics stored as JSONB:
        {
            "faithfulness": 0.92,
            "context_relevance": 0.87,
            "answer_relevance": 0.90,
            "context_recall": 0.85
        }
    """

    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    run_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="baseline, post_training, weekly_regression, comparison",
    )
    model_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="MODEL_CATALOG identifier of the model evaluated",
    )
    model_variant: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="base or finetuned",
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("fine_tuning_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Link to the fine-tuning job (if post_training run)",
    )
    metrics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="RAGAS metrics: faithfulness, context_relevance, answer_relevance, context_recall",
    )
    dataset_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of question-answer pairs in the eval dataset",
    )
    s3_report_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 path to the full evaluation report (if exported)",
    )

    # ── Relationships ─────────────────────────────────────────────
    job: Mapped["FineTuningJob | None"] = relationship(  # noqa: F821
        "FineTuningJob",
    )

    def __repr__(self) -> str:
        return (
            f"<EvaluationRun id={self.id!r} type={self.run_type!r} "
            f"model={self.model_id!r}>"
        )
