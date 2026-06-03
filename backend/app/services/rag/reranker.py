"""
Cross-encoder reranker — re-scores retrieval candidates with BGE-Reranker.

Uses a cross-encoder model (BGE-Reranker-v2-m3) to compute fine-grained
relevance scores for (query, passage) pairs.  The cross-encoder is more
accurate than the bi-encoder embedding similarity used in the initial
retrieval step, but much slower — so it runs only on the top candidates
from the hybrid retrieval stage.

Deployment options:
  1. Local: load the model via sentence-transformers (CPU or CUDA)
  2. Modal T4: offload reranking to a Modal function (≤ 500 ms for 20 cands)

The interface is the same regardless of backend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


# ── Types ─────────────────────────────────────────────────────────────


@dataclass
class RerankCandidate:
    """A single passage to be reranked against a query."""

    chunk_id: str
    document_id: str
    content: str
    score: float  # score from the previous retrieval stage
    metadata: dict


# ── Local cross-encoder (lazy singleton) ──────────────────────────────

_cross_encoder = None


def _get_cross_encoder():
    """Lazy-load the cross-encoder model for local inference."""
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        logger.info("Loading cross-encoder reranker: %s", settings.RAG_RERANKER_MODEL)
        _cross_encoder = CrossEncoder(
            settings.RAG_RERANKER_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        logger.info("Cross-encoder reranker loaded successfully")
    return _cross_encoder


# ── Public API ─────────────────────────────────────────────────────────


async def rerank(
    query: str,
    candidates: list[RerankCandidate],
    *,
    top_k: int | None = None,
) -> list[RerankCandidate]:
    """
    Rerank retrieval candidates using the cross-encoder model.

    Computes (query, passage) relevance scores and returns the top-K
    candidates sorted by the new cross-encoder score.

    Args:
        query: The user's query text.
        candidates: List of retrieval candidates from hybrid search.
        top_k: Number of top results to return (defaults to RAG_RERANKER_TOP_K).

    Returns:
        Re-sorted list of candidates with updated scores.
    """
    effective_top_k = top_k or settings.RAG_RERANKER_TOP_K

    if not candidates:
        return []

    if not settings.RAG_RERANKER_ENABLED:
        logger.info("Reranker disabled — returning candidates as-is")
        return candidates[:effective_top_k]

    try:
        # Build (query, passage) pairs for the cross-encoder
        pairs = [(query, c.content) for c in candidates]

        # Score all pairs with the cross-encoder
        model = _get_cross_encoder()
        ce_scores = model.predict(pairs, show_progress_bar=False)

        # Update candidate scores with cross-encoder scores
        scored_candidates = []
        for candidate, ce_score in zip(candidates, ce_scores):
            # Normalise cross-encoder score (sigmoid for models that output logits)
            import math

            normalised = 1.0 / (1.0 + math.exp(-float(ce_score)))
            candidate.score = normalised
            scored_candidates.append(candidate)

        # Sort by cross-encoder score descending
        scored_candidates.sort(key=lambda c: c.score, reverse=True)

        result = scored_candidates[:effective_top_k]

        logger.info(
            "Reranking complete: %d → %d candidates (top score=%.4f)",
            len(candidates),
            len(result),
            result[0].score if result else 0.0,
        )
        return result

    except Exception as exc:
        logger.exception("Cross-encoder reranking failed — falling back to original ranking")
        # Fallback: return original top-K without reranking
        return candidates[:effective_top_k]
