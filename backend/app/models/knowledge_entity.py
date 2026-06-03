"""KnowledgeEntity model — extracted entities/nodes for the knowledge graph."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class KnowledgeEntity(Base, TimestampMixin):
    """
    An entity extracted from documents — a node in the knowledge graph.

    Entity types include: person, organization, concept, technology,
    location, event, product, and custom types.
    """

    __tablename__ = "knowledge_entities"

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
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="person, org, concept, tech, etc.",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_doc_ids: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(36)),
        nullable=True,
        comment="Document IDs that mention this entity",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional entity attributes",
    )

    # ── Relationships ─────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="knowledge_entities")  # noqa: F821
    outgoing_relations: Mapped[list["KnowledgeRelation"]] = relationship(  # noqa: F821
        "KnowledgeRelation",
        foreign_keys="KnowledgeRelation.source_entity_id",
        back_populates="source_entity",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    incoming_relations: Mapped[list["KnowledgeRelation"]] = relationship(  # noqa: F821
        "KnowledgeRelation",
        foreign_keys="KnowledgeRelation.target_entity_id",
        back_populates="target_entity",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeEntity id={self.id!r} name={self.name!r} type={self.entity_type!r}>"
