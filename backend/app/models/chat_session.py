"""ChatSession model — conversation sessions for RAG chat."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class ChatSession(Base, TimestampMixin):
    """
    A chat conversation session.

    Each session groups related messages from a user's conversation.
    Sessions are scoped to the user who created them.
    """

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="Reference to the user who owns this session",
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="New Chat",
        comment="Auto-generated or user-set session title",
    )
    model_variant: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="base",
        comment="Active model variant: 'base' or 'finetuned'",
    )

    # ── Relationships ─────────────────────────────────────────────
    messages: Mapped[list["ChatMessage"]] = relationship(  # noqa: F821
        "ChatMessage",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ChatSession id={self.id!r} user={self.user_id!r} title={self.title!r}>"
