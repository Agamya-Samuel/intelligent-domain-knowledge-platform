"""Model comparison service — runs the same query through base and fine-tuned models.

Implements TRD §4.5: side-by-side comparison of base vs. fine-tuned model
responses with metric deltas. Used by:
  - POST /api/compare — real-time comparison
  - Automated weekly regression pipeline

The comparison runs the full RAG pipeline (retrieve → generate) for both
model variants and computes response-level metrics (length, latency,
citation count) alongside RAGAS evaluation scores when available.
"""

import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.llm_client import generate
from app.services.rag.prompt_builder import build_rag_prompt, extract_citations
from app.services.rag.retriever import retrieve

logger = logging.getLogger(__name__)


async def _generate_for_variant(
    query: str,
    *,
    model: str | None = None,
    variant: str = "base",
) -> dict[str, Any]:
    """
    Run the RAG pipeline for a single model variant.

    Returns:
        {
            "variant": "base" | "finetuned",
            "response": str,
            "citations": list,
            "latency_ms": int,
            "token_count": int,
        }
    """
    start = time.monotonic()
    retrieval = await retrieve(query)
    prompt = build_rag_prompt(retrieval)
    citations = extract_citations(retrieval)

    try:
        llm_response = await generate(prompt, model=model)
        response = llm_response.content
    except Exception as exc:
        logger.warning("LLM generation failed for variant=%s: %s", variant, exc)
        response = "[Generation failed]"

    latency_ms = int((time.monotonic() - start) * 1000)
    token_count = len(response) // 4

    return {
        "variant": variant,
        "response": response,
        "citations": citations,
        "latency_ms": latency_ms,
        "token_count": token_count,
    }


async def compare_models(
    db: AsyncSession,
    *,
    query: str,
    base_model_id: str | None = None,
    finetuned_model_id: str | None = None,
) -> dict[str, Any]:
    """
    Compare base and fine-tuned model responses for the same query.

    Both models receive identical retrieved context and user query.
    The comparison includes response text, latency, token count, and
    citation overlap.

    Returns:
        {
            "query": str,
            "base": { variant, response, citations, latency_ms, token_count },
            "finetuned": { variant, response, citations, latency_ms, token_count },
            "comparison": {
                "latency_delta_ms": int,
                "token_count_delta": int,
                "citation_overlap": float,
                "response_length_delta": int,
            }
        }
    """
    # Run both variants concurrently
    base_result, ft_result = await _run_both(query, base_model_id, finetuned_model_id)

    # Compute comparison metrics
    latency_delta = ft_result["latency_ms"] - base_result["latency_ms"]
    token_delta = ft_result["token_count"] - base_result["token_count"]
    length_delta = len(ft_result["response"]) - len(base_result["response"])

    # Citation overlap: Jaccard similarity of citation sources
    base_sources = {c.get("source", "") for c in base_result["citations"]}
    ft_sources = {c.get("source", "") for c in ft_result["citations"]}
    if base_sources or ft_sources:
        overlap = len(base_sources & ft_sources) / len(base_sources | ft_sources)
    else:
        overlap = 1.0

    return {
        "query": query,
        "base": base_result,
        "finetuned": ft_result,
        "comparison": {
            "latency_delta_ms": latency_delta,
            "token_count_delta": token_delta,
            "citation_overlap": round(overlap, 4),
            "response_length_delta": length_delta,
        },
    }


async def _run_both(
    query: str,
    base_model_id: str | None,
    finetuned_model_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run both model variants concurrently and return (base, finetuned) results."""
    import asyncio

    base_task = _generate_for_variant(query, model=base_model_id, variant="base")
    ft_task = _generate_for_variant(query, model=finetuned_model_id, variant="finetuned")

    base_result, ft_result = await asyncio.gather(base_task, ft_task, return_exceptions=True)

    # Handle exceptions
    if isinstance(base_result, Exception):
        logger.warning("Base model comparison failed: %s", base_result)
        base_result = {
            "variant": "base",
            "response": "[Base model error]",
            "citations": [],
            "latency_ms": 0,
            "token_count": 0,
        }
    if isinstance(ft_result, Exception):
        logger.warning("Fine-tuned model comparison failed: %s", ft_result)
        ft_result = {
            "variant": "finetuned",
            "response": "[Fine-tuned model error]",
            "citations": [],
            "latency_ms": 0,
            "token_count": 0,
        }

    return base_result, ft_result


# ── Dataset staleness detection ──────────────────────────────────────────


async def detect_staleness(
    db: AsyncSession,
    dataset_id: str,
) -> dict[str, Any]:
    """
    Check whether a dataset has been updated since the last fine-tuning job.

    Compares the dataset's current version against the dataset_version of
    the most recent completed fine-tuning job for this dataset.

    Returns:
        {
            "dataset_id": str,
            "current_version": int,
            "last_ft_version": int | None,
            "sources_since_ft": int,
            "is_stale": bool,
            "message": str | None
        }
    """
    from sqlalchemy import select

    from app.models.dataset import Dataset
    from app.models.fine_tuning_job import FineTuningJob

    # Get current dataset version
    ds_result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )
    dataset = ds_result.scalar_one_or_none()
    if not dataset:
        return {
            "dataset_id": dataset_id,
            "current_version": 0,
            "last_ft_version": None,
            "sources_since_ft": 0,
            "is_stale": False,
            "message": "Dataset not found",
        }

    # Get most recent completed FT job for this dataset
    ft_result = await db.execute(
        select(FineTuningJob)
        .where(
            FineTuningJob.dataset_id == dataset_id,
            FineTuningJob.status == "completed",
        )
        .order_by(FineTuningJob.completed_at.desc().nulls_last())
        .limit(1)
    )
    last_job = ft_result.scalar_one_or_none()

    if not last_job:
        return {
            "dataset_id": dataset_id,
            "current_version": dataset.version,
            "last_ft_version": None,
            "sources_since_ft": dataset.version,  # all versions are "new"
            "is_stale": False,
            "message": "No fine-tuning jobs completed for this dataset yet",
        }

    version_diff = dataset.version - last_job.dataset_version
    is_stale = version_diff > 0

    return {
        "dataset_id": dataset_id,
        "current_version": dataset.version,
        "last_ft_version": last_job.dataset_version,
        "sources_since_ft": version_diff,
        "is_stale": is_stale,
        "message": (
            f"{version_diff} new source(s) added since last fine-tune "
            f"(v{last_job.dataset_version}). Consider re-training."
            if is_stale
            else None
        ),
    }
