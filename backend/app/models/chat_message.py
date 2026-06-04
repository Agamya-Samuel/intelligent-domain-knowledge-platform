"""ChatMessage model — individual messages within a chat session."""

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class ChatMessage(Base, TimestampMixin):
    """
    A single message within a chat session.

    Stores both user queries and assistant responses, with citations
    and metadata in the JSONB fields.
    """

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Message role: 'user', 'assistant', 'system'",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message text content",
    )
    citations: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Citation metadata: [{source, page, section}]",
    )
    retrieval_context: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Retrieved chunks used for generation",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="End-to-end latency in milliseconds",
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Token count of this message",
    )

    # ── Relationships ─────────────────────────────────────────────
    session: Mapped["ChatSession"] = relationship(  # noqa: F821
        "ChatSession",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return (
            f"<ChatMessage id={self.id!r} session={self.session_id!r} "
            f"role={self.role!r}>"
        )
