"""
Hybrid retriever — combines BM25 sparse search with dense vector search.

Implements C2 (Hybrid Retrieval) and C3 (Reciprocal Rank Fusion) from
the advanced RAG pipeline (TRD §4.3).

Pipeline:
  1. BM25 sparse search → top-K_bm25 results (token-based relevance)
  2. Dense vector search  → top-K_dense results (semantic similarity)
  3. Reciprocal Rank Fusion (RRF, k=60) → merged ranking

The BM25 index is built in-memory from the Qdrant collection payloads
on first use and cached for subsequent queries.
"""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.config import settings
from app.services.rag.embeddings import embed_query
from app.services.rag.vector_store import SearchResult, get_qdrant_store

logger = logging.getLogger(__name__)


# ── BM25 In-Memory Index ──────────────────────────────────────────────


@dataclass
class _BM25Index:
    """Simple BM25 index over document chunks stored in Qdrant."""

    # Mapping: chunk_id → (document_id, content, metadata)
    docs: dict[str, tuple[str, str, dict]] = field(default_factory=dict)
    # Inverted index: token → {chunk_id: term_frequency}
    inverted: dict[str, dict[str, float]] = field(default_factory=lambda: defaultdict(dict))
    # Document lengths: chunk_id → token count
    doc_lengths: dict[str, int] = field(default_factory=dict)
    # Average document length
    avg_dl: float = 0.0
    # Total document count
    n_docs: int = 0
    # IDF cache: token → idf value
    _idf_cache: dict[str, float] = field(default_factory=dict)

    # BM25 parameters
    k1: float = 1.5
    b: float = 0.75


_index: _BM25Index | None = None


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenization with stop-word removal."""
    text = text.lower().strip()
    tokens = re.split(r"[\s,.;:!?()\[\]{}\"'/\\]+", text)
    # Filter very short tokens and common stop words
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "shall",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "and",
        "but", "or", "nor", "not", "so", "yet", "both", "either",
        "neither", "each", "every", "all", "any", "few", "more",
        "most", "other", "some", "such", "no", "only", "own", "same",
        "than", "too", "very", "just", "because", "if", "when", "while",
        "that", "this", "these", "those", "it", "its", "he", "she",
        "they", "them", "we", "us", "i", "my", "your", "our",
    }
    return [t for t in tokens if len(t) > 1 and t not in stop_words]


async def _build_index() -> _BM25Index:
    """
    Build the BM25 index from Qdrant payloads.

    Scrolls through all points in the collection and builds the
    inverted index and document statistics.
    """
    global _index
    if _index is not None:
        return _index

    logger.info("Building BM25 index from Qdrant collection...")
    store = await get_qdrant_store()
    client = store._client

    idx = _BM25Index()

    # Scroll through all points to build the index
    offset = None
    total_scrolled = 0
    while True:
        results, offset = await client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            break

        for point in results:
            payload = point.payload or {}
            chunk_id = str(point.id)
            doc_id = payload.get("document_id", "")
            content = payload.get("chunk_text", "")
            metadata = {
                "source_file": payload.get("source_file", ""),
                "document_type": payload.get("document_type", ""),
                "page_number": payload.get("page_number"),
                "chunk_index": payload.get("chunk_index"),
            }

            idx.docs[chunk_id] = (doc_id, content, metadata)

            # Tokenize and build inverted index
            tokens = _tokenize(content)
            idx.doc_lengths[chunk_id] = len(tokens)

            # Term frequency (with sublinear TF: 1 + log(tf))
            tf_counts: dict[str, int] = defaultdict(int)
            for token in tokens:
                tf_counts[token] += 1
            for token, count in tf_counts.items():
                idx.inverted[token][chunk_id] = 1.0 + math.log(count)

            total_scrolled += 1

        if offset is None:
            break

    # Compute average document length
    idx.n_docs = len(idx.docs)
    if idx.n_docs > 0:
        idx.avg_dl = sum(idx.doc_lengths.values()) / idx.n_docs

    # Precompute IDF values
    n_docs_total = idx.n_docs
    for token, posting in idx.inverted.items():
        df = len(posting)
        idx._idf_cache[token] = math.log((n_docs_total - df + 0.5) / (df + 0.5) + 1.0)

    _index = idx
    logger.info(
        "BM25 index built: %d documents, %d unique tokens, avg_dl=%.1f",
        idx.n_docs,
        len(idx.inverted),
        idx.avg_dl,
    )
    return idx


def invalidate_index() -> None:
    """Invalidate the cached BM25 index (call after document ingestion)."""
    global _index
    _index = None
    logger.info("BM25 index invalidated")


async def bm25_search(
    query: str,
    *,
    top_k: int | None = None,
) -> list[SearchResult]:
    """
    Perform BM25 sparse retrieval against the in-memory index.

    Args:
        query: The user's query text.
        top_k: Maximum number of results.

    Returns:
        List of SearchResult objects scored by BM25.
    """
    effective_top_k = top_k or settings.RAG_BM25_TOP_K
    idx = await _build_index()

    if idx.n_docs == 0:
        logger.warning("BM25 index is empty — no results")
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    # Score each document
    scores: dict[str, float] = defaultdict(float)
    avg_dl = idx.avg_dl if idx.avg_dl > 0 else 1.0

    for token in query_tokens:
        if token not in idx.inverted:
            continue

        idf = idx._idf_cache.get(token, 0.0)
        posting = idx.inverted[token]

        for chunk_id, tf in posting.items():
            dl = idx.doc_lengths.get(chunk_id, 0)
            # BM25 score component
            numerator = tf * (idx.k1 + 1)
            denominator = tf + idx.k1 * (1 - idx.b + idx.b * dl / avg_dl)
            scores[chunk_id] += idf * numerator / denominator

    # Sort by score and return top-K
    sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results: list[SearchResult] = []

    for chunk_id, score in sorted_chunks[:effective_top_k]:
        doc_id, content, metadata = idx.docs[chunk_id]
        results.append(
            SearchResult(
                chunk_id=chunk_id,
                document_id=doc_id,
                content=content,
                score=score,
                metadata=metadata,
            )
        )

    logger.info("BM25 search: %d results for query (top score=%.4f)", len(results),
                results[0].score if results else 0.0)
    return results


# ── Reciprocal Rank Fusion ────────────────────────────────────────────


def reciprocal_rank_fusion(
    *rankings: list[SearchResult],
    k: int | None = None,
) -> list[SearchResult]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion (RRF).

    RRF score = sum(1 / (k + rank_i)) for each list where the document appears.
    This is a robust fusion method that doesn't require score normalization.

    Args:
        rankings: Variable number of ranked result lists.
        k: RRF constant (default: 60, per Cormack et al.)

    Returns:
        Merged list sorted by RRF score, deduplicated by chunk_id.
    """
    rrf_k = k or settings.RAG_RRF_K
    rrf_scores: dict[str, float] = defaultdict(float)
    chunk_map: dict[str, SearchResult] = {}

    for ranking in rankings:
        for rank, result in enumerate(ranking, start=1):
            rrf_scores[result.chunk_id] += 1.0 / (rrf_k + rank)
            if result.chunk_id not in chunk_map:
                chunk_map[result.chunk_id] = result

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    fused: list[SearchResult] = []
    for chunk_id in sorted_ids:
        result = chunk_map[chunk_id]
        # Update the score to the RRF fused score
        result.score = rrf_scores[chunk_id]
        fused.append(result)

    logger.info(
        "RRF fusion: %d lists → %d unique results (k=%d)",
        len(rankings),
        len(fused),
        rrf_k,
    )
    return fused


# ── Hybrid Search (BM25 + Dense + RRF) ───────────────────────────────


async def hybrid_search(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    document_id: str | None = None,
) -> list[SearchResult]:
    """
    Perform hybrid retrieval combining BM25 and dense vector search.

    Steps:
      1. Run BM25 sparse search → top-K_bm25
      2. Run dense vector search → top-K_dense
      3. Fuse results with RRF
      4. Return top results

    Args:
        query: The user's query text.
        top_k: Final number of results after fusion.
        min_score: Minimum score threshold for dense search.
        document_id: Optional document filter for dense search.

    Returns:
        Fused list of SearchResult objects.
    """
    import asyncio

    effective_top_k = top_k or (settings.RAG_BM25_TOP_K + settings.RAG_DENSE_TOP_K)
    effective_min_score = min_score if min_score is not None else settings.RAG_MIN_SCORE

    # Run BM25 and dense search in parallel
    dense_top_k = settings.RAG_DENSE_TOP_K
    bm25_top_k = settings.RAG_BM25_TOP_K

    # Dense search needs the query embedding
    query_vector = embed_query(query)
    store = await get_qdrant_store()

    dense_task = store.search(
        query_vector,
        top_k=dense_top_k,
        min_score=effective_min_score,
        document_id=document_id,
    )
    bm25_task = bm25_search(query, top_k=bm25_top_k)

    dense_results, bm25_results = await asyncio.gather(dense_task, bm25_task)

    logger.info(
        "Hybrid retrieval: %d dense + %d BM25 results",
        len(dense_results),
        len(bm25_results),
    )

    # If hybrid is disabled or one side is empty, return the other
    if not settings.RAG_HYBRID_ENABLED:
        return dense_results[:effective_top_k]

    if not bm25_results:
        return dense_results[:effective_top_k]

    if not dense_results:
        return bm25_results[:effective_top_k]

    # Fuse with RRF
    fused = reciprocal_rank_fusion(dense_results, bm25_results)
    return fused[:effective_top_k]
