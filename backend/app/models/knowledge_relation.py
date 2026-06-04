"""KnowledgeRelation model — edges in the knowledge graph."""

from sqlalchemy import JSON, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class KnowledgeRelation(Base, TimestampMixin):
    """
    A directed relationship between two knowledge entities.

    Common relation types: related_to, part_of, depends_on, contains,
    authored_by, uses, preceded_by, caused_by.
    """

    __tablename__ = "knowledge_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_entity_id",
            "target_entity_id",
            "relation_type",
            name="uq_source_target_relation",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    source_entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="related_to, part_of, depends_on, etc.",
    )
    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Confidence or strength score (0.0–1.0)",
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        comment="Document that established this relation",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional relation attributes",
    )

    # ── Relationships ─────────────────────────────────────────────
    source_entity: Mapped["KnowledgeEntity"] = relationship(  # noqa: F821
        "KnowledgeEntity",
        foreign_keys=[source_entity_id],
        back_populates="outgoing_relations",
    )
    target_entity: Mapped["KnowledgeEntity"] = relationship(  # noqa: F821
        "KnowledgeEntity",
        foreign_keys=[target_entity_id],
        back_populates="incoming_relations",
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeRelation id={self.id!r} "
            f"{self.source_entity_id!r} --[{self.relation_type}]--> {self.target_entity_id!r}>"
        )
