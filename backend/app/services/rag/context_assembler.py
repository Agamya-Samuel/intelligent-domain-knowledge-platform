"""
Context assembler — builds the final LLM prompt with verified, compressed context.

Orchestrates the full pre-generation pipeline:
  1. Relevance gate (Self-RAG) — filter low-quality chunks
  2. Context compression — deduplicate and truncate to token budget
  3. Multi-document reasoning — ensure source diversity
  4. Prompt assembly — format context blocks with citation metadata

This module is the final step before LLM generation, taking raw
retrieval results and producing a clean, verified prompt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.config import settings
from app.services.rag.retriever import RetrievalResult
from app.services.rag.vector_store import SearchResult

logger = logging.getLogger(__name__)


# ── Types ─────────────────────────────────────────────────────────────


@dataclass
class AssembledContext:
    """The fully assembled context ready for prompt construction."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    prompt: str = ""
    n_dropped_relevance: int = 0
    n_dropped_compression: int = 0
    n_sources: int = 0

    @property
    def has_context(self) -> bool:
        return len(self.results) > 0


# ── System Prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are an intelligent assistant for the Intelligent Domain Knowledge "
    "Platform (IDKP). Your task is to answer user questions based on the "
    "provided document context.\n\n"
    "Rules:\n"
    "1. Answer ONLY using the provided context. If the context doesn't "
    "contain relevant information, say so clearly.\n"
    "2. Always cite your sources by referencing the document name and "
    "page/section using [Source: filename, page X] notation.\n"
    "3. Be concise but thorough. Prioritize accuracy over completeness.\n"
    "4. If multiple context blocks are relevant, synthesize them into "
    "a coherent answer.\n"
    "5. Do not make up information. If you are unsure, state your uncertainty."
)


# ── Context Block Formatting ──────────────────────────────────────────

_CONTEXT_BLOCK_TEMPLATE = (
    "[Context {index}]\nSource: {source_file}\n{page_info}Content: {content}\n"
)

_USER_INSTRUCTION = (
    "\n---\n\n"
    "Based on the context blocks above, answer the following question. "
    "Reference your sources using [Source: filename, page X] notation.\n\n"
    "Question: {query}\n\n"
    "Answer:"
)


def _format_context_blocks(
    results: list[SearchResult],
    *,
    max_tokens: int | None = None,
) -> str:
    """Format retrieval results into context blocks for the prompt."""
    effective_max_tokens = max_tokens or settings.RAG_MAX_CONTEXT_TOKENS
    max_chars = effective_max_tokens * 4

    if not results:
        return ""

    parts: list[str] = []
    total_chars = 0

    for i, result in enumerate(results, start=1):
        page_info = ""
        page = result.metadata.get("page_number")
        if page is not None:
            page_info = f"Page: {page}\n"

        block = _CONTEXT_BLOCK_TEMPLATE.format(
            index=i,
            source_file=result.metadata.get("source_file", "Unknown"),
            page_info=page_info,
            content=result.content,
        )

        if total_chars + len(block) > max_chars:
            break

        parts.append(block)
        total_chars += len(block)

    return "\n".join(parts)


# ── Assembly Pipeline ─────────────────────────────────────────────────


async def assemble_context(
    retrieval: RetrievalResult,
    *,
    use_relevance_gate: bool = True,
    use_compression: bool = True,
    use_multi_doc: bool = True,
    max_context_tokens: int | None = None,
) -> AssembledContext:
    """
    Assemble verified, compressed context into a final prompt.

    Runs the full pre-generation pipeline:
      1. Relevance gate (filter low-quality chunks)
      2. Context compression (dedup + truncate)
      3. Multi-document reasoning (ensure diversity)
      4. Prompt assembly (format context blocks)

    Args:
        retrieval: Raw retrieval results.
        use_relevance_gate: Apply Self-RAG relevance gate.
        use_compression: Apply context compression.
        use_multi_doc: Apply multi-document reasoning.
        max_context_tokens: Override max context token budget.

    Returns:
        AssembledContext with the final prompt and metadata.
    """
    results = list(retrieval.results)
    n_initial = len(results)

    if not results:
        prompt = _USER_INSTRUCTION.format(query=retrieval.query)
        return AssembledContext(
            query=retrieval.query,
            results=[],
            prompt=prompt,
        )

    # Step 1: Relevance gate
    n_dropped_relevance = 0
    if use_relevance_gate and settings.RAG_RELEVANCE_GATE_ENABLED:
        from app.services.rag.self_rag import relevance_gate

        results = await relevance_gate(retrieval.query, results)
        n_dropped_relevance = n_initial - len(results)

    # Step 2: Context compression
    n_dropped_compression = 0
    if use_compression:
        from app.services.rag.self_rag import compress_context

        n_before_compression = len(results)
        results = await compress_context(
            results,
            max_tokens=max_context_tokens,
        )
        n_dropped_compression = n_before_compression - len(results)

    # Step 3: Multi-document reasoning
    if use_multi_doc:
        from app.services.rag.self_rag import multi_document_reasoning

        results = await multi_document_reasoning(retrieval.query, results)

    # Step 4: Format context blocks
    context_section = _format_context_blocks(
        results,
        max_tokens=max_context_tokens,
    )

    # Assemble final prompt
    if context_section:
        prompt = f"{context_section}{_USER_INSTRUCTION.format(query=retrieval.query)}"
    else:
        prompt = _USER_INSTRUCTION.format(query=retrieval.query)

    # Count unique sources
    sources = {r.document_id for r in results}

    assembled = AssembledContext(
        query=retrieval.query,
        results=results,
        prompt=prompt,
        n_dropped_relevance=n_dropped_relevance,
        n_dropped_compression=n_dropped_compression,
        n_sources=len(sources),
    )

    logger.info(
        "Context assembled: %d→%d chunks, %d sources, ~%d tokens "
        "(dropped: %d relevance, %d compression)",
        n_initial,
        len(results),
        len(sources),
        len(prompt) // 4,
        n_dropped_relevance,
        n_dropped_compression,
    )
    return assembled
