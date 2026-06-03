"""
Qdrant vector store — manages collection lifecycle, upserts, and dense search.

Provides the interface between the embedding service and the Qdrant Cloud
instance for storing and retrieving document chunk embeddings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)

# Qdrant payload field names — single source of truth for payload keys
FIELD_DOCUMENT_ID = "document_id"
FIELD_SOURCE_FILE = "source_file"
FIELD_DOCUMENT_TYPE = "document_type"
FIELD_PAGE_NUMBER = "page_number"
FIELD_CHUNK_INDEX = "chunk_index"
FIELD_CONTENT_HASH = "content_hash"
FIELD_CHUNK_TEXT = "chunk_text"


@dataclass
class SearchResult:
    """A single search result from Qdrant."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class QdrantStore:
    """
    Async wrapper around QdrantClient for IDKP document operations.

    Usage:
        store = await QdrantStore.create()
        await store.upsert_chunks(doc_id, embeddings, payloads)
        results = await store.search(query_vector, top_k=5)
    """

    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    @classmethod
    async def create(cls) -> QdrantStore:
        """
        Create a QdrantStore and ensure the collection exists.

        Initialises the collection with the correct vector configuration
        and payload indexes if it does not already exist.
        """
        client = AsyncQdrantClient(
            url=settings.QDRANT_URL or None,
            api_key=settings.QDRANT_API_KEY or None,
            # Fallback to in-memory for local development when no URL is set
            **({"host": "localhost", "port": 6333} if not settings.QDRANT_URL else {}),
        )

        store = cls(client)
        await store._ensure_collection()
        return store

    # ── Collection Management ──────────────────────────────────────

    async def _ensure_collection(self) -> None:
        """Create the collection if it doesn't exist, with proper config."""
        collections = await self._client.get_collections()
        existing = [c.name for c in collections.collections]

        if settings.QDRANT_COLLECTION in existing:
            logger.info("Qdrant collection '%s' already exists", settings.QDRANT_COLLECTION)
            return

        await self._client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
                on_disk=False,
            ),
        )

        # Create payload indexes for filtering
        await self._client.create_payload_index(
            collection_name=settings.QDRANT_COLLECTION,
            field_name=FIELD_DOCUMENT_ID,
            field_schema=PayloadSchemaType.KEYWORD,
        )
        await self._client.create_payload_index(
            collection_name=settings.QDRANT_COLLECTION,
            field_name=FIELD_DOCUMENT_TYPE,
            field_schema=PayloadSchemaType.KEYWORD,
        )

        logger.info(
            "Created Qdrant collection '%s' (dim=%d)",
            settings.QDRANT_COLLECTION,
            settings.EMBEDDING_DIMENSION,
        )

    # ── Upsert ──────────────────────────────────────────────────────

    async def upsert_points(
        self,
        points: list[PointStruct],
    ) -> None:
        """
        Upsert a batch of points into the collection.

        Args:
            points: List of PointStruct objects with id, vector, and payload.
        """
        if not points:
            return

        await self._client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=points,
        )
        logger.info("Upserted %d points to Qdrant", len(points))

    # ── Search ────────────────────────────────────────────────────

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        min_score: float | None = None,
        document_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Perform dense vector search against the collection.

        Args:
            query_vector: The query embedding vector.
            top_k: Maximum number of results to return.
            min_score: Minimum cosine similarity score threshold.
            document_id: Optional filter to a specific document.

        Returns:
            List of SearchResult objects, ordered by descending score.
        """
        filters = None
        if document_id is not None:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            filters = Filter(
                must=[
                    FieldCondition(
                        key=FIELD_DOCUMENT_ID,
                        match=MatchValue(value=document_id),
                    )
                ],
            )

        query_results = await self._client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=min_score,
            query_filter=filters,
            with_payload=True,
        )

        results: list[SearchResult] = []
        for hit in query_results:
            payload = hit.payload or {}
            results.append(
                SearchResult(
                    chunk_id=str(hit.id),
                    document_id=payload.get(FIELD_DOCUMENT_ID, ""),
                    content=payload.get(FIELD_CHUNK_TEXT, ""),
                    score=hit.score,
                    metadata={
                        "source_file": payload.get(FIELD_SOURCE_FILE, ""),
                        "document_type": payload.get(FIELD_DOCUMENT_TYPE, ""),
                        "page_number": payload.get(FIELD_PAGE_NUMBER),
                        "chunk_index": payload.get(FIELD_CHUNK_INDEX),
                    },
                )
            )

        logger.info(
            "Qdrant search returned %d results (top_k=%d, min_score=%.2f)",
            len(results),
            top_k,
            min_score or 0.0,
        )
        return results

    # ── Deletion ───────────────────────────────────────────────────

    async def delete_by_document(self, document_id: str) -> None:
        """
        Delete all points belonging to a specific document.

        Used when a document is deleted or re-processed.
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        await self._client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key=FIELD_DOCUMENT_ID,
                        match=MatchValue(value=document_id),
                    )
                ],
            ),
        )
        logger.info("Deleted all Qdrant points for document %s", document_id)

    # ── Health Check ────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Verify the Qdrant client can reach the server."""
        try:
            await self._client.list_collections()
            return True
        except Exception:
            logger.exception("Qdrant health check failed")
            return False

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        await self._client.close()


# ── Module-level singleton ─────────────────────────────────────────

_qdrant_store: QdrantStore | None = None


async def get_qdrant_store() -> QdrantStore:
    """
    Get or create the singleton QdrantStore instance.

    Thread-safe for async context (single-threaded event loop).
    """
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = await QdrantStore.create()
    return _qdrant_store
