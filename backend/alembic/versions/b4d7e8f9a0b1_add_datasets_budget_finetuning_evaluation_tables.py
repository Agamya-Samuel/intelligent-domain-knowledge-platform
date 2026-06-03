"""add_datasets_budget_finetuning_evaluation_tables

Revision ID: b4d7e8f9a0b1
Revises: a3b7c9d2e4f5
Create Date: 2026-06-20 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b4d7e8f9a0b1"
down_revision: str | None = "a3b7c9d2e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Datasets ──────────────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("domain_tags", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Dataset Sources ───────────────────────────────────────────
    op.create_table(
        "dataset_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("dataset_version", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("processed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ds_sources_dataset_version", "dataset_sources", ["dataset_id", "dataset_version"])

    # ── Dataset Version History ─────────────────────────────────
    op.create_table(
        "dataset_version_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change_description", sa.Text, nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=True),
        sa.Column("sources_added", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Fine-Tuning Jobs ─────────────────────────────────────────
    op.create_table(
        "fine_tuning_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("dataset_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("queue_position", sa.Integer(), nullable=True),
        sa.Column("modal_function_id", sa.String(255), nullable=True),
        sa.Column("lora_adapter_path", sa.String(500), nullable=True),
        sa.Column("checkpoint_s3_path", sa.String(500), nullable=True),
        sa.Column("training_metrics", postgresql.JSONB(), nullable=True),
        sa.Column("eval_report", postgresql.JSONB(), nullable=True),
        sa.Column("cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ft_jobs_dataset_version", "fine_tuning_jobs", ["dataset_id", "dataset_version"])

    # ── Budget Tracking ────────────────────────────────────────────
    op.create_table(
        "budget_tracking",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("fine_tuning_jobs.id", ondelete="SET NULL"), nullable=False, index=True),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("model_tier", sa.Integer(), nullable=False),
        sa.Column("gpu_type", sa.String(20), nullable=False),
        sa.Column("cost", sa.Numeric(10, 4), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Evaluation Runs ───────────────────────────────────────────
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_type", sa.String(30), nullable=False, index=True),
        sa.Column("model_id", sa.String(100), nullable=True),
        sa.Column("model_variant", sa.String(20), nullable=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("fine_tuning_jobs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("dataset_size", sa.Integer(), nullable=True),
        sa.Column("s3_report_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("evaluation_runs")
    op.drop_table("budget_tracking")
    op.drop_index("idx_ft_jobs_dataset_version", table_name="fine_tuning_jobs")
    op.drop_table("fine_tuning_jobs")
    op.drop_table("dataset_version_history")
    op.drop_index("idx_ds_sources_dataset_version", table_name="dataset_sources")
    op.drop_table("dataset_sources")
    op.drop_table("datasets")
