"""add evaluation benchmark and status fields

Revision ID: c5e9f0a1b2c3
Revises: b4d7e8f9a0b1
Create Date: 2026-06-04 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c5e9f0a1b2c3"
down_revision: str | None = "b4d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── evaluation_runs: add benchmark & status columns ───────────
    op.add_column(
        "evaluation_runs",
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
    )
    op.create_index("idx_eval_runs_status", "evaluation_runs", ["status"])

    op.add_column(
        "evaluation_runs",
        sa.Column("per_sample_scores", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("benchmark_config", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("duration_seconds", sa.Float(), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    # Update the existing nullable constraint on metrics to allow default
    op.alter_column(
        "evaluation_runs",
        "metrics",
        server_default="{}",
    )


def downgrade() -> None:
    op.alter_column(
        "evaluation_runs",
        "metrics",
        server_default=None,
    )
    op.drop_column("evaluation_runs", "error_message")
    op.drop_column("evaluation_runs", "duration_seconds")
    op.drop_column("evaluation_runs", "benchmark_config")
    op.drop_column("evaluation_runs", "per_sample_scores")
    op.drop_index("idx_eval_runs_status", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "status")
