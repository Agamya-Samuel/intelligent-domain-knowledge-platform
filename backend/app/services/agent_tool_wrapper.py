"""Agent tool wrapper — exposes the IDKP RAG pipeline as a callable tool interface.

Provides adapters for:
  - LangChain: BaseTool subclass via ``as_langchain_tool()``
  - LlamaIndex: FunctionTool via ``as_llamaindex_tool()``
  - Raw callable: ``IDKPTool(query)`` for custom agent frameworks

The tool runs the full 9-component RAG pipeline:
    1. Query expansion (HyDE + multi-query)
    2. Hybrid retrieval (BM25 sparse + dense)
    3. RRF fusion
    4. Cross-encoder reranking
    5. Self-RAG relevance gate
    6. Context compression
    7. Prompt assembly
    8. LLM generation
    9. Citation extraction

TRD Reference: PID D-10
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tool metadata
IDKP_TOOL_NAME = "idkp_domain_knowledge"
IDKP_TOOL_DESCRIPTION = (
    "Query the Intelligent Domain Knowledge Platform for domain-specific answers. "
    "Uses RAG (retrieval-augmented generation) to provide grounded, cited responses "
    "from your fine-tuned knowledge corpus. Best for factual, domain-specific questions."
)


class IDKPTool:
    """
    Callable wrapper around the IDKP RAG pipeline.

    Usage::

        tool = IDKPTool(model_variant="finetuned")
        result = await tool("What is the recommended dosage for drug X?")

    Returns a dict with keys:
        - response: str — the generated answer
        - citations: list[dict] — source citations
        - latency_ms: int — total pipeline latency
        - model_variant: str — which model was used
    """

    def __init__(
        self,
        *,
        model_variant: str = "base",
        max_context_length: int = 4096,
        top_k: int = 10,
        enable_reranking: bool = True,
        enable_query_expansion: bool = True,
    ) -> None:
        """
        Args:
            model_variant: ``"base"`` or ``"finetuned"``.
            max_context_length: Maximum context window for the assembled prompt.
            top_k: Number of chunks to retrieve before reranking.
            enable_reranking: Whether to apply cross-encoder reranking.
            enable_query_expansion: Whether to expand the query (HyDE + multi-query).
        """
        self.model_variant = model_variant
        self.max_context_length = max_context_length
        self.top_k = top_k
        self.enable_reranking = enable_reranking
        self.enable_query_expansion = enable_query_expansion

    async def __call__(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the RAG pipeline and return results.

        Args:
            query: User question to answer from the knowledge corpus.
            **kwargs: Override default settings for this call.
                - model_variant: str
                - top_k: int
                - enable_reranking: bool

        Returns:
            Dict with response, citations, latency_ms, model_variant.
        """
        import time

        start = time.monotonic()

        # Allow per-call overrides
        model = kwargs.get("model_variant", self.model_variant)
        k = kwargs.get("top_k", self.top_k)
        rerank = kwargs.get("enable_reranking", self.enable_reranking)
        expand = kwargs.get("enable_query_expansion", self.enable_query_expansion)

        try:
            from app.services.rag.context_assembler import assemble_context
            from app.services.rag.llm_client import generate
            from app.services.rag.prompt_builder import build_rag_prompt, extract_citations
            from app.services.rag.query_expansion import expand_query
            from app.services.rag.reranker import rerank
            from app.services.rag.retriever import retrieve

            # Step 1: Query expansion
            if expand:
                try:
                    queries = await expand_query(query)
                except Exception as exc:
                    logger.warning("Query expansion failed, using original: %s", exc)
                    queries = [query]
            else:
                queries = [query]

            # Step 2: Retrieve for each query and merge
            all_chunks = []
            seen_ids = set()
            for q in queries:
                retrieval = await retrieve(q, top_k=k)
                for chunk in retrieval.get("chunks", []):
                    chunk_id = chunk.get("id", chunk.get("chunk_id", ""))
                    if chunk_id and chunk_id not in seen_ids:
                        all_chunks.append(chunk)
                        seen_ids.add(chunk_id)

            # Step 3: Rerank
            if rerank and all_chunks:
                try:
                    all_chunks = await rerank(query, all_chunks)
                except Exception as exc:
                    logger.warning("Reranking failed, using original order: %s", exc)

            retrieval_result = {
                "query": query,
                "chunks": all_chunks[:k],
            }

            # Step 4: Assemble context
            context = await assemble_context(retrieval_result, query)

            # Step 5: Build prompt
            prompt = build_rag_prompt(context)

            # Step 6: Generate response
            llm_result = await generate(prompt, model=model)
            response_text = llm_result.content

            # Step 7: Extract citations
            citations = extract_citations(context)

        except Exception as exc:
            logger.exception("IDKP tool execution failed")
            response_text = f"[IDKP Error: {exc}]"
            citations = []

        latency_ms = int((time.monotonic() - start) * 1000)

        return {
            "response": response_text,
            "citations": citations,
            "latency_ms": latency_ms,
            "model_variant": model,
        }

    # ── LangChain Adapter ─────────────────────────────────────────────

    def as_langchain_tool(self) -> Any:
        """
        Return a LangChain ``BaseTool`` instance wrapping this IDKP tool.

        Requires ``langchain-core`` to be installed.

        Usage::

            from app.services.agent_tool_wrapper import IDKPTool
            tool = IDKPTool(model_variant="finetuned").as_langchain_tool()
            # Use with LangChain agent...
        """
        try:
            from langchain_core.tools import StructuredTool
            from pydantic import BaseModel, Field

            class IDKPToolInput(BaseModel):
                query: str = Field(
                    ...,
                    description="The question to answer from the domain knowledge corpus.",
                )

            tool_instance = self

            async def _run_tool(query: str) -> str:
                result = await tool_instance(query)
                # Format output for LangChain agent consumption
                output = result["response"]
                if result["citations"]:
                    output += "\n\nSources:\n"
                    for cite in result["citations"]:
                        source = cite.get("source", "Unknown")
                        page = cite.get("page", "")
                        section = cite.get("section", "")
                        ref = source
                        if page:
                            ref += f" (p.{page})"
                        if section:
                            ref += f" [{section}]"
                        output += f"  - {ref}\n"
                return output

            return StructuredTool.from_function(
                coroutine=_run_tool,
                name=IDKP_TOOL_NAME,
                description=IDKP_TOOL_DESCRIPTION,
                args_schema=IDKPToolInput,
            )
        except ImportError:
            raise ImportError(
                "langchain-core is required for LangChain tool adapter. "
                "Install it with: pip install langchain-core"
            ) from None

    # ── LlamaIndex Adapter ───────────────────────────────────────────

    def as_llamaindex_tool(self) -> Any:
        """
        Return a LlamaIndex ``FunctionTool`` wrapping this IDKP tool.

        Requires ``llama-index-core`` to be installed.

        Usage::

            from app.services.agent_tool_wrapper import IDKPTool
            tool = IDKPTool(model_variant="finetuned").as_llamaindex_tool()
            # Use with LlamaIndex agent...
        """
        try:
            from llama_index.core.tools import FunctionTool

            tool_instance = self

            async def _query_idkp(query: str) -> str:
                result = await tool_instance(query)
                output = result["response"]
                if result["citations"]:
                    output += "\n\nSources:\n"
                    for cite in result["citations"]:
                        source = cite.get("source", "Unknown")
                        page = cite.get("page", "")
                        section = cite.get("section", "")
                        ref = source
                        if page:
                            ref += f" (p.{page})"
                        if section:
                            ref += f" [{section}]"
                        output += f"  - {ref}\n"
                return output

            return FunctionTool.from_defaults(
                fn=_query_idkp,
                name=IDKP_TOOL_NAME,
                description=IDKP_TOOL_DESCRIPTION,
            )
        except ImportError:
            raise ImportError(
                "llama-index-core is required for LlamaIndex tool adapter. "
                "Install it with: pip install llama-index-core"
            ) from None

    # ── JSON Schema (for custom agent frameworks) ────────────────────

    def to_json_schema(self) -> dict[str, Any]:
        """
        Return the OpenAI-compatible function/tool schema for this tool.

        Useful for custom agent frameworks that accept JSON Schema tool definitions.
        """
        return {
            "type": "function",
            "function": {
                "name": IDKP_TOOL_NAME,
                "description": IDKP_TOOL_DESCRIPTION,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question to answer from the domain knowledge corpus.",
                        },
                        "model_variant": {
                            "type": "string",
                            "enum": ["base", "finetuned"],
                            "description": "Which model variant to use (default: base).",
                            "default": self.model_variant,
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        }
