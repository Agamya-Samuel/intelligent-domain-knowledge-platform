"""
Embedding service — generates vector embeddings using sentence-transformers.

Loads a BGE-M3 model locally for embedding text chunks and queries.
In production v1, this will be replaced by Modal T4 embedding calls,
but the interface remains the same.

Design note: The model is loaded once as a module-level singleton and reused
across all requests to avoid re-loading the 2.2 GB weights.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

# ── Module-level singleton ─────────────────────────────────────────

_model = None


def _get_model():
    """
    Lazy-load the sentence-transformer model.

    Thread-safe for single-threaded async event loops.
    The model is loaded once and reused for all subsequent calls.
    """
    global _model
    if _model is None:
        if not settings.EMBEDDING_MODEL:
            raise RuntimeError(
                "EMBEDDING_MODEL not configured. Set EMBEDDING_MODEL in .env or use Modal embeddings in production."
            )
        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        logger.info(
            "Embedding model loaded: %s (dim=%d, device=%s)",
            settings.EMBEDDING_MODEL,
            settings.EMBEDDING_DIMENSION,
            settings.EMBEDDING_DEVICE,
        )
    return _model


# ── Public API ──────────────────────────────────────────────────────


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts into dense vectors.

    Uses BGE-M3 with normalized embeddings for cosine similarity.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of float vectors, one per input text.
    """
    if not texts:
        return []

    model = _get_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32,
    )
    # Convert numpy array to list of lists
    return [emb.tolist() for emb in embeddings]


def embed_query(text: str) -> list[float]:
    """
    Embed a single query text into a dense vector.

    BGE-M3 supports prefix-based query/text distinction, but for the
    baseline RAG we use the same encoding for both.

    Args:
        text: The query string.

    Returns:
        A single float vector.
    """
    model = _get_model()
    embedding = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embedding.tolist()


def get_embedding_dimension() -> int:
    """Return the dimensionality of the embedding vectors."""
    return settings.EMBEDDING_DIMENSION
