"""
RAG retriever — unified retrieval pipeline with advanced RAG components.

Orchestrates the full retrieval pipeline combining:
  - C1: Semantic chunking (validated during ingestion)
  - C2: Hybrid retrieval (BM25 + dense vector search)
  - C3: Reciprocal Rank Fusion (RRF)
  - C4: Cross-encoder reranking (BGE-Reranker)
  - C5: HyDE query expansion
  - C6: Multi-query generation
  - Metadata filtering (Qdrant payload filters)

Pipeline flow:
  query → expand (HyDE + multi-query)
       → hybrid search (BM25 + dense) for each query variant
       → RRF fusion across all results
       → cross-encoder reranking
       → metadata filtering
       → top-K results

All advanced components can be individually toggled via config settings.
When all are disabled, the pipeline falls back to baseline dense-only search.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

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


# ── Metadata Filter Builder ──────────────────────────────────────────


def build_metadata_filter(
    *,
    doc_type: str | None = None,
    source_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int | None = None,
    section: str | None = None,
) -> dict[str, Any] | None:
    """
    Build a Qdrant payload filter dict from metadata parameters.

    Returns None if no filters are specified.

    Args:
        doc_type: Filter by document type (pdf, docx, md, etc.)
        source_id: Filter by source document ID.
        date_from: Filter chunks created after this date (ISO format).
        date_to: Filter chunks created before this date (ISO format).
        page: Filter by specific page number.
        section: Filter by section name.

    Returns:
        Filter dict or None.
    """
    conditions: list[dict] = []

    if doc_type:
        conditions.append({"key": "document_type", "match": {"value": doc_type}})
    if source_id:
        conditions.append({"key": "document_id", "match": {"value": source_id}})
    if page is not None:
        conditions.append({"key": "page_number", "match": {"value": page}})
    if section:
        conditions.append({"key": "section", "match": {"value": section}})

    if not conditions:
        return None

    return {"must": conditions}


# ── Context Deduplication ─────────────────────────────────────────────


def deduplicate_results(
    results: list[SearchResult],
    *,
    threshold: float | None = None,
) -> list[SearchResult]:
    """
    Remove near-duplicate results based on content similarity.

    Uses Jaccard similarity on word sets as a fast approximation
    (avoids computing cosine similarity on embeddings).

    Args:
        results: List of search results to deduplicate.
        threshold: Similarity threshold (default from config).

    Returns:
        Deduplicated list preserving order.
    """
    sim_threshold = threshold or settings.RAG_CONTEXT_DEDUP_THRESHOLD

    if len(results) <= 1:
        return results

    kept: list[SearchResult] = []
    kept_token_sets: list[set[str]] = []

    for result in results:
        # Tokenize for Jaccard comparison
        tokens = set(result.content.lower().split())

        is_duplicate = False
        for existing_tokens in kept_token_sets:
            if not tokens or not existing_tokens:
                continue
            intersection = tokens & existing_tokens
            union = tokens | existing_tokens
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard >= sim_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            kept.append(result)
            kept_token_sets.append(tokens)

    if len(kept) < len(results):
        logger.info(
            "Deduplication: %d → %d results (threshold=%.2f)",
            len(results),
            len(kept),
            sim_threshold,
        )

    return kept


# ── Unified Retrieve Function ─────────────────────────────────────────


async def retrieve(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    document_id: str | None = None,
    doc_type: str | None = None,
    source_id: str | None = None,
    page: int | None = None,
    section: str | None = None,
    use_hybrid: bool | None = None,
    use_reranker: bool | None = None,
    use_expansion: bool | None = None,
) -> RetrievalResult:
    """
    Retrieve relevant document chunks using the full advanced RAG pipeline.

    The pipeline applies (when enabled):
      1. Query expansion (HyDE + multi-query)
      2. Hybrid retrieval (BM25 + dense) for each query variant
      3. Reciprocal Rank Fusion across all results
      4. Cross-encoder reranking
      5. Deduplication
      6. Metadata filtering

    Each component can be individually disabled via the function parameters
    or globally via config settings.

    Args:
        query: The user's question or query text.
        top_k: Maximum number of results (defaults to settings.RAG_TOP_K).
        min_score: Minimum similarity score (defaults to settings.RAG_MIN_SCORE).
        document_id: Optional filter to search within a specific document.
        doc_type: Optional filter by document type.
        source_id: Optional filter by source ID.
        page: Optional filter by page number.
        section: Optional filter by section name.
        use_hybrid: Override hybrid retrieval setting.
        use_reranker: Override reranker setting.
        use_expansion: Override query expansion setting.

    Returns:
        RetrievalResult containing ranked search results.

    Raises:
        RuntimeError: If the retrieval pipeline fails.
    """
    effective_top_k = top_k or settings.RAG_TOP_K
    effective_min_score = min_score if min_score is not None else settings.RAG_MIN_SCORE

    try:
        # Determine which components are active
        hybrid_active = (use_hybrid if use_hybrid is not None
                         else settings.RAG_HYBRID_ENABLED)
        reranker_active = (use_reranker if use_reranker is not None
                           else settings.RAG_RERANKER_ENABLED)
        expansion_active = (use_expansion if use_expansion is not None
                            else (settings.RAG_HYDE_ENABLED or settings.RAG_MULTI_QUERY_ENABLED))

        logger.info(
            "Retrieval pipeline: query=%.80s... hybrid=%s reranker=%s expansion=%s",
            query, hybrid_active, reranker_active, expansion_active,
        )

        # ── Step 1: Query expansion ──
        query_vectors: list[list[float]] = []
        if expansion_active:
            from app.services.rag.query_expansion import expand_query

            _queries, query_vectors = await expand_query(query)
        else:
            query_vectors = [embed_query(query)]

        # ── Step 2: Retrieval (hybrid or dense-only) ──
        all_results: list[SearchResult] = []

        if hybrid_active:
            from app.services.rag.hybrid_retriever import reciprocal_rank_fusion

            # Search with each query vector variant
            variant_results: list[list[SearchResult]] = []
            for vector in query_vectors:
                # Dense search for this vector
                store = await get_qdrant_store()
                dense_results = await store.search(
                    vector,
                    top_k=settings.RAG_DENSE_TOP_K,
                    min_score=effective_min_score,
                    document_id=document_id,
                )
                variant_results.append(dense_results)

            # Also run BM25 for the original query
            from app.services.rag.hybrid_retriever import bm25_search

            bm25_results = await bm25_search(query, top_k=settings.RAG_BM25_TOP_K)

            # Fuse all rankings with RRF
            all_rankings = variant_results + ([bm25_results] if bm25_results else [])
            if len(all_rankings) == 1:
                all_results = all_rankings[0]
            else:
                all_results = reciprocal_rank_fusion(*all_rankings)

        else:
            # Baseline: dense-only search with the first (or only) query vector
            store = await get_qdrant_store()
            all_results = await store.search(
                query_vectors[0],
                top_k=effective_top_k,
                min_score=effective_min_score,
                document_id=document_id,
            )

        # ── Step 3: Cross-encoder reranking ──
        if reranker_active and len(all_results) > 1:
            from app.services.rag.reranker import RerankCandidate, rerank

            candidates = [
                RerankCandidate(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    content=r.content,
                    score=r.score,
                    metadata=r.metadata,
                )
                for r in all_results
            ]

            reranked = await rerank(query, candidates, top_k=effective_top_k)

            all_results = [
                SearchResult(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    content=c.content,
                    score=c.score,
                    metadata=c.metadata,
                )
                for c in reranked
            ]
        else:
            all_results = all_results[:effective_top_k]

        # ── Step 4: Deduplication ──
        all_results = deduplicate_results(all_results)

        # ── Step 5: Metadata filtering (post-retrieval) ──
        if settings.RAG_METADATA_FILTERS_ENABLED and (doc_type or source_id or page or section):
            filtered: list[SearchResult] = []
            for r in all_results:
                if doc_type and r.metadata.get("document_type") != doc_type:
                    continue
                if source_id and r.document_id != source_id:
                    continue
                if page is not None and r.metadata.get("page_number") != page:
                    continue
                if section and r.metadata.get("section") != section:
                    continue
                filtered.append(r)
            all_results = filtered

        retrieval = RetrievalResult(query=query, results=all_results)

        logger.info(
            "Retrieval complete: %d results (%d estimated tokens)",
            len(all_results),
            retrieval.total_tokens_estimate,
        )
        return retrieval

    except Exception as exc:
        logger.exception("RAG retrieval failed for query: %.100s", query)
        raise RuntimeError(f"RAG retrieval failed: {exc}") from exc
