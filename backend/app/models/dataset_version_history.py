"""DatasetVersionHistory model — tracks version changes for datasets."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class DatasetVersionHistory(Base, TimestampMixin):
    """
    Records each version change for a dataset.

    Created automatically when sources are added, removed, or dataset
    is modified in ways that warrant a version increment.
    """

    __tablename__ = "dataset_version_history"

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
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Version number this history entry represents",
    )
    change_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of what changed",
    )
    source_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total source count at this version",
    )
    sources_added: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of new sources added in this version increment",
    )

    # ── Relationships ─────────────────────────────────────────────
    dataset: Mapped["Dataset"] = relationship(  # noqa: F821
        "Dataset",
        back_populates="version_history",
    )

    def __repr__(self) -> str:
        return (
            f"<DatasetVersionHistory id={self.id!r} dataset={self.dataset_id!r} "
            f"version={self.version!r}>"
        )
