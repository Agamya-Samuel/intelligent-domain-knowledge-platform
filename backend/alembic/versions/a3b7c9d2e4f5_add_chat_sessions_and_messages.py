"""add_chat_sessions_and_messages

Revision ID: a3b7c9d2e4f5
Revises: 2c2a501c1c87
Create Date: 2026-06-16 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b7c9d2e4f5"
down_revision: str | None = "2c2a501c1c87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── chat_sessions ────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            nullable=False,
            index=True,
            comment="Reference to the user who owns this session",
        ),
        sa.Column(
            "title",
            sa.String(500),
            nullable=False,
            server_default="New Chat",
            comment="Auto-generated or user-set session title",
        ),
        sa.Column(
            "model_variant",
            sa.String(20),
            nullable=False,
            server_default="base",
            comment="Active model variant: 'base' or 'finetuned'",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── chat_messages ───────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            comment="Message role: 'user', 'assistant', 'system'",
        ),
        sa.Column(
            "content",
            sa.Text,
            nullable=False,
            comment="Message text content",
        ),
        sa.Column(
            "citations",
            sa.JSON,
            nullable=True,
            comment="Citation metadata: [{source, page, section}]",
        ),
        sa.Column(
            "retrieval_context",
            sa.JSON,
            nullable=True,
            comment="Retrieved chunks used for generation",
        ),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
