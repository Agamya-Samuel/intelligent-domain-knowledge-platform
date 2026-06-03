"""
Query expansion — HyDE and multi-query generation for improved recall.

Implements C5 (HyDE Query Expansion) and C6 (Multi-query Generation)
from the advanced RAG pipeline (TRD §4.3).

HyDE (Hypothetical Document Embeddings):
  1. Generate a hypothetical answer to the user's query using the LLM
  2. Embed the hypothetical answer (which is closer to document language)
  3. Use that embedding for retrieval instead of the raw query

Multi-query Generation:
  1. Ask the LLM to generate N variant phrasings of the same query
  2. Run retrieval for each variant
  3. Deduplicate and merge results

Both strategies can be used independently or together.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.services.rag.embeddings import embed_query
from app.services.rag.llm_client import generate

logger = logging.getLogger(__name__)


# ── HyDE ──────────────────────────────────────────────────────────────

_HYDE_PROMPT = (
    "You are a helpful assistant. Given the user's question, write a brief "
    "hypothetical answer paragraph (3-5 sentences) that could appear in a "
    "document answering this question. Focus on the key concepts and terminology "
    "that would appear in relevant documents.\n\n"
    "Question: {query}\n\n"
    "Hypothetical answer:"
)


async def hyde_expand(query: str) -> tuple[str, list[float]]:
    """
    Generate a HyDE (Hypothetical Document Embedding) for the query.

    Uses the LLM to generate a hypothetical answer, then embeds it.
    The hypothetical answer embedding is often closer to relevant document
    chunks than the raw query embedding.

    Args:
        query: The user's original query.

    Returns:
        Tuple of (hypothetical_answer_text, embedding_vector).
    """
    try:
        # Generate hypothetical answer with low temperature for factual tone
        response = await generate(
            _HYDE_PROMPT.format(query=query),
            max_tokens=256,
            temperature=0.0,
        )

        hypothetical_answer = response.content.strip()

        if not hypothetical_answer:
            logger.warning("HyDE generation returned empty — using original query")
            return query, embed_query(query)

        # Embed the hypothetical answer
        hyde_vector = embed_query(hypothetical_answer)

        logger.info(
            "HyDE expansion generated: %.100s...",
            hypothetical_answer,
        )
        return hypothetical_answer, hyde_vector

    except Exception as exc:
        logger.warning("HyDE expansion failed — using original query: %s", exc)
        return query, embed_query(query)


# ── Multi-query Generation ────────────────────────────────────────────

_MULTI_QUERY_PROMPT = (
    "You are a helpful assistant. Generate {n} different search queries that "
    "capture the same information need as the original query. Each variant "
    "should use different wording, synonyms, or perspectives while preserving "
    "the core intent.\n\n"
    "Original query: {query}\n\n"
    "Generate {n} variant queries, one per line, numbered:\n"
    "1. \n"
    "2. \n"
    "3. \n"
)


async def generate_multi_queries(
    query: str,
    *,
    n: int | None = None,
) -> list[str]:
    """
    Generate multiple query variants for diversified retrieval.

    Uses the LLM to create different phrasings of the same query,
    which helps retrieve documents that may use different terminology.

    Args:
        query: The original user query.
        n: Number of variants to generate (defaults to RAG_MULTI_QUERY_COUNT).

    Returns:
        List of query strings (including the original).
    """
    effective_n = n or settings.RAG_MULTI_QUERY_COUNT

    try:
        response = await generate(
            _MULTI_QUERY_PROMPT.format(query=query, n=effective_n),
            max_tokens=256,
            temperature=0.7,
        )

        # Parse numbered variants from the response
        variants: list[str] = [query]  # always include original
        for line in response.content.strip().split("\n"):
            line = line.strip()
            # Match numbered lines like "1. query text" or "1) query text"
            if line and (line[0].isdigit()):
                # Remove the number prefix
                import re

                cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
                if cleaned and cleaned != query and len(cleaned) > 5:
                    variants.append(cleaned)

        # Trim to requested count (original + n-1 variants)
        variants = variants[: effective_n + 1]

        logger.info(
            "Multi-query generated %d variants from: %.60s...",
            len(variants),
            query,
        )
        return variants

    except Exception as exc:
        logger.warning("Multi-query generation failed — using original query only: %s", exc)
        return [query]


# ── Combined Expansion ────────────────────────────────────────────────


async def expand_query(
    query: str,
) -> tuple[list[str], list[list[float]]]:
    """
    Apply all enabled query expansion strategies.

    Returns all query texts and their embedding vectors for use in
    the retrieval pipeline.

    Args:
        query: The original user query.

    Returns:
        Tuple of (list_of_queries, list_of_embedding_vectors).
    """
    queries: list[str] = [query]
    vectors: list[list[float]] = [embed_query(query)]

    # HyDE expansion
    if settings.RAG_HYDE_ENABLED:
        hyde_text, hyde_vector = await hyde_expand(query)
        if hyde_text != query:
            queries.append(hyde_text)
            vectors.append(hyde_vector)

    # Multi-query expansion
    if settings.RAG_MULTI_QUERY_ENABLED:
        multi_variants = await generate_multi_queries(query)
        for variant in multi_variants:
            if variant not in queries:
                queries.append(variant)
                vectors.append(embed_query(variant))

    logger.info(
        "Query expansion: %d total queries (HyDE=%s, multi_query=%s)",
        len(queries),
        settings.RAG_HYDE_ENABLED,
        settings.RAG_MULTI_QUERY_ENABLED,
    )
    return queries, vectors
