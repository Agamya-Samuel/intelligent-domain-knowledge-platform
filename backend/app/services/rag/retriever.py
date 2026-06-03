"""
RAG retriever — orchestrates embedding generation and vector search.

Coordinates the embedding service and Qdrant vector store to perform
the retrieval step of the RAG pipeline.

Flow: query → embed_query → Qdrant.search → top-K chunks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.config import settings
from app.services.rag.embeddings import embed_query
from app.services.rag.vector_store import SearchResult, get_qdrant_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result of a RAG retrieval operation."""

    query: str
    results: list[SearchResult] = field(default_factory=list)

    @property
    def context_texts(self) -> list[str]:
        """Return just the content texts from search results."""
        return [r.content for r in self.results]

    @property
    def total_tokens_estimate(self) -> int:
        """Estimate total token count of retrieved context (4 chars ≈ 1 token)."""
        return sum(len(r.content) // 4 for r in self.results)

    @property
    def has_results(self) -> bool:
        """Check if any results were found."""
        return len(self.results) > 0


async def retrieve(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    document_id: str | None = None,
) -> RetrievalResult:
    """
    Retrieve relevant document chunks for a query using dense vector search.

    This is the baseline RAG retrieval — dense search only, no reranking,
    no query expansion. Advanced RAG components are added in Phase 3 (Week 8-9).

    Args:
        query: The user's question or query text.
        top_k: Maximum number of results (defaults to settings.RAG_TOP_K).
        min_score: Minimum cosine similarity score (defaults to settings.RAG_MIN_SCORE).
        document_id: Optional filter to search within a specific document.

    Returns:
        RetrievalResult containing ranked search results.

    Raises:
        RuntimeError: If embedding generation or Qdrant search fails.
    """
    effective_top_k = top_k or settings.RAG_TOP_K
    effective_min_score = min_score if min_score is not None else settings.RAG_MIN_SCORE

    try:
        # Step 1: Embed the query
        logger.info("Embedding query: %.100s...", query)
        query_vector = embed_query(query)

        # Step 2: Search Qdrant
        store = await get_qdrant_store()
        logger.info(
            "Searching Qdrant: top_k=%d, min_score=%.2f",
            effective_top_k,
            effective_min_score,
        )
        results = await store.search(
            query_vector,
            top_k=effective_top_k,
            min_score=effective_min_score,
            document_id=document_id,
        )

        retrieval = RetrievalResult(query=query, results=results)

        logger.info(
            "Retrieval complete: %d results for query (%d estimated tokens)",
            len(results),
            retrieval.total_tokens_estimate,
        )
        return retrieval

    except Exception as exc:
        logger.exception("RAG retrieval failed for query: %.100s", query)
        raise RuntimeError(f"RAG retrieval failed: {exc}") from exc
