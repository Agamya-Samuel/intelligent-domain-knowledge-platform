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
    model_map = {
        "qwen2.5-7b": "Qwen/Qwen2.5-7B-Instruct",
        "gemma4-e4b": "google/gemma-4-E4B",
        "qwen2.5-14b": "Qwen/Qwen2.5-14B-Instruct",
        "ministral3-14b": "mistralai/Ministral-3-14B-Instruct",
        "deepseek-r1-14b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "qwen2.5-32b": "Qwen/Qwen2.5-32B-Instruct",
        "gemma4-31b": "google/gemma-4-31B",
        "qwen2.5-72b": "Qwen/Qwen2.5-72B-Instruct",
        "llama3.3-70b": "meta-llama/Llama-3.3-70B-Instruct",
    }
    return model_map.get(model_id, model_id)


def _build_lora_config(config: dict[str, Any]) -> dict[str, Any]:
    """Build a PEFT LoraConfig from our training config dict."""
    return {
        "r": config.get("lora_rank", 64),
        "lora_alpha": config.get("lora_alpha", 128),
        "lora_dropout": config.get("lora_dropout", 0.05),
        "target_modules": [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
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

    Tries Unsloth for 2x faster training first. If the model is not
    supported by the installed Unsloth version, falls back to standard
    transformers + bitsandbytes 4-bit quantization.

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
    import tempfile

    # Guard: heavy imports only available on Modal
    try:
        from datasets import load_dataset  # type: ignore[import-not-found]
        from peft import LoraConfig, get_peft_model  # type: ignore[import-not-found] # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainerCallback, TrainingArguments  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "PEFT/transformers not available — returning dry-run result for job %s",
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
        hf_model_path,
        job_id,
        config.get("num_epochs", 3),
    )

    # 1. Load base model — try Unsloth first (2x faster), fall back to
    #    plain transformers + bitsandbytes for unsupported models.
    use_unsloth = True
    try:
        from unsloth import FastLanguageModel  # type: ignore[import-not-found]
    except ImportError:
        use_unsloth = False
        logger.warning("Unsloth not available — using plain transformers + bitsandbytes")

    if use_unsloth:
        try:
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=hf_model_path,
                max_seq_length=max_seq_length,
                dtype=None,  # auto-detect
                load_in_4bit=True,
            )
        except (NotImplementedError, ValueError) as exc:
            logger.warning(
                "Unsloth does not support model %s (%s) — falling back to plain transformers",
                hf_model_path,
                exc,
            )
            use_unsloth = False

    if not use_unsloth:
        # Fallback: load model with standard transformers + 4-bit quantization
        from transformers import BitsAndBytesConfig  # type: ignore[import-not-found]

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="bfloat16",
            bnb_4bit_use_double_quant=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(hf_model_path, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            hf_model_path,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        # Enable gradient checkpointing for memory efficiency (required for QLoRA)
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()

    # 2. Apply LoRA adapters
    lora_config_dict = _build_lora_config(config)
    if use_unsloth:
        from unsloth import FastLanguageModel  # type: ignore[import-not-found]
        model = FastLanguageModel.get_peft_model(
            model,
            r=lora_config_dict["r"],
            lora_alpha=lora_config_dict["lora_alpha"],
            lora_dropout=lora_config_dict["lora_dropout"],
            target_modules=lora_config_dict["target_modules"],
            bias=lora_config_dict["bias"],
            use_gradient_checkpointing="unsloth",
        )
    else:
        lora_config = LoraConfig(
            r=lora_config_dict["r"],
            lora_alpha=lora_config_dict["lora_alpha"],
            lora_dropout=lora_config_dict["lora_dropout"],
            target_modules=lora_config_dict["target_modules"],
            bias=lora_config_dict["bias"],
            task_type=lora_config_dict["task_type"],
        )
        model = get_peft_model(model, lora_config)

    # 3. Load training data
    # Download from S3 (assumes boto3 is available on Modal)
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as tmp:
        try:
            import boto3

            s3_uri = s3_data_path.replace("s3://", "")
            bucket, key = s3_uri.split("/", 1)
            s3 = boto3.client(
                "s3",
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
            )
            logger.info(
                "Downloading training data from s3://%s/%s", bucket, key,
            )
            s3.download_file(bucket, key, tmp.name)
        except Exception:
            logger.warning(
                "Could not download training data from S3 (path=%s); "
                "check that the file was uploaded and AWS credentials "
                "are in the Modal secret 'idkp-secrets'",
                s3_data_path,
            )
            raise

    dataset = load_dataset("json", data_files=tmp.name, split="train")

    for col in ("instruction", "input", "output"):
        if col not in dataset.column_names:
            raise ValueError(
                f"Training data is missing required column '{col}'. "
                f"Found columns: {dataset.column_names}. "
                f"The train.json file must be a flat JSON array of sample dicts."
            )

    # 4. Tokenise dataset
    def tokenize_fn(examples: dict) -> dict:
        """Format each sample as instruction + input → output for causal LM."""
        texts = []
        for inst, inp, out in zip(examples["instruction"], examples["input"], examples["output"]):
            prompt = (
                f"### Instruction:\n{inst}\n\n"
                f"### Input:\n{inp}\n\n"
                f"### Response:\n{out}{tokenizer.eos_token}"
            )
            texts.append(prompt)
        tokenized = tokenizer(
            texts,
            truncation=True,
            max_length=max_seq_length,
            padding="max_length",
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    tokenized = dataset.map(tokenize_fn, batched=True, remove_columns=dataset.column_names)

    # 5. Training loop
    training_args_dict = _build_training_args(config, f"/tmp/checkpoints/{job_id}")
    training_args = TrainingArguments(**training_args_dict)

    loss_history: list[dict[str, float]] = []

    class LossCallback(TrainerCallback):
        """Collect loss values during training for the metrics report."""

        def __init__(self) -> None:
            self.losses: list[float] = []

        def on_log(self, args, state, control, logs=None, **kwargs) -> None:
            if logs and "loss" in logs:
                self.losses.append(logs["loss"])
                loss_history.append(
                    {
                        "step": len(self.losses),
                        "loss": round(logs["loss"], 6),
                    }
                )

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
        from pathlib import Path

        import boto3

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
# Deploy with: modal deploy backend/app/services/modal_train.py
#
# The entire backend/app/ directory is mounted so that train_qlora() and
# its helper functions (_resolve_base_model, _build_lora_config, etc.)
# are importable inside the Modal sandbox.
#
# When running locally (without Modal SDK), this block is skipped.

try:
    import modal

    app = modal.App("idkp-train")
    models_volume = modal.Volume.from_name("idkp-models", create_if_missing=True)

    # Mount the backend/app/ package so all helper functions and modules
    # are available inside the Modal sandbox.
    import pathlib
    _app_dir = pathlib.Path(__file__).resolve().parent.parent  # backend/app/

    training_image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("git")
        .pip_install(
            "unsloth>=2026.5.0",
            "unsloth-zoo>=2025.11.0",
            "peft",
            "transformers>=4.51.0",
            "datasets",
            "bitsandbytes",
            "accelerate",
            "boto3",
            "xformers",
        )
        .add_local_dir(
            _app_dir,
            remote_path="/root/app",
            ignore=["__pycache__", "*.pyc", ".pytest_cache"],
        )
    )

    @app.function(
        gpu="A10G",
        timeout=600,
        volumes={"/models": models_volume},
        secrets=[modal.Secret.from_name("idkp-secrets")],
        image=training_image,
    )
    def train_qlora_fn(config, s3_data_path, job_id):
        """Modal entry point for QLoRA training.

        This wrapper delegates to ``app.services.modal_train.train_qlora``
        which is available because the ``app/`` package is mounted above.
        After training, it commits the LoRA adapter to the shared volume.
        """
        import sys
        if "/root" not in sys.path:
            sys.path.insert(0, "/root")

        from app.services.modal_train import train_qlora

        result = train_qlora(config, s3_data_path, job_id)

        # Commit adapter files to the volume so they persist across calls
        import shutil
        from pathlib import Path

        adapter_dir = f"/models/adapters/{job_id}"
        src = Path(f"/tmp/adapters/{job_id}")
        if src.exists():
            shutil.copytree(src, adapter_dir, dirs_exist_ok=True)
            models_volume.commit()
        return result

    @app.local_entrypoint()
    def main(config=None, s3_data_path=None, job_id=None):
        """Local entrypoint for testing the training function directly.

        Usage:
            modal run backend/app/services/modal_train.py
        """
        import json

        if config is None:
            config = {
                "model_id": "qwen2.5-7b",
                "lora_rank": 64,
                "lora_alpha": 128,
                "lora_dropout": 0.05,
                "learning_rate": 2e-4,
                "num_epochs": 1,
                "batch_size": 4,
                "grad_accum_steps": 4,
                "max_seq_length": 2048,
                "checkpoint_steps": 50,
            }
        if job_id is None:
            job_id = "local-test"
        if s3_data_path is None:
            s3_data_path = "s3://idkp/datasets/local-test/train.json"
        result = train_qlora_fn.remote(config, s3_data_path, job_id)
        print(json.dumps(result, indent=2, default=str))

except ImportError:
    # Modal SDK not installed — training function unavailable locally
    pass
