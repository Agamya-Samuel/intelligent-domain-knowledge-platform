"""
Prompt builder — assembles retrieved context into LLM prompts.

Constructs the RAG prompt with system instructions, retrieved context
blocks (with source metadata), and the user query. The format follows
the TRD §4.3 context assembly specification.

Baseline prompt structure:
    [System Prompt — domain-specific instructions]
    [Retrieved Context Block 1 — with source metadata]
    [Retrieved Context Block 2 — with source metadata]
    ...
    [Retrieved Context Block N — max N=5]
    [User Query]
    [Instruction: Answer with citations]
"""

from __future__ import annotations

import logging

from app.services.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)

# ── System prompt templates ────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = (
    "You are an intelligent assistant for the Intelligent Domain Knowledge Platform (IDKP). "
    "Your task is to answer user questions based on the provided document context.\n\n"
    "Rules:\n"
    "1. Answer ONLY using the provided context. If the context doesn't contain relevant "
    "information, say so clearly.\n"
    "2. Always cite your sources by referencing the document name and page/section.\n"
    "3. Be concise but thorough. Prioritize accuracy over completeness.\n"
    "4. If multiple context blocks are relevant, synthesize them into a coherent answer.\n"
)

# ── Context block template ─────────────────────────────────────────

_CONTEXT_BLOCK_TEMPLATE = (
    "[Context {index}]\nSource: {source_file}\n{page_info}Content: {content}\n"
)

# ── User instruction template ────────────────────────────────────────

_USER_INSTRUCTION = (
    "\n---\n\n"
    "Based on the context blocks above, answer the following question. "
    "Reference your sources using [Source: filename, page X] notation.\n\n"
    "Question: {query}\n\n"
    "Answer:"
)


def build_rag_prompt(
    retrieval: RetrievalResult,
    *,
    system_prompt: str | None = None,
    max_context_tokens: int | None = None,
) -> str:
    """
    Assemble a RAG prompt from retrieval results.

    Constructs the full user prompt with retrieved context blocks
    formatted with source metadata for citation support.

    Args:
        retrieval: The retrieval result containing search hits.
        system_prompt: Optional custom system prompt (uses default if None).
        max_context_tokens: Max context tokens to include (defaults to settings).

    Returns:
        The assembled user prompt string (excluding system prompt).
    """
    from app.config import settings

    effective_max_tokens = max_context_tokens or settings.RAG_MAX_CONTEXT_TOKENS
    _ = system_prompt or DEFAULT_SYSTEM_PROMPT  # reserved for Phase 2 system prompt injection

    if not retrieval.has_results:
        logger.info("No retrieval results — building no-context prompt")
        return f"{_USER_INSTRUCTION.format(query=retrieval.query)}"

    # Build context blocks
    context_parts: list[str] = []
    total_chars = 0
    max_chars = effective_max_tokens * 4  # approximate char limit

    for i, result in enumerate(retrieval.results, start=1):
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

        # Check if adding this block would exceed context limit
        if total_chars + len(block) > max_chars:
            logger.info(
                "Context truncated at block %d/%d (char limit reached)",
                i,
                len(retrieval.results),
            )
            break

        context_parts.append(block)
        total_chars += len(block)

    context_section = "\n".join(context_parts)
    prompt = f"{context_section}{_USER_INSTRUCTION.format(query=retrieval.query)}"

    logger.info(
        "RAG prompt assembled: %d context blocks, ~%d chars",
        len(context_parts),
        len(prompt),
    )
    return prompt


def extract_citations(retrieval: RetrievalResult) -> list[dict[str, str | int | None]]:
    """
    Extract citation metadata from retrieval results.

    Returns a list of citation dicts suitable for SSE events.

    Each citation has: source (filename), page (optional), section (optional).
    """
    citations: list[dict[str, str | int | None]] = []
    for result in retrieval.results:
        citation = {
            "source": result.metadata.get("source_file", "Unknown"),
            "page": result.metadata.get("page_number"),
        }
        citations.append(citation)

    return citations
