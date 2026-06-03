"""RAGAS Evaluation service — runs RAGAS metrics against the RAG pipeline.

Currently supports:
  - baseline: Evaluate the base model on the eval dataset
  - post_training: Evaluate a fine-tuned model (linked to a job)
  - weekly_regression: Scheduled regression check
  - comparison: A/B comparison between base and finetuned

Week 4 scope: baseline + post_training evaluation harness skeleton.
Full RAGAS integration deferred to Week 6+ when the fine-tuning pipeline
actually produces LoRA adapters.
"""

import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_run import EvaluationRun

logger = logging.getLogger(__name__)

EVAL_DATASET_PATH = Path(__file__).parent.parent.parent.parent / "eval_dataset.json"


def _load_eval_dataset() -> list[dict]:
    """Load the ground-truth evaluation dataset from JSON."""
    if not EVAL_DATASET_PATH.exists():
        logger.warning("Eval dataset not found at %s", EVAL_DATASET_PATH)
        return []
    with open(EVAL_DATASET_PATH) as f:
        return json.load(f)


async def run_evaluation(
    db: AsyncSession,
    *,
    run_type: str,
    model_id: str | None = None,
    model_variant: str = "base",
    job_id: str | None = None,
) -> EvaluationRun:
    """
    Run a RAGAS evaluation and store the results.

    Week 4 implementation: skeleton that creates an EvaluationRun with
    placeholder metrics. Full RAGAS integration will compute actual
    faithfulness, context_relevance, answer_relevance, context_recall.
    """
    eval_data = _load_eval_dataset()
    dataset_size = len(eval_data)

    # TODO (Week 6+): Full RAGAS integration
    # 1. For each question in eval_data, run the RAG pipeline
    # 2. Collect retrieved contexts, generated answers, ground truth
    # 3. Compute RAGAS metrics: faithfulness, context_relevance,
    #    answer_relevance, context_recall
    # 4. Average across all examples

    # Placeholder metrics for Week 4 Phase 1 Gate
    metrics = {
        "faithfulness": None,
        "context_relevance": None,
        "answer_relevance": None,
        "context_recall": None,
        "note": "Placeholder metrics — full RAGAS integration in Week 6+",
    }

    eval_run = EvaluationRun(
        run_type=run_type,
        model_id=model_id,
        model_variant=model_variant,
        job_id=job_id,
        metrics=metrics,
        dataset_size=dataset_size if dataset_size > 0 else None,
    )
    db.add(eval_run)
    await db.flush()

    logger.info(
        "Evaluation run created: id=%s type=%s model=%s variant=%s",
        eval_run.id,
        run_type,
        model_id,
        model_variant,
    )

    return eval_run
