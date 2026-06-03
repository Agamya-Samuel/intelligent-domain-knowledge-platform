"""Dataset model — user-managed collections of document sources for fine-tuning."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class Dataset(Base, TimestampMixin):
    """
    A dataset is a user-managed collection of document sources.

    Lifecycle:
        active → archived (soft-delete; data preserved)

    Version auto-increments when sources are added.
    No deletion allowed — PID constraint.
    """

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the user who owns this dataset",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable dataset name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional dataset description",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Current version number; auto-increments on source add",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        index=True,
        comment="active or archived",
    )
    domain_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
        comment="Optional user-defined domain tags",
    )

    # ── Relationships ─────────────────────────────────────────────
    sources: Mapped[list["DatasetSource"]] = relationship(  # noqa: F821
        "DatasetSource",
        back_populates="dataset",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    version_history: Mapped[list["DatasetVersionHistory"]] = relationship(  # noqa: F821
        "DatasetVersionHistory",
        back_populates="dataset",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Dataset id={self.id!r} name={self.name!r} "
            f"version={self.version!r} status={self.status!r}>"
        )
