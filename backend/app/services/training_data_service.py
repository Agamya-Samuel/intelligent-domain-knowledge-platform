"""Training data preparation service — converts dataset sources into instruction-tuning JSON.

Responsibilities:
  - Load processed document chunks linked to a dataset
  - Generate instruction-tuning samples (Q&A pairs, summaries, reasoning)
  - Mix ~5–10% general-domain examples to prevent catastrophic forgetting
  - Export in the format expected by the QLoRA training pipeline
  - Preview without persisting (for the UI cost preview flow)

Output format (per sample):
  {
    "instruction": "<system or user instruction>",
    "input": "<context or retrieved document text>",
    "output": "<expected model response>",
    "domain": "<domain tag>",
    "type": "qa" | "summary" | "reasoning" | "general"
  }

The service reads from document chunks stored in PostgreSQL (via the
ingestion pipeline) and optionally from S3-hosted dataset source files.
"""

import json
import logging
import random
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.dataset import Dataset
from app.models.dataset_source import DatasetSource
from app.models.document import Document
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)

# ── General-domain seed examples (anti-forgetting) ─────────────────────

_GENERAL_DOMAIN_EXAMPLES: list[dict[str, str]] = [
    {
        "instruction": "Summarize the following text in two sentences.",
        "input": (
            "The Industrial Revolution, which began in Britain in the late 18th century, "
            "transformed agrarian societies into industrial ones. Factories replaced "
            "cottage industries, and urbanisation accelerated as people moved to cities "
            "for work."
        ),
        "output": (
            "The Industrial Revolution marked the shift from agrarian to industrial "
            "economies, starting in late-18th-century Britain. It drove mass urbanisation "
            "as factory work replaced cottage industries."
        ),
        "domain": "general",
        "type": "summary",
    },
    {
        "instruction": "Answer the following question using only the provided context.",
        "input": (
            "Context: Photosynthesis is the process by which green plants convert sunlight, "
            "water, and carbon dioxide into glucose and oxygen. It occurs primarily in the "
            "chloroplasts of leaf cells."
        ),
        "output": (
            "Photosynthesis is the process in which green plants use sunlight, water, and "
            "CO₂ to produce glucose and oxygen, taking place mainly in leaf chloroplasts."
        ),
        "domain": "general",
        "type": "qa",
    },
    {
        "instruction": "Explain the reasoning behind the following statement.",
        "input": (
            "Statement: Diversification reduces portfolio risk but does not eliminate "
            "systematic risk."
        ),
        "output": (
            "Diversification spreads investments across uncorrelated assets, which lowers "
            "unsystematic (asset-specific) risk. However, systematic risk — driven by "
            "macroeconomic factors like interest rates or recessions — affects all assets "
            "simultaneously and cannot be diversified away."
        ),
        "domain": "general",
        "type": "reasoning",
    },
    {
        "instruction": "Rewrite the following paragraph to be more concise.",
        "input": (
            "In today's modern world, it is absolutely essential for organisations of all "
            "sizes to carefully and thoughtfully consider the various cybersecurity threats "
            "that they may potentially face on a daily basis."
        ),
        "output": (
            "Organisations of all sizes must carefully consider the cybersecurity threats "
            "they face daily."
        ),
        "domain": "general",
        "type": "summary",
    },
    {
        "instruction": "Given the context, answer the question.",
        "input": (
            "Context: The TCP/IP model consists of four layers — Application, Transport, "
            "Internet, and Network Access. HTTP operates at the Application layer and "
            "relies on TCP at the Transport layer for reliable delivery."
        ),
        "output": (
            "HTTP operates at the Application layer of the TCP/IP model, using TCP at the "
            "Transport layer to guarantee reliable packet delivery."
        ),
        "domain": "general",
        "type": "qa",
    },
]

# ── Instruction templates per sample type ───────────────────────────────

_QA_INSTRUCTION = (
    "Answer the following question using only the information in the provided context. "
    "If the context does not contain enough information, say so."
)
_SUMMARY_INSTRUCTION = (
    "Provide a concise, accurate summary of the following text. "
    "Preserve all key facts and technical terminology."
)
_REASONING_INSTRUCTION = (
    "Analyse the provided information and explain your reasoning step-by-step "
    "to arrive at a well-supported conclusion."
)


# ── Public helpers ───────────────────────────────────────────────────────


async def _load_dataset_chunks(
    db: AsyncSession,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """
    Load all processed document chunks belonging to a dataset's sources.

    Matches dataset sources (by S3 path) to documents (by s3_key),
    then returns their associated chunks.

    Returns a list of dicts with keys: content, metadata, source_id, domain.
    """
    # 1. Get all sources for this dataset
    src_result = await db.execute(
        select(DatasetSource).where(
            DatasetSource.dataset_id == dataset_id,
            DatasetSource.processed.is_(True),
        )
    )
    sources = src_result.scalars().all()
    if not sources:
        return []

    source_paths = {s.source_path for s in sources if s.source_path}

    # 2. Find documents whose s3_key matches any source path
    if not source_paths:
        return []

    doc_result = await db.execute(
        select(Document).where(
            Document.s3_key.in_(source_paths),
            Document.status == "completed",
        )
    )
    docs = doc_result.scalars().all()
    if not docs:
        return []

    doc_ids = [d.id for d in docs]

    # 3. Load all chunks belonging to those documents
    chunk_result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))
    )
    chunks = chunk_result.scalars().all()

    return [
        {
            "content": c.content,
            "metadata": c.metadata_ or {},
            "source_id": c.document_id,
            "domain": "domain",
        }
        for c in chunks
    ]


def _chunks_to_qa_pairs(chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """
    Convert document chunks into instruction-tuning Q&A pairs.

    Each chunk becomes one Q&A sample:
      - instruction: "Answer using context..."
      - input: the chunk content (as context) + a synthetic question
      - output: a synthetic answer grounded in the chunk
    """
    samples: list[dict[str, str]] = []

    for chunk in chunks:
        content = chunk.get("content", "")
        if not content or len(content.strip()) < 50:
            continue

        # Use the first 200 chars as the "question topic"
        topic = content[:200].strip()
        instruction = _QA_INSTRUCTION
        sample_input = (
            f"Context:\n{content}\n\n"
            f"Question: What key information does this context provide about: "
            f"{topic[:80]}...?"
        )
        sample_output = (
            f"Based on the provided context, the key information is: "
            f"{content[:300].strip()}"
        )
        samples.append({
            "instruction": instruction,
            "input": sample_input,
            "output": sample_output,
            "domain": chunk.get("domain", "domain"),
            "type": "qa",
        })

    return samples


def _chunks_to_summary_samples(chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert every third chunk into a summarisation training sample."""
    samples: list[dict[str, str]] = []

    for chunk in chunks[::3]:
        content = chunk.get("content", "")
        if not content or len(content.strip()) < 100:
            continue

        truncated = content[:800].strip()
        samples.append({
            "instruction": _SUMMARY_INSTRUCTION,
            "input": truncated,
            "output": f"Summary: {truncated[:300].strip()}",
            "domain": chunk.get("domain", "domain"),
            "type": "summary",
        })

    return samples


def _chunks_to_reasoning_samples(chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert every fifth chunk into a reasoning/analysis training sample."""
    samples: list[dict[str, str]] = []

    for chunk in chunks[::5]:
        content = chunk.get("content", "")
        if not content or len(content.strip()) < 100:
            continue

        truncated = content[:600].strip()
        samples.append({
            "instruction": _REASONING_INSTRUCTION,
            "input": f"Analyse the following information:\n{truncated}",
            "output": (
                f"Step-by-step analysis:\n"
                f"1. The key topic addressed is: {truncated[:120].strip()}\n"
                f"2. Supporting evidence includes: {truncated[120:300].strip()}\n"
                f"3. Conclusion: The information provides insight into the domain topic."
            ),
            "domain": chunk.get("domain", "domain"),
            "type": "reasoning",
        })

    return samples


def _inject_general_examples(
    samples: list[dict[str, str]],
    ratio: float = 0.07,
) -> list[dict[str, str]]:
    """
    Inject general-domain examples to prevent catastrophic forgetting.

    ratio: target proportion of general examples in the final dataset (5–10%).
    """
    if not samples:
        return list(_GENERAL_DOMAIN_EXAMPLES)

    target_count = max(1, int(len(samples) * ratio))
    # Cycle through the seed examples to reach target_count
    general = []
    for i in range(target_count):
        ex = _GENERAL_DOMAIN_EXAMPLES[i % len(_GENERAL_DOMAIN_EXAMPLES)]
        general.append(dict(ex))

    combined = samples + general
    random.shuffle(combined)
    logger.info(
        "Training data: %d domain samples + %d general samples = %d total",
        len(samples), len(general), len(combined),
    )
    return combined


# ── Public API ───────────────────────────────────────────────────────────


async def prepare_training_data(
    db: AsyncSession,
    dataset_id: str,
    *,
    include_general: bool = True,
    general_ratio: float = 0.07,
) -> dict[str, Any]:
    """
    Generate a complete instruction-tuning dataset from a dataset's chunks.

    Returns:
        {
            "dataset_id": "<uuid>",
            "dataset_version": <int>,
            "total_samples": <int>,
            "domain_samples": <int>,
            "general_samples": <int>,
            "by_type": {"qa": <n>, "summary": <n>, "reasoning": <n>, "general": <n>},
            "samples": [<sample dicts>]
        }
    """
    # Validate dataset
    ds_result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = ds_result.scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset '{dataset_id}' not found")
    if dataset.status != "active":
        raise ValueError(f"Dataset '{dataset_id}' is not active")

    # Load chunks and build samples
    chunks = await _load_dataset_chunks(db, dataset_id)
    logger.info("Loaded %d chunks for dataset %s", len(chunks), dataset_id)

    domain_samples: list[dict[str, str]] = []
    domain_samples.extend(_chunks_to_qa_pairs(chunks))
    domain_samples.extend(_chunks_to_summary_samples(chunks))
    domain_samples.extend(_chunks_to_reasoning_samples(chunks))

    if include_general:
        all_samples = _inject_general_examples(domain_samples, general_ratio)
    else:
        all_samples = domain_samples

    general_count = sum(1 for s in all_samples if s.get("type") == "general")
    by_type: dict[str, int] = {}
    for s in all_samples:
        t = s.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "dataset_id": dataset_id,
        "dataset_version": dataset.version,
        "total_samples": len(all_samples),
        "domain_samples": len(all_samples) - general_count,
        "general_samples": general_count,
        "by_type": by_type,
        "samples": all_samples,
    }


def export_training_json(data: dict[str, Any]) -> str:
    """Serialise the training data dict to a JSON string for S3 upload or download."""
    return json.dumps(data, ensure_ascii=False, indent=2)


async def estimate_training_cost(
    model_id: str,
    dataset_id: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Estimate the cost of fine-tuning on a given model + dataset without running.

    Returns:
        {
            "model_id": "<id>",
            "estimated_cost": <float>,
            "estimated_time_min": <int>,
            "dataset_sample_count": <int>,
            "remaining_budget": <float>,
            "within_budget": <bool>
        }
    """
    from app.config import MODEL_CATALOG
    from app.services.budget_service import get_monthly_spend

    model_entry = next((m for m in MODEL_CATALOG if m["id"] == model_id), None)
    if not model_entry:
        raise ValueError(f"Model '{model_id}' not found in MODEL_CATALOG")

    # Count samples for context
    chunks = await _load_dataset_chunks(db, dataset_id)
    sample_count = len(chunks)  # approximate

    est_cost = model_entry["est_cost"]
    est_time = model_entry["est_time_min"]

    current_spend = float(await get_monthly_spend(db))
    remaining = round(settings.BUDGET_MONTHLY_LIMIT - current_spend, 4)
    within_budget = (current_spend + est_cost) <= settings.BUDGET_MONTHLY_LIMIT

    return {
        "model_id": model_id,
        "estimated_cost": est_cost,
        "estimated_time_min": est_time,
        "dataset_sample_count": sample_count,
        "remaining_budget": remaining,
        "within_budget": within_budget,
    }
