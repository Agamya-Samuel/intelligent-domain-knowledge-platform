"""DocumentChunk model — text segments for RAG retrieval."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class DocumentChunk(Base, TimestampMixin):
    """
    A text chunk extracted from a document.

    Each chunk is a small segment of text (typically 256–1024 tokens)
    that will be embedded and stored in the vector DB for retrieval.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        # Prevent duplicate chunks within the same document
        {"comment": "Text segments extracted from documents for RAG retrieval"},
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash for deduplication",
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="page_num, section, headings, etc.",
    )

    # ── Relationships ─────────────────────────────────────────────
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")  # noqa: F821

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id!r} doc={self.document_id!r} idx={self.chunk_index!r}>"
