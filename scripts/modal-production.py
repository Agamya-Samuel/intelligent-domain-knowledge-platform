"""
Modal Production Functions — GPU inference, embeddings, and reranking.

Production Modal function definitions for IDKP:
  - Inference (A10G): vLLM serving with LoRA hot-swap support
  - Embeddings (T4): BAAI/bge-m3 dense embeddings
  - Reranker (T4): BAAI/bge-reranker-v2-m3 cross-encoder

Each function is deployed independently with scale-to-zero.
The inference function supports LoRA adapter hot-swapping via
the /v1/load/adapter endpoint (vLLM feature).

Usage:
    modal deploy scripts/modal-production.py

Environment:
    Modal token must be configured (modal token new / set MODAL_TOKEN_ID + MODAL_TOKEN_SECRET).
"""

from pathlib import Path

import modal

# ── Modal App ────────────────────────────────────────────────────────────

app = modal.App("idkp-production")

# ── Shared Volume for model weights and checkpoints ─────────────────────

model_volume = modal.Volume.from_name(
    "idkp-models",
    create_if_missing=True,
)
MODEL_DIR = "/models"

# ── Shared image with GPU dependencies ───────────────────────────────────

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.7.3",
        "torch>=2.4.1",
        "sentence-transformers>=3.3.1",
        "FlagEmbedding>=1.3.2",
        "boto3>=1.35.0",
    )
)

# ─────────────────────────────────────────────────────────────────────────
# Inference Function — vLLM on A10G (24GB VRAM)
# ─────────────────────────────────────────────────────────────────────────


@app.function(
    image=gpu_image,
    gpu="A10G",
    volumes={MODEL_DIR: model_volume},
    secrets=[modal.Secret.from_name("idkp-secrets")],
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=8000)
def inference():
    """
    vLLM inference server with LoRA hot-swap.

    Serves via vllm serve CLI subprocess (OpenAI-compatible API).
    Supports loading LoRA adapters from Modal Volume at
    /models/adapters/latest (symlink to the most recent fine-tuning job).

    GPU: NVIDIA A10G (24GB) — supports up to 14B models.
    Scale: 0 (cold start) to 4 concurrent containers.
    """
    import os
    import subprocess

    os.environ["VLLM_ALLOW_RUNTIME_LORA_UPDATING"] = "1"

    model_name = "Qwen/Qwen2.5-7B-Instruct"
    model_path = f"{MODEL_DIR}/{model_name.replace('/', '-')}"

    if Path(model_path).exists():
        model_name = model_path

    adapters_dir = Path(f"{MODEL_DIR}/adapters")
    adapters_dir.mkdir(parents=True, exist_ok=True)
    latest_link = adapters_dir / "latest"
    if not latest_link.exists():
        adapters = sorted([d for d in adapters_dir.iterdir() if d.is_dir() and d.name != "latest"])
        if adapters:
            latest_link.symlink_to(adapters[-1])

    engine_args = [
        "--host", "0.0.0.0",
        "--port", "8000",
        "--model", model_name,
        "--dtype", "auto",
        "--max-model-len", "4096",
        "--gpu-memory-utilization", "0.90",
        "--enable-lora",
        "--lora-modules", "default-adapters=/models/adapters/latest",
        "--max-lora-rank", "64",
    ]

    subprocess.Popen(["vllm", "serve"] + engine_args)


# ─────────────────────────────────────────────────────────────────────────
# Embeddings Function — sentence-transformers on T4
# ─────────────────────────────────────────────────────────────────────────


@app.function(
    image=gpu_image,
    gpu="T4",
    secrets=[modal.Secret.from_name("idkp-secrets")],
)
@modal.concurrent(max_inputs=20)
@modal.web_server(port=8000)
def embeddings():
    """
    Dense embedding service using BAAI/bge-m3.

    Provides an OpenAI-compatible /v1/embeddings endpoint.
    Used by the RAG pipeline for document chunk and query encoding.

    GPU: NVIDIA T4 (16GB) — sufficient for bge-m3 (1024-dim).
    Scale: 0 (cold start) to 2 concurrent containers.
    """
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="IDKP Embeddings", version="1.0.0")
    model = None  # type: ignore

    @app.on_event("startup")
    async def load_model():
        nonlocal model
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3", device="cuda")

    class EmbedRequest(BaseModel):
        input: list[str] | str
        model: str = "BAAI/bge-m3"

    class EmbedData(BaseModel):
        object: str = "embedding"
        index: int
        embedding: list[float]

    class EmbedResponse(BaseModel):
        object: str = "list"
        data: list[EmbedData]
        model: str
        usage: dict

    @app.post("/v1/embeddings")
    async def create_embeddings(body: EmbedRequest):
        texts = body.input if isinstance(body.input, list) else [body.input]
        embeddings = model.encode(texts, normalize_embeddings=True)
        data = [
            EmbedData(object="embedding", index=i, embedding=emb.tolist())
            for i, emb in enumerate(embeddings)
        ]
        return EmbedResponse(
            object="list",
            data=data,
            model=body.model,
            usage={"prompt_tokens": sum(len(t.split()) for t in texts), "total_tokens": sum(len(t.split()) for t in texts)},
        )

    @app.get("/health")
    async def health():
        return {"status": "healthy", "model": "BAAI/bge-m3", "dimension": 1024}

    return app


# ─────────────────────────────────────────────────────────────────────────
# Reranker Function — cross-encoder on T4
# ─────────────────────────────────────────────────────────────────────────


@app.function(
    image=gpu_image,
    gpu="T4",
    secrets=[modal.Secret.from_name("idkp-secrets")],
)
@modal.concurrent(max_inputs=20)
@modal.web_server(port=8000)
def reranker():
    """
    Cross-encoder reranking service using BAAI/bge-reranker-v2-m3.

    Provides a /v1/rerank endpoint compatible with Cohere's rerank API.
    Used by the RAG pipeline to re-rank retrieved chunks after fusion.

    GPU: NVIDIA T4 (16GB) — sufficient for bge-reranker-v2-m3.
    Scale: 0 (cold start) to 2 concurrent containers.
    """
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="IDKP Reranker", version="1.0.0")
    model = None  # type: ignore

    @app.on_event("startup")
    async def load_model():
        nonlocal model
        from FlagEmbedding import FlagReranker
        model = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True, device="cuda")

    class RerankRequest(BaseModel):
        query: str
        documents: list[str]
        top_n: int = 5
        model: str = "BAAI/bge-reranker-v2-m3"

    class RerankResult(BaseModel):
        index: int
        document: str
        relevance_score: float

    class RerankResponse(BaseModel):
        model: str
        results: list[RerankResult]

    @app.post("/v1/rerank")
    async def rerank_documents(body: RerankRequest):
        pairs = [[body.query, doc] for doc in body.documents]
        scores = model.compute_score(pairs, normalize=True)

        if not isinstance(scores, list):
            scores = [scores]

        ranked = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:body.top_n]

        results = [
            RerankResult(
                index=idx,
                document=body.documents[idx],
                relevance_score=float(scores[idx]),
            )
            for idx in ranked
        ]

        return RerankResponse(model=body.model, results=results)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "model": "BAAI/bge-reranker-v2-m3"}

    return app
