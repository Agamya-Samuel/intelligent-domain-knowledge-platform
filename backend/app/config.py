"""
IDKP Backend — application settings loaded from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "IDKP Backend"
    DEBUG: bool = True
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://idkp:idkp_secret@localhost:5432/idkp"

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Auth (Auth.js v5 / NextAuth) ─────────────────────────────
    AUTH_SECRET: str = "change-me-in-production"
    AUTH_TRUST_HOST: bool = True

    # ── Modal.com ────────────────────────────────────────────────
    MODAL_TOKEN_ID: str = ""
    MODAL_TOKEN_SECRET: str = ""

    # ── AWS S3 ───────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "idkp-documents-dev"

    # ── Qdrant ───────────────────────────────────────────────────
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""

    # ── Langfuse ─────────────────────────────────────────────────
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://localhost:3001"

    # ── Document Ingestion ───────────────────────────────────────
    UPLOAD_MAX_FILE_SIZE_MB: int = 50
    UPLOAD_CHUNK_SIZE: int = 1000
    UPLOAD_CHUNK_OVERLAP: int = 200
    SUPPORTED_FILE_TYPES: str = ".pdf,.txt,.md,.docx"

    # ── Embedding ─────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_DEVICE: str = "cpu"  # "cpu" or "cuda"

    # ── RAG Pipeline ──────────────────────────────────────────────
    QDRANT_COLLECTION: str = "idkp_documents"
    RAG_TOP_K: int = 5
    RAG_MIN_SCORE: float = 0.5
    RAG_MAX_CONTEXT_TOKENS: int = 4096

    # ── LLM Inference (Modal vLLM) ────────────────────────────────
    LLM_BASE_URL: str = "http://localhost:8001"  # vLLM OpenAI-compatible endpoint
    LLM_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.3
    LLM_STREAM: bool = True

    # ── Budget ────────────────────────────────────────────────────
    BUDGET_MONTHLY_LIMIT: float = 30.00

    # ── Evaluation / RAGAS ─────────────────────────────────────────
    EVAL_LLM_BASE_URL: str = ""  # defaults to LLM_BASE_URL if empty
    EVAL_LLM_MODEL: str = ""     # defaults to LLM_MODEL if empty
    EVAL_LLM_API_KEY: str = "not-needed"
    EVAL_MAX_CONCURRENCY: int = 3   # max parallel RAG pipeline calls during eval
    EVAL_TIMEOUT_SECONDS: int = 300 # total timeout for a full evaluation run

    # ── QLoRA Fine-tuning ──────────────────────────────────────────
    QLORA_RANK: int = 64               # LoRA rank (higher = more capacity)
    QLORA_ALPHA: int = 128             # LoRA alpha scaling factor
    QLORA_DROPOUT: float = 0.05        # LoRA dropout rate
    QLORA_LEARNING_RATE: float = 2e-4  # Initial learning rate
    QLORA_NUM_EPOCHS: int = 3          # Default training epochs
    QLORA_BATCH_SIZE: int = 4          # Per-device batch size
    QLORA_GRAD_ACCUM_STEPS: int = 4    # Gradient accumulation steps
    QLORA_MAX_SEQ_LENGTH: int = 2048   # Max sequence length for training
    QLORA_CHECKPOINT_STEPS: int = 50   # Save checkpoint every N steps
    CHECKPOINT_S3_PREFIX: str = "checkpoints"  # S3 prefix for checkpoints
    MODAL_VOLUME_NAME: str = "idkp-models"     # Modal Volume for base model persistence


settings = Settings()


# ── Model Catalog (static configuration — TRD §4.2) ───────────────
MODEL_CATALOG: list[dict] = [
    # Tier 0 — Compact
    {"id": "qwen2.5-7b", "name": "Qwen 2.5 7B-Instruct", "tier": 0, "size": "7B",
     "gpu": "A10G", "vram_gb": 6.5, "est_cost": 2.0, "est_time_min": 30,
     "license": "Apache 2.0", "available": True, "quality_rating": 0.75},
    {"id": "gemma4-e4b", "name": "Gemma 4 E4B", "tier": 0, "size": "4B",
     "gpu": "A10G", "vram_gb": 5.0, "est_cost": 1.0, "est_time_min": 20,
     "license": "Gemma", "available": True, "quality_rating": 0.70},
    # Tier 1 — Standard (Primary)
    {"id": "qwen2.5-14b", "name": "Qwen 2.5 14B-Instruct", "tier": 1, "size": "14B",
     "gpu": "A10G", "vram_gb": 8.5, "est_cost": 3.5, "est_time_min": 60,
     "license": "Apache 2.0", "available": True, "quality_rating": 0.85},
    {"id": "ministral3-14b", "name": "Mistral Ministral 3 14B-Instruct", "tier": 1, "size": "14B",
     "gpu": "A10G", "vram_gb": 9.0, "est_cost": 4.0, "est_time_min": 65,
     "license": "Apache 2.0", "available": True, "quality_rating": 0.83},
    {"id": "deepseek-r1-14b", "name": "DeepSeek-R1 Distill Qwen 14B", "tier": 1, "size": "14B",
     "gpu": "A10G", "vram_gb": 8.5, "est_cost": 3.5, "est_time_min": 55,
     "license": "MIT", "available": True, "quality_rating": 0.84},
    # Tier 2 — Enhanced
    {"id": "qwen2.5-32b", "name": "Qwen 2.5 32B-Instruct", "tier": 2, "size": "32B",
     "gpu": "L40S", "vram_gb": 24.0, "est_cost": 12.0, "est_time_min": 90,
     "license": "Apache 2.0", "available": True, "quality_rating": 0.92},
    {"id": "gemma4-31b", "name": "Gemma 4 31B", "tier": 2, "size": "31B",
     "gpu": "L40S", "vram_gb": 26.0, "est_cost": 14.0, "est_time_min": 100,
     "license": "Gemma", "available": True, "quality_rating": 0.90},
    # Tier 3 — Maximum
    {"id": "qwen2.5-72b", "name": "Qwen 2.5 72B-Instruct", "tier": 3, "size": "72B",
     "gpu": "A100-80GB", "vram_gb": 41.0, "est_cost": 28.0, "est_time_min": 180,
     "license": "Apache 2.0", "available": True, "quality_rating": 0.96},
    {"id": "llama3.3-70b", "name": "Llama 3.3 70B-Instruct", "tier": 3, "size": "70B",
     "gpu": "A100-80GB", "vram_gb": 40.0, "est_cost": 25.0, "est_time_min": 170,
     "license": "Llama 3.3", "available": True, "quality_rating": 0.95},
]
