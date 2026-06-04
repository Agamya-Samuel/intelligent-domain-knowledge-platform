"""RAGAS-compatible Evaluation service — LLM-as-judge metrics for the RAG pipeline.

Supports:
  - baseline: Evaluate the base model on the eval dataset
  - post_training: Evaluate a fine-tuned model (linked to a job)
  - weekly_regression: Scheduled regression check
  - comparison: A/B comparison between base and finetuned
  - benchmark: Model benchmarking across multiple catalog models

Metrics computed (RAGAS-compatible scoring via LLM-as-judge):
  - faithfulness: Is the answer grounded in the retrieved context?
  - context_relevance: Are the retrieved chunks relevant to the question?
  - answer_relevance: Is the answer relevant to the question?
  - context_recall: Does the context cover the ground-truth answer?

The evaluator LLM is configured via EVAL_LLM_BASE_URL / EVAL_LLM_MODEL
settings, falling back to the main LLM endpoint when not specified.
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.evaluation_run import EvaluationRun
from app.services.rag.llm_client import generate as llm_generate
from app.services.rag.prompt_builder import build_rag_prompt
from app.services.rag.retriever import retrieve

logger = logging.getLogger(__name__)

EVAL_DATASET_PATH = Path(__file__).parent.parent.parent / "eval_dataset.json"

# Semaphore to limit concurrent RAG pipeline invocations during evaluation
_eval_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazy-initialise the eval concurrency semaphore."""
    global _eval_semaphore
    if _eval_semaphore is None:
        _eval_semaphore = asyncio.Semaphore(settings.EVAL_MAX_CONCURRENCY)
    return _eval_semaphore


# ── Eval dataset loader ──────────────────────────────────────────────


def _load_eval_dataset() -> list[dict[str, str]]:
    """Load the ground-truth evaluation dataset from JSON."""
    if not EVAL_DATASET_PATH.exists():
        logger.warning("Eval dataset not found at %s", EVAL_DATASET_PATH)
        return []
    with open(EVAL_DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loaded %d evaluation samples from %s", len(data), EVAL_DATASET_PATH)
    return data


# ── Evaluator LLM client ────────────────────────────────────────────


def _get_evaluator_client() -> AsyncOpenAI:
    """Create an AsyncOpenAI client for the evaluator (judge) LLM."""
    base_url = settings.EVAL_LLM_BASE_URL or settings.LLM_BASE_URL
    api_key = settings.EVAL_LLM_API_KEY or "not-needed"
    return AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=1, timeout=120.0)


def _evaluator_model() -> str:
    """Return the evaluator model name."""
    return settings.EVAL_LLM_MODEL or settings.LLM_MODEL


async def _judge_score(prompt: str) -> float | None:
    """
    Call the evaluator LLM with a scoring prompt and extract the numeric score.

    The LLM is expected to return a response containing:
      - A score on a 0.0–1.0 scale
      - Optional reasoning

    Returns the extracted score, or None if extraction fails.
    """
    client = _get_evaluator_client()
    model = _evaluator_model()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.0,
            stream=False,
        )
        text = (response.choices[0].message.content or "").strip()
        # Extract a float between 0.0 and 1.0 from the response
        match = re.search(r"(?:score|Score|SCORE)\s*[:=]\s*(0(?:\.\d+)?|1(?:\.0+)?)", text)
        if match:
            return round(float(match.group(1)), 4)
        # Fallback: look for any float in [0, 1]
        floats = re.findall(r"(0(?:\.\d+)?|1(?:\.0+)?)", text)
        if floats:
            return round(float(floats[-1]), 4)
        logger.warning("Could not extract score from judge response: %.200s", text)
        return None
    except Exception as exc:
        logger.warning("Judge LLM call failed: %s", exc)
        return None


# ── RAGAS-compatible metric prompts ─────────────────────────────────

_FAITHFULNESS_PROMPT = """\
You are an expert evaluator. Score how faithful the given ANSWER is to the provided CONTEXT.
A score of 1.0 means every claim in the answer is directly supported by the context.
A score of 0.0 means the answer contains claims not supported by the context at all.

QUESTION: {question}
CONTEXT:
{contexts}
ANSWER: {answer}

Respond with your reasoning followed by:
Score: <value between 0.0 and 1.0>"""

_CONTEXT_RELEVANCE_PROMPT = """\
You are an expert evaluator. Score how relevant the retrieved CONTEXT is to the QUESTION.
A score of 1.0 means all context chunks are directly relevant.
A score of 0.0 means none of the context is relevant.

QUESTION: {question}
CONTEXT:
{contexts}

Respond with your reasoning followed by:
Score: <value between 0.0 and 1.0>"""

_ANSWER_RELEVANCE_PROMPT = """\
You are an expert evaluator. Score how relevant the ANSWER is to the QUESTION.
A score of 1.0 means the answer directly and fully addresses the question.
A score of 0.0 means the answer is completely off-topic.

QUESTION: {question}
ANSWER: {answer}

Respond with your reasoning followed by:
Score: <value between 0.0 and 1.0>"""

_CONTEXT_RECALL_PROMPT = """\
You are an expert evaluator. Score how well the retrieved CONTEXT covers the GROUND TRUTH answer.
A score of 1.0 means the context fully contains all information needed for the ground truth.
A score of 0.0 means the context contains none of the ground truth information.

QUESTION: {question}
CONTEXT:
{contexts}
GROUND TRUTH: {ground_truth}

Respond with your reasoning followed by:
Score: <value between 0.0 and 1.0>"""


async def _score_faithfulness(
    question: str,
    contexts: list[str],
    answer: str,
) -> float | None:
    ctx = "\n---\n".join(contexts) if contexts else "[No context]"
    return await _judge_score(
        _FAITHFULNESS_PROMPT.format(
            question=question,
            contexts=ctx,
            answer=answer,
        )
    )


async def _score_context_relevance(
    question: str,
    contexts: list[str],
) -> float | None:
    ctx = "\n---\n".join(contexts) if contexts else "[No context]"
    return await _judge_score(
        _CONTEXT_RELEVANCE_PROMPT.format(
            question=question,
            contexts=ctx,
        )
    )


async def _score_answer_relevance(
    question: str,
    answer: str,
) -> float | None:
    return await _judge_score(
        _ANSWER_RELEVANCE_PROMPT.format(
            question=question,
            answer=answer,
        )
    )


async def _score_context_recall(
    question: str,
    contexts: list[str],
    ground_truth: str,
) -> float | None:
    ctx = "\n---\n".join(contexts) if contexts else "[No context]"
    return await _judge_score(
        _CONTEXT_RECALL_PROMPT.format(
            question=question,
            contexts=ctx,
            ground_truth=ground_truth,
        )
    )


# ── RAG pipeline runner for a single eval sample ────────────────────


async def _run_single_sample(
    question: str,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Execute the full RAG pipeline for a single evaluation question.

    Returns a dict with question, retrieved_contexts, and response.
    """
    async with _get_semaphore():
        # Step 1: Retrieve relevant chunks
        retrieval = await retrieve(question)
        retrieved_contexts = retrieval.context_texts if retrieval.has_results else []

        # Step 2: Build the RAG prompt from retrieved context
        prompt = build_rag_prompt(retrieval)

        # Step 3: Generate an answer via the LLM
        try:
            llm_response = await llm_generate(prompt, model=model)
            response = llm_response.content
        except Exception as exc:
            logger.warning("LLM generation failed for question '%s': %s", question[:60], exc)
            response = "[LLM generation failed]"

        return {
            "question": question,
            "retrieved_contexts": retrieved_contexts if retrieved_contexts else [],
            "response": response,
        }


# ── Metric computation ──────────────────────────────────────────────


async def _score_single_sample(
    sample: dict[str, Any],
    ground_truth: str,
) -> dict[str, Any]:
    """Compute all 4 RAGAS metrics for a single sample concurrently."""
    question = sample["question"]
    contexts = sample["retrieved_contexts"]
    answer = sample["response"]

    results = await asyncio.gather(
        _score_faithfulness(question, contexts, answer),
        _score_context_relevance(question, contexts),
        _score_answer_relevance(question, answer),
        _score_context_recall(question, contexts, ground_truth),
        return_exceptions=True,
    )

    def _safe(val: Any) -> float | None:
        return val if isinstance(val, float | int | type(None)) else None

    return {
        "question": question,
        "faithfulness": _safe(results[0]),
        "context_relevance": _safe(results[1]),
        "answer_relevance": _safe(results[2]),
        "context_recall": _safe(results[3]),
    }


async def _compute_metrics(
    samples: list[dict[str, Any]],
    ground_truths: list[str],
) -> tuple[dict[str, float | None], list[dict[str, Any]]]:
    """
    Compute RAGAS-compatible metrics over a set of evaluation samples.

    Returns:
        Tuple of (aggregate_metrics, per_sample_scores)
    """
    if not samples:
        return (
            {
                "faithfulness": None,
                "context_relevance": None,
                "answer_relevance": None,
                "context_recall": None,
            },
            [],
        )

    # Score each sample
    per_sample: list[dict[str, Any]] = []
    for sample, gt in zip(samples, ground_truths):
        scores = await _score_single_sample(sample, gt)
        per_sample.append(scores)

    # Aggregate: mean across all samples
    metric_keys = ["faithfulness", "context_relevance", "answer_relevance", "context_recall"]
    aggregate: dict[str, float | None] = {}
    for key in metric_keys:
        values = [s[key] for s in per_sample if s[key] is not None]
        aggregate[key] = round(sum(values) / len(values), 4) if values else None

    return aggregate, per_sample


# ── Public API ───────────────────────────────────────────────────────


async def run_evaluation(
    db: AsyncSession,
    *,
    run_type: str,
    model_id: str | None = None,
    model_variant: str = "base",
    job_id: str | None = None,
    user_id: str,
) -> EvaluationRun:
    """
    Run a RAGAS-compatible evaluation and store the results.

    For each question in the eval dataset:
      1. Run the RAG pipeline (retrieve -> build prompt -> generate)
      2. Collect retrieved contexts, generated answers, and ground truth
      3. Compute metrics: faithfulness, context_relevance,
         answer_relevance, context_recall (via LLM-as-judge)
      4. Store aggregate + per-sample scores in the EvaluationRun
    """
    start_time = time.monotonic()

    eval_data = _load_eval_dataset()
    dataset_size = len(eval_data)

    if dataset_size == 0:
        logger.warning("Evaluation dataset is empty — creating run with no metrics")
        eval_run = EvaluationRun(
            user_id=user_id,
            run_type=run_type,
            status="completed",
            model_id=model_id,
            model_variant=model_variant,
            job_id=job_id,
            metrics={
                "faithfulness": None,
                "context_relevance": None,
                "answer_relevance": None,
                "context_recall": None,
                "note": "Empty evaluation dataset",
            },
            dataset_size=0,
            duration_seconds=round(time.monotonic() - start_time, 2),
        )
        db.add(eval_run)
        await db.flush()
        return eval_run

    # Create the run record in "running" state
    eval_run = EvaluationRun(
        user_id=user_id,
        run_type=run_type,
        status="running",
        model_id=model_id,
        model_variant=model_variant,
        job_id=job_id,
        metrics={},
        dataset_size=dataset_size,
    )
    db.add(eval_run)
    await db.flush()

    logger.info(
        "Starting evaluation run %s: type=%s model=%s variant=%s samples=%d",
        eval_run.id,
        run_type,
        model_id,
        model_variant,
        dataset_size,
    )

    try:
        # Step 1: Run the RAG pipeline for every eval question concurrently
        questions = [item["question"] for item in eval_data]
        ground_truths = [item["ground_truth"] for item in eval_data]

        # Determine which LLM model to use for generation
        llm_model = model_id  # pass model_id to vLLM if specified

        rag_results = await asyncio.gather(
            *[_run_single_sample(q, model=llm_model) for q in questions],
            return_exceptions=True,
        )

        # Filter out any exceptions from individual samples
        valid_samples: list[dict[str, Any]] = []
        valid_ground_truths: list[str] = []
        for i, result in enumerate(rag_results):
            if isinstance(result, Exception):
                logger.warning("Sample %d failed: %s", i, result)
            else:
                valid_samples.append(result)
                valid_ground_truths.append(ground_truths[i])

        if not valid_samples:
            raise RuntimeError("All RAG pipeline calls failed — no valid samples to evaluate")

        # Step 2: Compute RAGAS-compatible metrics (LLM-as-judge)
        aggregate_metrics, per_sample_scores = await _compute_metrics(
            valid_samples,
            valid_ground_truths,
        )

        # Step 3: Update the run record with results
        duration = round(time.monotonic() - start_time, 2)
        eval_run.metrics = aggregate_metrics
        eval_run.per_sample_scores = per_sample_scores
        eval_run.status = "completed"
        eval_run.duration_seconds = duration
        await db.flush()

        logger.info(
            "Evaluation run %s completed in %.1fs: %s",
            eval_run.id,
            duration,
            aggregate_metrics,
        )

    except Exception as exc:
        duration = round(time.monotonic() - start_time, 2)
        eval_run.status = "failed"
        eval_run.error_message = str(exc)[:2000]
        eval_run.duration_seconds = duration
        eval_run.metrics = {
            "faithfulness": None,
            "context_relevance": None,
            "answer_relevance": None,
            "context_recall": None,
        }
        await db.flush()
        logger.exception("Evaluation run %s failed after %.1fs: %s", eval_run.id, duration, exc)

    return eval_run


async def run_benchmark(
    db: AsyncSession,
    *,
    model_ids: list[str],
    model_variant: str = "base",
    job_id: str | None = None,
    user_id: str,
) -> list[EvaluationRun]:
    """
    Run a benchmark evaluation across multiple models.

    Each model gets its own EvaluationRun with a shared benchmark_config.
    Models are evaluated sequentially to avoid overloading the LLM endpoint.

    Returns the list of EvaluationRun records (one per model).
    """
    from app.db.base import generate_uuid

    benchmark_id = generate_uuid()
    benchmark_config = {
        "benchmark_id": benchmark_id,
        "model_ids": model_ids,
        "model_variant": model_variant,
        "job_id": job_id,
    }

    logger.info(
        "Starting benchmark %s across %d models: %s",
        benchmark_id,
        len(model_ids),
        model_ids,
    )

    runs: list[EvaluationRun] = []
    for model_id in model_ids:
        eval_run = EvaluationRun(
            user_id=user_id,
            run_type="benchmark",
            status="pending",
            model_id=model_id,
            model_variant=model_variant,
            job_id=job_id,
            metrics={},
            benchmark_config=benchmark_config,
        )
        db.add(eval_run)
        await db.flush()

        # Run the evaluation for this model
        completed_run = await _run_benchmark_single(
            db,
            eval_run=eval_run,
            model_id=model_id,
            model_variant=model_variant,
        )
        runs.append(completed_run)

    logger.info("Benchmark %s completed: %d runs", benchmark_id, len(runs))
    return runs


async def _run_benchmark_single(
    db: AsyncSession,
    *,
    eval_run: EvaluationRun,
    model_id: str,
    model_variant: str,
) -> EvaluationRun:
    """Run evaluation for a single model within a benchmark."""
    start_time = time.monotonic()
    eval_data = _load_eval_dataset()
    dataset_size = len(eval_data)

    eval_run.status = "running"
    eval_run.dataset_size = dataset_size
    await db.flush()

    if dataset_size == 0:
        eval_run.status = "completed"
        eval_run.metrics = {"note": "Empty evaluation dataset"}
        eval_run.duration_seconds = round(time.monotonic() - start_time, 2)
        await db.flush()
        return eval_run

    try:
        questions = [item["question"] for item in eval_data]
        ground_truths = [item["ground_truth"] for item in eval_data]

        rag_results = await asyncio.gather(
            *[_run_single_sample(q, model=model_id) for q in questions],
            return_exceptions=True,
        )

        valid_samples: list[dict[str, Any]] = []
        valid_ground_truths: list[str] = []
        for i, result in enumerate(rag_results):
            if isinstance(result, Exception):
                logger.warning("Benchmark sample %d (model=%s) failed: %s", i, model_id, result)
            else:
                valid_samples.append(result)
                valid_ground_truths.append(ground_truths[i])

        if not valid_samples:
            raise RuntimeError(f"All RAG pipeline calls failed for model {model_id}")

        aggregate_metrics, per_sample_scores = await _compute_metrics(
            valid_samples,
            valid_ground_truths,
        )

        duration = round(time.monotonic() - start_time, 2)
        eval_run.metrics = aggregate_metrics
        eval_run.per_sample_scores = per_sample_scores
        eval_run.status = "completed"
        eval_run.duration_seconds = duration
        await db.flush()

        logger.info(
            "Benchmark model %s completed in %.1fs: %s",
            model_id,
            duration,
            aggregate_metrics,
        )

    except Exception as exc:
        duration = round(time.monotonic() - start_time, 2)
        eval_run.status = "failed"
        eval_run.error_message = str(exc)[:2000]
        eval_run.duration_seconds = duration
        eval_run.metrics = {
            "faithfulness": None,
            "context_relevance": None,
            "answer_relevance": None,
            "context_recall": None,
        }
        await db.flush()
        logger.exception("Benchmark model %s failed: %s", model_id, exc)

    return eval_run


async def compare_evaluations(
    db: AsyncSession,
    *,
    base_eval_id: str,
    candidate_eval_id: str,
) -> dict[str, Any]:
    """
    Compare two completed evaluation runs and compute metric deltas.

    Returns a dict matching ComparisonResponse schema.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(EvaluationRun).where(EvaluationRun.id.in_([base_eval_id, candidate_eval_id]))
    )
    runs = {r.id: r for r in result.scalars().all()}

    base_run = runs.get(base_eval_id)
    cand_run = runs.get(candidate_eval_id)

    if not base_run:
        raise ValueError(f"Base evaluation run '{base_eval_id}' not found")
    if not cand_run:
        raise ValueError(f"Candidate evaluation run '{candidate_eval_id}' not found")

    def _safe_float(val: Any) -> float | None:
        return float(val) if val is not None else None

    base_m = base_run.metrics or {}
    cand_m = cand_run.metrics or {}

    base_metrics = {
        "faithfulness": _safe_float(base_m.get("faithfulness")),
        "context_relevance": _safe_float(base_m.get("context_relevance")),
        "answer_relevance": _safe_float(base_m.get("answer_relevance")),
        "context_recall": _safe_float(base_m.get("context_recall")),
    }
    cand_metrics = {
        "faithfulness": _safe_float(cand_m.get("faithfulness")),
        "context_relevance": _safe_float(cand_m.get("context_relevance")),
        "answer_relevance": _safe_float(cand_m.get("answer_relevance")),
        "context_recall": _safe_float(cand_m.get("context_recall")),
    }

    def _delta(c: float | None, b: float | None) -> float | None:
        if c is not None and b is not None:
            return round(c - b, 4)
        return None

    deltas = {
        "faithfulness_delta": _delta(
            cand_metrics["faithfulness"],
            base_metrics["faithfulness"],
        ),
        "context_relevance_delta": _delta(
            cand_metrics["context_relevance"],
            base_metrics["context_relevance"],
        ),
        "answer_relevance_delta": _delta(
            cand_metrics["answer_relevance"],
            base_metrics["answer_relevance"],
        ),
        "context_recall_delta": _delta(
            cand_metrics["context_recall"],
            base_metrics["context_recall"],
        ),
    }

    # Determine winner based on average delta
    valid_deltas = [d for d in deltas.values() if d is not None]
    winner: str | None = None
    if valid_deltas:
        avg_delta = sum(valid_deltas) / len(valid_deltas)
        if avg_delta > 0:
            winner = cand_run.model_id or cand_run.model_variant or "candidate"
        elif avg_delta < 0:
            winner = base_run.model_id or base_run.model_variant or "base"
        else:
            winner = "tie"

    return {
        "base_eval_id": base_eval_id,
        "candidate_eval_id": candidate_eval_id,
        "base_metrics": base_metrics,
        "candidate_metrics": cand_metrics,
        "deltas": deltas,
        "winner": winner,
    }
