"""add_user_id_to_evaluation_runs

Revision ID: e1f2g3h4i5j6
Revises: c5e9f0a1b2c3
Create Date: 2026-06-20 10:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2g3h4i5j6"
down_revision: str | None = "c5e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add user_id column to evaluation_runs table
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "user_id",
            sa.String(255),
            nullable=True,
            index=True,
            comment="User who triggered the evaluation",
        ),
    )


def downgrade() -> None:
    # Remove user_id column from evaluation_runs table
    op.drop_column("evaluation_runs", "user_id")