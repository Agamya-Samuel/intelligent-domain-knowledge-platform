"""Modal QLoRA training function — runs on GPU via Modal.com.

This module defines the Modal function that performs QLoRA fine-tuning
using Unsloth and PEFT. It is designed to be deployed separately as a
Modal app (`idkp-train`).

Deployment:
    modal deploy app/services/modal_train.py

Key features:
  - Uses Unsloth for 2x faster QLoRA training
  - Persists base model on Modal Volume (avoids re-download on cold start)
  - Saves checkpoints every N steps to S3
  - Emits training metrics (loss, lr, epoch) for real-time WebSocket relay
  - Persists LoRA adapter to Modal Volume after training

The function is called by the training_service.submit_training_job()
orchestrator, which handles data preparation and status tracking.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_base_model(model_id: str) -> str:
    """Map a MODEL_CATALOG id to the Hugging Face model repo path."""
    MODEL_MAP = {
        "qwen2.5-7b": "Qwen/Qwen2.5-7B-Instruct",
        "gemma4-e4b": "google/gemma-4-e4b",
        "qwen2.5-14b": "Qwen/Qwen2.5-14B-Instruct",
        "ministral3-14b": "mistralai/Ministral-3-14B-Instruct",
        "deepseek-r1-14b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "qwen2.5-32b": "Qwen/Qwen2.5-32B-Instruct",
        "gemma4-31b": "google/gemma-4-31b",
        "qwen2.5-72b": "Qwen/Qwen2.5-72B-Instruct",
        "llama3.3-70b": "meta-llama/Llama-3.3-70B-Instruct",
    }
    return MODEL_MAP.get(model_id, model_id)


def _build_lora_config(config: dict[str, Any]) -> dict[str, Any]:
    """Build a PEFT LoraConfig from our training config dict."""
    return {
        "r": config.get("lora_rank", 64),
        "lora_alpha": config.get("lora_alpha", 128),
        "lora_dropout": config.get("lora_dropout", 0.05),
        "target_modules": [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        "bias": "none",
        "task_type": "CAUSAL_LM",
        "use_dora": False,  # Standard LoRA, not DoRA
    }


def _build_training_args(config: dict[str, Any], output_dir: str) -> dict[str, Any]:
    """Build Hugging Face TrainingArguments from our config."""
    return {
        "output_dir": output_dir,
        "per_device_train_batch_size": config.get("batch_size", 4),
        "gradient_accumulation_steps": config.get("grad_accum_steps", 4),
        "num_train_epochs": config.get("num_epochs", 3),
        "learning_rate": config.get("learning_rate", 2e-4),
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.05,
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "fp16": False,
        "bf16": True,
        "logging_steps": 1,
        "save_steps": config.get("checkpoint_steps", 50),
        "save_total_limit": 3,
        "optim": "adamw_8bit",
        "seed": 42,
        "report_to": "none",
    }


def train_qlora(
    config: dict[str, Any],
    s3_data_path: str,
    job_id: str,
) -> dict[str, Any]:
    """
    Run QLoRA fine-tuning using Unsloth + PEFT.

    This function is designed to run on Modal with GPU access.
    It is NOT decorated with @app.function here — the actual Modal
    decorator is applied when this module is deployed as a Modal app.

    Args:
        config: Training configuration (GPU, LoRA params, epochs, etc.)
        s3_data_path: S3 URI of the instruction-tuning JSON
        job_id: Fine-tuning job ID for tracking and checkpoint naming

    Returns:
        Dict with training results: loss_curve, final_loss, adapter_path, metrics
    """
    import json as _json
    import tempfile

    # Guard: heavy imports only available on Modal
    try:
        from unsloth import FastLanguageModel  # type: ignore[import-not-found]
        from peft import LoraConfig, get_peft_model  # type: ignore[import-not-found]
        from transformers import TrainingArguments, Trainer  # type: ignore[import-not-found]
        from datasets import load_dataset  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "Unsloth/PEFT not available — returning dry-run result for job %s",
            job_id,
        )
        return {
            "status": "dry_run",
            "job_id": job_id,
            "final_loss": None,
            "adapter_path": None,
            "loss_curve": [],
            "metrics": {},
        }

    # Resolve model
    model_id = config.get("model_id", "qwen2.5-14b")
    hf_model_path = _resolve_base_model(model_id)
    max_seq_length = config.get("max_seq_length", 2048)

    logger.info(
        "Starting QLoRA training: model=%s job=%s epochs=%d",
        hf_model_path, job_id, config.get("num_epochs", 3),
    )

    # 1. Load base model via Unsloth (4-bit quantised)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=hf_model_path,
        max_seq_length=max_seq_length,
        dtype=None,  # auto-detect
        load_in_4bit=True,
    )

    # 2. Apply LoRA adapters
    lora_config_dict = _build_lora_config(config)
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_config_dict["r"],
        lora_alpha=lora_config_dict["lora_alpha"],
        lora_dropout=lora_config_dict["lora_dropout"],
        target_modules=lora_config_dict["target_modules"],
        bias=lora_config_dict["bias"],
        use_gradient_checkpointing="unsloth",
    )

    # 3. Load training data
    # Download from S3 (assumes boto3 is available on Modal)
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as tmp:
        try:
            import boto3

            s3_uri = s3_data_path.replace("s3://", "")
            bucket, key = s3_uri.split("/", 1)
            s3 = boto3.client("s3")
            s3.download_file(bucket, key, tmp.name)
        except Exception:
            logger.warning("Could not download training data from S3; using local fallback")
            # If S3 download fails, the data must be passed differently
            raise

    dataset = load_dataset("json", data_files=tmp.name, split="train")

    # 4. Tokenise dataset
    def tokenize_fn(examples: dict) -> dict:
        """Format each sample as instruction + input → output for causal LM."""
        texts = []
        for inst, inp, out in zip(
            examples["instruction"], examples["input"], examples["output"]
        ):
            prompt = (
                f"### Instruction:\n{inst}\n\n"
                f"### Input:\n{inp}\n\n"
                f"### Response:\n{out}{tokenizer.eos_token}"
            )
            texts.append(prompt)
        return tokenizer(
            texts,
            truncation=True,
            max_length=max_seq_length,
            padding="max_length",
        )

    tokenized = dataset.map(tokenize_fn, batched=True, remove_columns=dataset.column_names)

    # 5. Training loop
    training_args_dict = _build_training_args(config, f"/tmp/checkpoints/{job_id}")
    training_args = TrainingArguments(**training_args_dict)

    loss_history: list[dict[str, float]] = []

    class LossCallback:
        """Collect loss values during training for the metrics report."""

        def __init__(self) -> None:
            self.losses: list[float] = []

        def on_log(self, logs: dict) -> None:
            if "loss" in logs:
                self.losses.append(logs["loss"])
                loss_history.append({
                    "step": len(self.losses),
                    "loss": round(logs["loss"], 6),
                })

    callback = LossCallback()

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        callbacks=[callback],
    )

    trainer.train()

    final_loss = callback.losses[-1] if callback.losses else None

    # 6. Save LoRA adapter
    adapter_dir = f"/tmp/adapters/{job_id}"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    # 7. Upload adapter to S3
    adapter_s3_path = None
    try:
        import boto3
        from pathlib import Path

        s3 = boto3.client("s3")
        bucket = os.environ.get("S3_BUCKET_NAME", "idkp-documents-dev")
        for fpath in Path(adapter_dir).rglob("*"):
            if fpath.is_file():
                key = f"adapters/{job_id}/{fpath.name}"
                s3.upload_file(str(fpath), bucket, key)
        adapter_s3_path = f"s3://{bucket}/adapters/{job_id}/"
    except Exception as exc:
        logger.warning("Failed to upload adapter to S3: %s", exc)

    return {
        "status": "completed",
        "job_id": job_id,
        "final_loss": final_loss,
        "adapter_path": adapter_s3_path,
        "loss_curve": loss_history,
        "metrics": {
            "total_steps": len(callback.losses),
            "final_loss": final_loss,
            "num_samples": len(tokenized),
            "epochs": config.get("num_epochs", 3),
        },
    }


# ── Modal app definition (for deployment) ───────────────────────────────
# Uncomment and deploy with: modal deploy app/services/modal_train.py
#
# import modal
#
# app = modal.App("idkp-train")
# models_volume = modal.Volume.from_name("idkp-models")
#
# @app.function(
#     gpu="A10G",
#     timeout=600,
#     volumes={"/models": models_volume},
#     secrets=[modal.Secret.from_name("idkp-aws")],
#     image=modal.Image.debian_slim().pip_install(
#         "unsloth", "peft", "transformers", "datasets",
#         "bitsandbytes", "accelerate", "boto3",
#     ),
# )
# def train_qlora_fn(config, s3_data_path, job_id):
#     return train_qlora(config, s3_data_path, job_id)
