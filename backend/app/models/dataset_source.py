"""DatasetSource model — individual sources within a dataset."""

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class DatasetSource(Base, TimestampMixin):
    """
    An individual source (document) within a dataset.

    Source types:
        upload  — File uploaded by user → stored in S3
        s3      — Reference to existing S3 object
        text    — Pasted text → converted to Markdown → S3
        url     — Fetched URL → converted → S3

    Each source is linked to a specific dataset version.
    """

    __tablename__ = "dataset_sources"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent dataset",
    )
    dataset_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Dataset version at the time this source was added",
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="upload, s3, text, or url",
    )
    source_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="S3 key or URL where the source is stored",
    )
    file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Original file name (for upload sources)",
    )
    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="File size in bytes",
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type of the source file",
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 content hash for deduplication",
    )
    processed: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether the source has been processed through ingestion",
    )
    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if processing failed",
    )

    # ── Relationships ─────────────────────────────────────────────
    dataset: Mapped["Dataset"] = relationship(  # noqa: F821
        "Dataset",
        back_populates="sources",
    )

    def __repr__(self) -> str:
        return (
            f"<DatasetSource id={self.id!r} dataset={self.dataset_id!r} "
            f"type={self.source_type!r}>"
        )
