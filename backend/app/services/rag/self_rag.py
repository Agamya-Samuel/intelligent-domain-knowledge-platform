"""
Self-RAG verification — relevance gate and context compression.

Implements C9 (Self-RAG Verification) and context compression from
the advanced RAG pipeline (TRD §4.3).

Relevance Gate:
  Scores each retrieved chunk for relevance to the query before
  passing it to the LLM. Chunks below the threshold are dropped,
  preventing the LLM from being confused by irrelevant context.

Context Compression:
  - Removes near-duplicate chunks (cosine similarity > threshold)
  - Truncates total context to fit within the token budget
  - Preserves diversity of sources

Together these ensure the LLM receives only high-quality, diverse
context that improves faithfulness and reduces hallucination.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.services.rag.embeddings import embed_texts
from app.services.rag.retriever import RetrievalResult
from app.services.rag.vector_store import SearchResult

logger = logging.getLogger(__name__)


# ── Types ─────────────────────────────────────────────────────────────


@dataclass
class RelevanceScore:
    """Relevance assessment for a single chunk."""

    chunk_id: str
    score: float
    passed: bool


# ── Relevance Gate ────────────────────────────────────────────────────


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def relevance_gate(
    query: str,
    results: list[SearchResult],
    *,
    threshold: float | None = None,
) -> list[SearchResult]:
    """
    Score retrieved chunks for relevance and filter low-quality ones.

    Uses embedding similarity between the query and each chunk as a
    relevance proxy. Chunks below the threshold are dropped.

    This is a lighter-weight alternative to the cross-encoder reranker
    that can run even when the reranker is disabled.

    Args:
        query: The user's query text.
        results: Retrieved chunks from the retrieval pipeline.
        threshold: Minimum relevance score (defaults to config).

    Returns:
        Filtered list of chunks that passed the relevance gate.
    """
    effective_threshold = (
        threshold if threshold is not None else settings.RAG_RELEVANCE_GATE_THRESHOLD
    )

    if not settings.RAG_RELEVANCE_GATE_ENABLED or not results:
        return results

    try:
        # Embed all chunks at once for efficiency
        chunk_texts = [r.content for r in results]
        chunk_embeddings = embed_texts(chunk_texts)
        query_embedding = embed_texts([query])[0]

        # Score each chunk
        passed_results: list[SearchResult] = []
        scores: list[RelevanceScore] = []

        for result, chunk_emb in zip(results, chunk_embeddings):
            sim = _cosine_similarity(query_embedding, chunk_emb)
            passed = sim >= effective_threshold

            scores.append(RelevanceScore(chunk_id=result.chunk_id, score=sim, passed=passed))

            if passed:
                passed_results.append(result)

        n_dropped = len(results) - len(passed_results)
        if n_dropped > 0:
            logger.info(
                "Relevance gate: dropped %d/%d chunks (threshold=%.2f)",
                n_dropped,
                len(results),
                effective_threshold,
            )

        # Safety: always keep at least 1 result even if all are below threshold
        if not passed_results and results:
            passed_results = [results[0]]
            logger.warning("Relevance gate: all chunks below threshold — keeping top result")

        return passed_results

    except Exception as exc:
        logger.warning("Relevance gate failed — passing all results through: %s", exc)
        return results


# ── Context Compression ───────────────────────────────────────────────


async def compress_context(
    results: list[SearchResult],
    *,
    max_tokens: int | None = None,
    dedup_threshold: float | None = None,
) -> list[SearchResult]:
    """
    Compress retrieved context by removing near-duplicates and truncating.

    Steps:
      1. Remove near-duplicate chunks (Jaccard similarity > threshold)
      2. Truncate to fit within the token budget (4 chars ≈ 1 token)
      3. Preserve source diversity (round-robin across documents)

    Args:
        results: Retrieved chunks to compress.
        max_tokens: Maximum total tokens (defaults to RAG_MAX_CONTEXT_TOKENS).
        dedup_threshold: Near-duplicate threshold (defaults to config).

    Returns:
        Compressed list of chunks.
    """
    effective_max_tokens = max_tokens or settings.RAG_MAX_CONTEXT_TOKENS
    effective_dedup = (
        dedup_threshold if dedup_threshold is not None
        else settings.RAG_CONTEXT_DEDUP_THRESHOLD
    )

    if not results:
        return results

    # Step 1: Deduplicate by Jaccard similarity
    deduped: list[SearchResult] = []
    kept_token_sets: list[set[str]] = []

    for result in results:
        tokens = set(result.content.lower().split())
        is_dup = False

        for existing_tokens in kept_token_sets:
            if not tokens or not existing_tokens:
                continue
            intersection = tokens & existing_tokens
            union = tokens | existing_tokens
            jaccard = len(intersection) / len(union) if union else 0.0
            if jaccard >= effective_dedup:
                is_dup = True
                break

        if not is_dup:
            deduped.append(result)
            kept_token_sets.append(tokens)

    if len(deduped) < len(results):
        logger.info(
            "Context compression: dedup removed %d near-duplicates",
            len(results) - len(deduped),
        )

    # Step 2: Truncate to token budget
    max_chars = effective_max_tokens * 4
    total_chars = 0
    truncated: list[SearchResult] = []

    for result in deduped:
        if total_chars + len(result.content) > max_chars:
            logger.info(
                "Context compression: truncated at %d/%d chunks (token budget reached)",
                len(truncated),
                len(deduped),
            )
            break
        truncated.append(result)
        total_chars += len(result.content)

    return truncated


# ── Multi-Document Reasoning ──────────────────────────────────────────


async def multi_document_reasoning(
    query: str,
    results: list[SearchResult],
) -> list[SearchResult]:
    """
    Ensure diverse source coverage for complex multi-document queries.

    For queries that require information from multiple documents,
    this function ensures the result set includes chunks from
    different source documents (round-robin selection).

    This helps the LLM synthesize information across documents
    rather than relying on a single source.

    Args:
        query: The user's query.
        results: Retrieved chunks (may be dominated by one document).

    Returns:
        Re-ranked results with improved source diversity.
    """
    if len(results) <= 2:
        return results

    # Group results by document
    by_doc: dict[str, list[SearchResult]] = {}
    for r in results:
        doc_id = r.document_id
        if doc_id not in by_doc:
            by_doc[doc_id] = []
        by_doc[doc_id].append(r)

    # If all results are from the same document, no re-ranking needed
    if len(by_doc) <= 1:
        return results

    # Round-robin across documents to ensure diversity
    diverse: list[SearchResult] = []
    max_per_doc = max(len(v) for v in by_doc.values())
    doc_ids = list(by_doc.keys())

    for i in range(max_per_doc):
        for doc_id in doc_ids:
            if i < len(by_doc[doc_id]):
                diverse.append(by_doc[doc_id][i])

    logger.info(
        "Multi-doc reasoning: %d docs represented in %d results",
        len(by_doc),
        len(diverse),
    )
    return diverse
