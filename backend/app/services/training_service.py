"""QLoRA training service — orchestrates fine-tuning jobs on Modal.com.

Responsibilities:
  - Submit fine-tuning jobs to Modal GPU functions (Unsloth + PEFT)
  - Persist LoRA adapter to Modal Volume and S3
  - Save training checkpoints to S3 every N steps
  - Update job status in PostgreSQL (queued → training → evaluating → completed)
  - Poll job progress and relay metrics for WebSocket consumers

The training pipeline uses Unsloth for 2x faster QLoRA training and
PEFT for adapter configuration. Base models are persisted on a Modal
Volume to avoid re-downloading on cold starts.

Training data is uploaded to S3 before job submission, and the Modal
function pulls it at runtime from the `datasets/` prefix.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.fine_tuning_job import FineTuningJob
from app.services.budget_service import record_spend
from app.services.training_data_service import export_training_samples_json, prepare_training_data

logger = logging.getLogger(__name__)


# ── S3 helpers ───────────────────────────────────────────────────────────


def _s3_client():
    """Lazy-create a boto3 S3 client (import guarded for environments without boto3)."""
    try:
        import boto3

        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
    except ImportError:
        logger.warning("boto3 not installed — S3 upload will be skipped")
        return None


def _upload_training_data(job_id: str, training_json: str) -> str:
    """Upload the instruction-tuning JSON to S3 and return the S3 key."""
    client = _s3_client()
    if not client:
        return f"s3://{settings.S3_BUCKET_NAME}/datasets/{job_id}/train.json"

    s3_key = f"datasets/{job_id}/train.json"
    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=training_json.encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Uploaded training data to s3://%s/%s", settings.S3_BUCKET_NAME, s3_key)
    return f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"


def _record_checkpoint_path(job_id: str) -> str:
    """Return the S3 prefix where training checkpoints will be saved."""
    return f"s3://{settings.S3_BUCKET_NAME}/{settings.CHECKPOINT_S3_PREFIX}/{job_id}/"


# ── Modal client helpers ─────────────────────────────────────────────────


def _get_modal_client():
    """
    Return an authenticated Modal client for submitting training functions.

    Authenticates using ``MODAL_TOKEN_ID`` and ``MODAL_TOKEN_SECRET`` from
    settings.  The Modal SDK also reads ``~/.modal.toml`` or the same env
    vars, so we set them before importing so the SDK picks them up.

    Raises ``RuntimeError`` when the SDK is missing or no credentials are
    configured, so callers can propagate a clear failure to the job record
    instead of silently entering a dry-run mode that never reaches Modal.
    """
    # Propagate settings → env vars so the Modal SDK can pick them up
    import os
    if settings.MODAL_TOKEN_ID:
        os.environ.setdefault("MODAL_TOKEN_ID", settings.MODAL_TOKEN_ID)
    if settings.MODAL_TOKEN_SECRET:
        os.environ.setdefault("MODAL_TOKEN_SECRET", settings.MODAL_TOKEN_SECRET)

    try:
        import modal  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Modal SDK is not installed. Install it with: pip install modal"
        ) from exc

    if not settings.MODAL_TOKEN_ID or not settings.MODAL_TOKEN_SECRET:
        raise RuntimeError(
            "MODAL_TOKEN_ID and MODAL_TOKEN_SECRET must be set in environment / .env "
            "for fine-tuning jobs to reach Modal. "
            "Get credentials at https://modal.com/settings/tokens"
        )

    return modal


# ── Training job orchestration ───────────────────────────────────────────


async def submit_training_job(
    db: AsyncSession,
    job_id: str,
) -> dict[str, Any]:
    """
    Orchestrate a complete fine-tuning run for the given job_id.

    Steps:
      1. Load job from DB and transition to 'training'
      2. Generate + upload training data to S3
      3. Build Modal function config (QLoRA params, GPU tier)
      4. Submit to Modal and record function_id
      5. Update job status and modal_function_id

    Returns the updated job data as a dict.
    """
    # 1. Load job
    result = await db.execute(select(FineTuningJob).where(FineTuningJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError(f"Job '{job_id}' not found")
    if job.status not in ("queued",):
        raise ValueError(f"Job '{job_id}' is in status '{job.status}', cannot start training")

    # Transition to training
    await _update_job_status(db, job_id, "training", started_at=datetime.now(UTC))

    try:
        # 2. Prepare and upload training data
        data = await prepare_training_data(db, job.dataset_id)
        training_json = export_training_samples_json(data)
        s3_data_path = _upload_training_data(job_id, training_json)

        # 3. Build Modal config
        checkpoint_prefix = _record_checkpoint_path(job_id)
        modal_config = _build_modal_config(job, checkpoint_prefix)

        # 4. Submit to Modal — raises RuntimeError if SDK/credentials are missing
        modal = _get_modal_client()
        function_id = await _submit_modal_job(modal, modal_config, s3_data_path, job_id)

        # 5. Update job with modal_function_id and training metadata
        await db.execute(
            update(FineTuningJob)
            .where(FineTuningJob.id == job_id)
            .values(
                modal_function_id=function_id,
                checkpoint_s3_path=checkpoint_prefix,
                training_metrics={
                    "status": "submitted",
                    "s3_data_path": s3_data_path,
                    "sample_count": data["total_samples"],
                    "modal_config": modal_config,
                },
            )
        )
        await db.flush()

        logger.info(
            "Training job %s submitted: modal_fn=%s samples=%d",
            job_id,
            function_id,
            data["total_samples"],
        )

        return {
            "job_id": job_id,
            "status": "training",
            "modal_function_id": function_id,
            "sample_count": data["total_samples"],
        }

    except Exception as exc:
        await _update_job_status(
            db,
            job_id,
            "failed",
            error_message=str(exc)[:2000],
            completed_at=datetime.now(UTC),
        )
        logger.exception("Training job %s submission failed: %s", job_id, exc)
        raise


def _build_modal_config(
    job: FineTuningJob,
    checkpoint_prefix: str,
) -> dict[str, Any]:
    """
    Build the Modal function configuration for a QLoRA training job.

    GPU tier is selected based on the model's MODEL_CATALOG entry:
      - Tier 0/1 (7B–14B): A10G
      - Tier 2 (31B–32B): L40S
      - Tier 3 (70B–72B): A100-80GB
    """
    from app.config import MODEL_CATALOG

    model_entry = next((m for m in MODEL_CATALOG if m["id"] == job.model_id), None)
    gpu = model_entry["gpu"] if model_entry else "A10G"
    vram_gb = model_entry["vram_gb"] if model_entry else 16.0

    return {
        "gpu": gpu,
        "vram_gb": vram_gb,
        "model_id": job.model_id,
        "lora_rank": settings.QLORA_RANK,
        "lora_alpha": settings.QLORA_ALPHA,
        "lora_dropout": settings.QLORA_DROPOUT,
        "learning_rate": settings.QLORA_LEARNING_RATE,
        "num_epochs": settings.QLORA_NUM_EPOCHS,
        "batch_size": settings.QLORA_BATCH_SIZE,
        "grad_accum_steps": settings.QLORA_GRAD_ACCUM_STEPS,
        "max_seq_length": settings.QLORA_MAX_SEQ_LENGTH,
        "checkpoint_steps": settings.QLORA_CHECKPOINT_STEPS,
        "checkpoint_s3_prefix": checkpoint_prefix,
        "modal_volume": settings.MODAL_VOLUME_NAME,
        "timeout_seconds": 600,
    }


async def _submit_modal_job(
    modal: Any,
    config: dict[str, Any],
    s3_data_path: str,
    job_id: str,
) -> str:
    """
    Submit the QLoRA training function to Modal.

    Uses ``modal.Function.from_name`` to look up the deployed function
    in the ``idkp-train`` app, then spawns it asynchronously.
    ``.spawn.aio()`` (async variant) returns a ``FunctionCall`` whose
    ``object_id`` we persist so we can poll/cancel later via
    ``FunctionCall.from_id``.

    Raises ``RuntimeError`` if the ``idkp-train`` app has not been deployed.
    """
    logger.info(
        "Submitting Modal training job: gpu=%s model=%s data=%s",
        config["gpu"],
        config["model_id"],
        s3_data_path,
    )

    # Look up the deployed Modal function by app name + function name.
    # from_name() is lazy — the actual server round-trip happens on .spawn().
    train_fn = modal.Function.from_name("idkp-train", "train_qlora_fn")

    # Override GPU if the job config specifies a different tier
    gpu = config.get("gpu")
    if gpu:
        train_fn = train_fn.with_options(gpu=gpu)

    try:
        # Spawn asynchronously — returns a FunctionCall object
        function_call = await train_fn.spawn.aio(config, s3_data_path, job_id)
        call_id = function_call.object_id
    except Exception as exc:
        error_msg = str(exc)
        if "not found" in error_msg.lower() or "not deployed" in error_msg.lower():
            raise RuntimeError(
                f"Modal app 'idkp-train' is not deployed. "
                f"Deploy it first with: modal deploy backend/app/services/modal_train.py\n"
                f"Original error: {error_msg}"
            ) from exc
        raise RuntimeError(
            f"Failed to spawn Modal training function: {error_msg}"
        ) from exc

    logger.info("Modal job spawned: call_id=%s", call_id)
    return call_id


# ── Job state machine ────────────────────────────────────────────────────


async def _update_job_status(
    db: AsyncSession,
    job_id: str,
    new_status: str,
    *,
    error_message: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    """Update job status and optional timestamp fields atomically."""
    values: dict[str, Any] = {"status": new_status}
    if error_message is not None:
        values["error_message"] = error_message
    if started_at is not None:
        values["started_at"] = started_at
    if completed_at is not None:
        values["completed_at"] = completed_at

    await db.execute(update(FineTuningJob).where(FineTuningJob.id == job_id).values(**values))
    await db.flush()


async def complete_training_job(
    db: AsyncSession,
    job_id: str,
    *,
    lora_adapter_path: str | None = None,
    training_metrics: dict | None = None,
    cost: float | None = None,
) -> None:
    """
    Transition a job from 'training' to 'evaluating'.

    Called when the Modal function signals training is done.
    The evaluation step is triggered separately.
    """
    await db.execute(
        update(FineTuningJob)
        .where(FineTuningJob.id == job_id)
        .values(
            status="evaluating",
            lora_adapter_path=lora_adapter_path,
            training_metrics=training_metrics or {},
            cost=cost,
        )
    )
    await db.flush()
    logger.info("Job %s transitioned to 'evaluating'", job_id)


async def finalize_job(
    db: AsyncSession,
    job_id: str,
    *,
    eval_report: dict | None = None,
    cost: float | None = None,
) -> None:
    """
    Mark a job as 'completed' after evaluation.

    Records the final cost in the budget tracking table.
    """
    await db.execute(
        update(FineTuningJob)
        .where(FineTuningJob.id == job_id)
        .values(
            status="completed",
            eval_report=eval_report or {},
            cost=cost,
            completed_at=datetime.now(UTC),
        )
    )
    await db.flush()

    # Record spend in budget tracking
    if cost is not None and cost > 0:
        await record_spend(db, job_id, cost)

    logger.info("Job %s completed. eval_report=%s cost=%s", job_id, eval_report, cost)


async def fail_job(
    db: AsyncSession,
    job_id: str,
    error: str,
) -> None:
    """Mark a job as 'failed' with an error message."""
    await _update_job_status(
        db,
        job_id,
        "failed",
        error_message=error[:2000],
        completed_at=datetime.now(UTC),
    )
    logger.warning("Job %s failed: %s", job_id, error[:200])


async def cancel_training_job(
    db: AsyncSession,
    job: FineTuningJob,
) -> None:
    """
    Cancel an active fine-tuning job.

    Transitions queued/training/evaluating jobs to 'cancelled'.
    Attempts to stop the Modal function if one is running.
    """
    cancellable_statuses = {"queued", "training", "evaluating"}
    if job.status not in cancellable_statuses:
        raise ValueError(
            f"Job '{job.id}' is in status '{job.status}' and cannot be cancelled. "
            f"Only {', '.join(sorted(cancellable_statuses))} jobs can be cancelled."
        )

    # Attempt to stop the Modal function if running
    if job.modal_function_id and job.status in ("training", "evaluating"):
        try:
            modal = _get_modal_client()
            # Re-instantiate the FunctionCall from its stored object_id
            # and cancel the execution on Modal infrastructure.
            fc = modal.FunctionCall.from_id(job.modal_function_id)
            fc.cancel(terminate_containers=True)
            logger.info(
                "Cancelled Modal function %s for job %s",
                job.modal_function_id,
                job.id,
            )
        except RuntimeError:
            # Modal not configured — nothing to cancel on the infrastructure side
            logger.warning(
                "Modal not configured — cannot cancel remote function for job %s", job.id
            )
        except Exception as exc:
            logger.warning("Failed to cancel Modal function for job %s: %s", job.id, exc)

    await _update_job_status(
        db,
        job.id,
        "cancelled",
        error_message="Cancelled by user",
        completed_at=datetime.now(UTC),
    )
    logger.info("Job %s cancelled by user", job.id)


async def delete_training_job(
    db: AsyncSession,
    job: FineTuningJob,
) -> None:
    """
    Permanently delete a job from the database.

    Only terminal status jobs (completed, failed, cancelled) can be deleted.
    Active jobs must be cancelled first.
    """
    deletable_statuses = {"completed", "failed", "cancelled"}
    if job.status not in deletable_statuses:
        raise ValueError(
            f"Job '{job.id}' is in status '{job.status}' and cannot be deleted. "
            f"Only {', '.join(sorted(deletable_statuses))} jobs can be deleted. "
            f"Cancel the job first if it is still active."
        )

    await db.delete(job)
    await db.flush()
    logger.info("Job %s deleted by user", job.id)


# ── Queue processing ─────────────────────────────────────────────────────


async def process_queue(db: AsyncSession) -> FineTuningJob | None:
    """
    Pick up the next queued job if no job is currently running.

    FIFO ordering: the job with the lowest queue_position is selected.
    Returns the job if one was started, or None if the queue is idle.
    """
    # Check if any job is currently training/evaluating
    running_result = await db.execute(
        select(FineTuningJob).where(FineTuningJob.status.in_(["training", "evaluating"]))
    )
    if running_result.scalar_one_or_none() is not None:
        return None  # A job is already running

    # Get the next queued job (FIFO)
    next_result = await db.execute(
        select(FineTuningJob)
        .where(FineTuningJob.status == "queued")
        .order_by(FineTuningJob.queue_position.asc().nulls_last(), FineTuningJob.created_at.asc())
        .limit(1)
    )
    job = next_result.scalar_one_or_none()
    if not job:
        return None

    logger.info("Queue: starting job %s (queue_pos=%s)", job.id, job.queue_position)
    return job


# ── Modal job completion polling ─────────────────────────────────────────


async def poll_modal_jobs(db: AsyncSession) -> list[str]:
    """
    Check all jobs in ``training`` / ``evaluating`` status for Modal
    function completion.

    Uses the stored ``modal_function_id`` to instantiate a
    ``FunctionCall.from_id`` and call ``.get(timeout=0)`` (non-blocking).
    If the call has returned, the job is finalized; if a timeout is raised
    the job is still running and is skipped for this cycle.

    Returns a list of job IDs that were resolved (completed or failed).
    """
    result = await db.execute(
        select(FineTuningJob).where(
            FineTuningJob.status.in_(["training", "evaluating"]),
            FineTuningJob.modal_function_id.isnot(None),
        )
    )
    jobs = result.scalars().all()
    resolved_ids: list[str] = []

    if not jobs:
        return resolved_ids

    try:
        modal = _get_modal_client()
    except RuntimeError:
        logger.warning("Modal SDK unavailable — skipping job completion poll")
        return resolved_ids

    for job in jobs:
        try:
            fc = modal.FunctionCall.from_id(job.modal_function_id)
            call_result = fc.get(timeout=0)

            if call_result and isinstance(call_result, dict):
                await db.execute(
                    update(FineTuningJob)
                    .where(FineTuningJob.id == job.id)
                    .values(
                        status="completed",
                        training_metrics=call_result.get("metrics", {}),
                        lora_adapter_path=call_result.get("adapter_path"),
                        cost=call_result.get("cost"),
                        completed_at=datetime.now(UTC),
                    )
                )
                await db.flush()

                if call_result.get("cost"):
                    await record_spend(db, job.id, call_result["cost"])

                logger.info(
                    "Job %s completed via Modal poll. adapter=%s loss=%s",
                    job.id,
                    call_result.get("adapter_path"),
                    call_result.get("final_loss"),
                )
            else:
                await finalize_job(db, job.id)

        except Exception as exc:
            exc_str = str(exc)
            if _is_still_running(exc_str):
                continue

            await fail_job(db, job.id, exc_str[:2000])
            logger.warning("Modal job %s failed during poll: %s", job.id, exc_str[:200])

        resolved_ids.append(job.id)

    return resolved_ids


def _is_still_running(exc_str: str) -> bool:
    """
    Return True if the exception string indicates the Modal function is still
    running (hasn't returned yet).

    Modal raises various errors for in-progress calls — the message typically
    contains phrases like ``timed out`` or ``not ready``.
    """
    lower = exc_str.lower()
    return any(
        phrase in lower
        for phrase in (
            "timed out",
            "timeout",
            "not ready",
            "still running",
            "hasn't returned",
            "in progress",
        )
    )
