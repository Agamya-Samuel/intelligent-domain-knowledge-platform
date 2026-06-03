"""
IDKP ORM models — import all models here so Alembic can discover them.

Usage in alembic/env.py:
    from app.models import *  # noqa: F401
"""

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_entity import KnowledgeEntity
from app.models.knowledge_relation import KnowledgeRelation
from app.models.user import User

__all__ = [
    "Document",
    "DocumentChunk",
    "KnowledgeEntity",
    "KnowledgeRelation",
    "User",
]
