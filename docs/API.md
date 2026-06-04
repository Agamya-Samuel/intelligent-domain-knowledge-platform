# API Documentation

## Overview

IDKP exposes a REST API at `/api/v1/` built with **FastAPI**. All endpoints return JSON. Interactive OpenAPI docs are available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when the server is running.

**Base URL:** `http://localhost:8000` (development) / `https://api.idkp.local` (production)

### Authentication

All endpoints except `/health` require authentication via a **Bearer JWT token** in the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

The token is issued by NextAuth.js v5 on the frontend and validated server-side via JWE/JWT decode using a shared `AUTH_SECRET`. The token payload contains `sub` (user ID), `email`, and `name` claims.

### Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes (except `/health`) | Bearer JWT token |
| `Content-Type` | Yes for POST/PATCH | `application/json` |
| `Accept` | Optional | `application/json` (default) or `text/event-stream` (SSE) |

### Common Error Responses

| Status | Description |
|--------|-------------|
| `400` | Bad request — malformed input |
| `401` | Unauthorized — missing or invalid token |
| `403` | Forbidden — authenticated but not authorized (e.g. budget exceeded) |
| `404` | Not found — resource does not exist |
| `422` | Validation error — request body failed schema validation |
| `429` | Too many requests — rate limit exceeded |
| `500` | Internal server error |

### Rate Limiting

Redis-based sliding window rate limiting (configurable via `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` in `.env`). Returns `429` with headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1718000000
```

---

## 1. Health

### `GET /health`

Returns service health status. No authentication required.

**Response `200`:**

```json
{
  "status": "ok"
}
```

---

## 2. Authentication

### `GET /api/v1/auth/me`

Returns the currently authenticated user's profile.

**Response `200`:**

```json
{
  "id": "a1b2c3d4-...",
  "email": "user@example.com",
  "name": "Jane Doe",
  "image_url": "https://...",
  "created_at": "2026-01-15T10:30:00Z",
  "updated_at": "2026-01-15T10:30:00Z"
}
```

---

## 3. Documents

Manage uploaded documents through the parsing and chunking pipeline.

### `POST /api/v1/documents/upload`

Upload a new document. Accepts `multipart/form-data` with a file field.

**Request:**
- Content-Type: `multipart/form-data`
- Fields: `file` (required), `title` (optional)

**Response `201`:**

```json
{
  "id": "doc-uuid-1",
  "user_id": "user-uuid",
  "title": "Research Paper.pdf",
  "file_name": "Research_Paper.pdf",
  "file_type": "application/pdf",
  "file_size": 2048576,
  "status": "pending",
  "created_at": "2026-06-04T12:00:00Z"
}
```

### `GET /api/v1/documents/`

List all documents for the authenticated user.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `offset` | int | `0` | Pagination offset |
| `limit` | int | `20` | Max results (1–100) |

**Response `200`:**

```json
[
  {
    "id": "doc-uuid-1",
    "title": "Research Paper.pdf",
    "file_name": "Research_Paper.pdf",
    "file_type": "application/pdf",
    "file_size": 2048576,
    "status": "completed",
    "chunk_count": 42,
    "created_at": "2026-06-04T12:00:00Z",
    "updated_at": "2026-06-04T12:05:00Z"
  }
]
```

### `GET /api/v1/documents/{document_id}`

Get full details of a single document.

**Response `200`:**

```json
{
  "id": "doc-uuid-1",
  "user_id": "user-uuid",
  "title": "Research Paper.pdf",
  "description": "Overview of transformer architectures",
  "file_name": "Research_Paper.pdf",
  "file_type": "application/pdf",
  "file_size": 2048576,
  "s3_key": "documents/user-uuid/doc-uuid-1.pdf",
  "status": "completed",
  "processing_error": null,
  "chunk_count": 42,
  "created_at": "2026-06-04T12:00:00Z",
  "updated_at": "2026-06-04T12:05:00Z"
}
```

### `PATCH /api/v1/documents/{document_id}`

Update document metadata (title and/or description).

**Request Body:**

```json
{
  "title": "Updated Paper Title",
  "description": "New description"
}
```

**Response `200`:** Updated document detail (same schema as `GET /{document_id}`).

### `DELETE /api/v1/documents/{document_id}`

Delete a document and its associated chunks.

**Response `204`:** No content.

### `POST /api/v1/documents/{document_id}/process`

Trigger document processing (parsing, chunking, embedding).

**Response `200`:**

```json
{
  "id": "doc-uuid-1",
  "status": "processing",
  "chunk_count": 0,
  "message": "Document processing started"
}
```

### `GET /api/v1/documents/{document_id}/chunks`

List all chunks for a document.

**Response `200`:**

```json
[
  {
    "id": "chunk-uuid-1",
    "document_id": "doc-uuid-1",
    "chunk_index": 0,
    "content": "First chunk text...",
    "token_count": 512,
    "metadata_": {
      "page": 1,
      "section": "Introduction"
    },
    "created_at": "2026-06-04T12:05:00Z"
  }
]
```

---

## 4. Chat

RAG-powered chat with streaming support and session management.

### `POST /api/v1/chat/`

Send a chat query. Supports SSE streaming for real-time token delivery.

**Request Body:**

```json
{
  "query": "What is the RAG pipeline architecture?",
  "session_id": null,
  "model_variant": "base",
  "filters": {
    "doc_type": "pdf",
    "page": 1
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | User question (1–4096 chars) |
| `session_id` | string\|null | No | Existing session; creates new if null |
| `model_variant` | `"base"` \| `"finetuned"` | No | LLM variant (default: `"base"`) |
| `filters` | MetadataFilter\|null | No | Retrieval metadata filters |

**Response `200` (SSE stream):**

```
event: token
data: {"content": "The", "citations": null}

event: token
data: {"content": " RAG pipeline", "citations": null}

event: citation
data: {"source": "Research Paper.pdf", "page": 3, "section": "Architecture"}

event: done
data: {"latency_ms": 1850, "model_variant": "base", "citations_count": 2, "citation_accuracy": 0.95, "message_id": "msg-uuid", "session_id": "session-uuid"}
```

**SSE Event Types:**

| Event | Schema | Description |
|-------|--------|-------------|
| `token` | `SSETokenEvent` | Streaming text token |
| `citation` | `SSECitationEvent` | Source citation from retrieval |
| `done` | `SSEDoneEvent` | Stream complete with metadata |
| `error` | `SSEErrorEvent` | Error during streaming |

### `POST /api/v1/chat/sessions`

Create a new chat session.

**Request Body:**

```json
{
  "title": "Research Discussion"
}
```

**Response `201`:**

```json
{
  "id": "session-uuid",
  "user_id": "user-uuid",
  "title": "Research Discussion",
  "model_variant": "base",
  "created_at": "2026-06-04T12:00:00Z",
  "updated_at": "2026-06-04T12:00:00Z"
}
```

### `GET /api/v1/chat/sessions`

List all chat sessions for the authenticated user.

**Response `200`:** Array of `ChatSessionResponse`.

### `GET /api/v1/chat/sessions/{session_id}`

Get a session with all its messages.

**Response `200`:**

```json
{
  "id": "session-uuid",
  "user_id": "user-uuid",
  "title": "Research Discussion",
  "model_variant": "base",
  "messages": [
    {
      "id": "msg-uuid-1",
      "session_id": "session-uuid",
      "role": "user",
      "content": "What is RAG?",
      "citations": null,
      "latency_ms": null,
      "token_count": 12,
      "created_at": "2026-06-04T12:01:00Z"
    },
    {
      "id": "msg-uuid-2",
      "session_id": "session-uuid",
      "role": "assistant",
      "content": "RAG stands for...",
      "citations": [{"source": "Paper.pdf", "page": 1}],
      "latency_ms": 950,
      "token_count": 87,
      "created_at": "2026-06-04T12:01:02Z"
    }
  ],
  "created_at": "2026-06-04T12:00:00Z",
  "updated_at": "2026-06-04T12:01:02Z"
}
```

### `DELETE /api/v1/chat/sessions/{session_id}`

Delete a chat session and all its messages.

**Response `204`:** No content.

### `POST /api/v1/chat/sessions/{session_id}/model-variant`

Switch the active model variant for a session.

**Request Body:**

```json
{
  "model_variant": "finetuned"
}
```

**Response `200`:** Updated session response.

---

## 5. Datasets

Manage datasets for fine-tuning with versioning and source tracking.

### `POST /api/v1/datasets/`

Create a new dataset.

**Request Body:**

```json
{
  "name": "Domain Knowledge v1",
  "description": "Curated domain-specific Q&A pairs"
}
```

**Response `201`:**

```json
{
  "id": "ds-uuid-1",
  "name": "Domain Knowledge v1",
  "description": "Curated domain-specific Q&A pairs",
  "version": 1,
  "status": "active",
  "source_count": 0,
  "created_at": "2026-06-04T12:00:00Z",
  "updated_at": "2026-06-04T12:00:00Z"
}
```

### `GET /api/v1/datasets/`

List all datasets.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `offset` | int | `0` | Pagination offset |
| `limit` | int | `20` | Max results (1–100) |

**Response `200`:** Array of `DatasetResponse`.

### `GET /api/v1/datasets/{dataset_id}`

Get full dataset details including sources and version history.

**Response `200`:**

```json
{
  "id": "ds-uuid-1",
  "name": "Domain Knowledge v1",
  "description": "Curated domain-specific Q&A pairs",
  "version": 3,
  "status": "active",
  "domain_tags": ["ml", "nlp"],
  "sources": [
    {
      "id": "src-uuid-1",
      "dataset_id": "ds-uuid-1",
      "dataset_version": 3,
      "source_type": "pdf",
      "source_path": "documents/paper.pdf",
      "file_name": "paper.pdf",
      "file_size": 1024000,
      "mime_type": "application/pdf",
      "content_hash": "abc123",
      "processed": true,
      "processing_error": null,
      "created_at": "2026-06-04T12:00:00Z"
    }
  ],
  "version_history": [
    {
      "id": "vh-uuid-1",
      "dataset_id": "ds-uuid-1",
      "version": 2,
      "change_description": "Added 3 new sources",
      "source_count": 5,
      "sources_added": 3,
      "created_at": "2026-06-03T10:00:00Z"
    }
  ],
  "created_at": "2026-06-04T12:00:00Z",
  "updated_at": "2026-06-04T12:05:00Z"
}
```

### `PATCH /api/v1/datasets/{dataset_id}`

Update dataset metadata.

**Response `200`:** Updated dataset detail.

### `POST /api/v1/datasets/{dataset_id}/archive`

Soft-archive a dataset. Sets status to `archived`.

**Response `200`:** Updated dataset response.

### `POST /api/v1/datasets/{dataset_id}/sources`

Add a source to a dataset. Accepts `multipart/form-data` with a file field.

**Request:** Content-Type: `multipart/form-data`, field: `file`

**Response `201`:**

```json
{
  "source_id": "src-uuid-2",
  "dataset_version": 4,
  "file_name": "new_doc.pdf",
  "status": "processing"
}
```

### `GET /api/v1/datasets/{dataset_id}/sources`

List all sources for a dataset.

**Response `200`:** Array of `DatasetSourceResponse`.

### `DELETE /api/v1/datasets/{dataset_id}/sources/{source_id}`

Remove a source from a dataset.

**Response `204`:** No content.

---

## 6. Models

Read-only access to the model catalog.

### `GET /api/v1/models/`

List all models across all tiers.

**Response `200`:**

```json
{
  "models": [
    {
      "id": "qwen2.5-7b",
      "name": "Qwen 2.5 7B",
      "tier": 0,
      "size": "7B",
      "gpu": "T4",
      "vram_gb": 16.0,
      "est_cost": 2.50,
      "est_time_min": 15,
      "license": "apache-2.0",
      "available": true,
      "quality_rating": null
    }
  ]
}
```

### `GET /api/v1/models/{model_id}`

Get details for a specific model.

**Response `200`:** Single `ModelDetailResponse`.

**Response `404`:** Model not found.

---

## 7. Budget

Monthly budget tracking and remaining balance.

### `GET /api/v1/budget/`

Get current month's budget summary.

**Response `200`:**

```json
{
  "total_spend": 12.50,
  "remaining": 17.50,
  "budget_limit": 30.00,
  "runs_this_month": 3,
  "estimated_runs_left": 2,
  "period_start": "2026-06-01T00:00:00Z",
  "period_end": "2026-06-30T23:59:59Z"
}
```

---

## 8. Fine-Tuning

Trigger, monitor, and manage fine-tuning jobs. Jobs are queued FIFO with budget enforcement ($30/month cap).

### `POST /api/v1/fine-tune/`

Trigger a new fine-tuning job. Follows the validation flow from TRD §6.4:

1. Validate auth
2. Validate model exists in catalog
3. Validate dataset exists and is active
4. Budget check: `total_spend + estimated_cost <= $30`
5. Queue check: if a job is running, assign queue position
6. Create job record

**Request Body:**

```json
{
  "model_id": "qwen2.5-14b",
  "dataset_id": "ds-uuid-1"
}
```

**Response `202`:**

```json
{
  "job_id": "job-uuid-1",
  "status": "queued",
  "queue_position": null,
  "estimated_cost": 8.50
}
```

**Error Responses:**

| Status | Description |
|--------|-------------|
| `403` | Monthly budget exceeded — includes `remaining`, `estimated_cost`, `budget_limit` |
| `404` | Model or active dataset not found |

### `GET /api/v1/fine-tune/status/{job_id}`

Get the current status and metrics of a fine-tuning job.

**Response `200`:**

```json
{
  "id": "job-uuid-1",
  "user_id": "user-uuid",
  "model_id": "qwen2.5-14b",
  "dataset_id": "ds-uuid-1",
  "dataset_version": 3,
  "status": "completed",
  "queue_position": null,
  "training_metrics": {
    "final_loss": 0.234,
    "epochs": 3,
    "steps": 1500
  },
  "eval_report": {
    "faithfulness": 0.92,
    "context_relevance": 0.88
  },
  "cost": 8.50,
  "error_message": null,
  "started_at": "2026-06-04T12:10:00Z",
  "completed_at": "2026-06-04T12:45:00Z",
  "created_at": "2026-06-04T12:00:00Z"
}
```

**Job Status Lifecycle:** `queued` → `training` → `evaluating` → `completed` | `failed`

### `GET /api/v1/fine-tune/history`

List the authenticated user's fine-tuning job history.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `offset` | int | `0` | Pagination offset |
| `limit` | int | `20` | Max results (1–100) |

**Response `200`:**

```json
{
  "jobs": [
    { "id": "job-uuid-1", "status": "completed", ... }
  ]
}
```

### `GET /api/v1/fine-tune/estimate`

Pre-flight cost estimation without triggering a job.

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `model_id` | string | Yes | Model catalog ID |
| `dataset_id` | string | Yes | Dataset UUID |

**Response `200`:**

```json
{
  "model_id": "qwen2.5-14b",
  "estimated_cost": 8.50,
  "estimated_time_min": 35,
  "dataset_sample_count": 1500,
  "remaining_budget": 17.50,
  "within_budget": true
}
```

### `GET /api/v1/fine-tune/training-data/preview`

Preview instruction-tuning samples (first 10).

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_id` | string | Yes | Dataset UUID |

**Response `200`:**

```json
{
  "dataset_id": "ds-uuid-1",
  "dataset_version": 3,
  "total_samples": 1500,
  "domain_samples": 900,
  "general_samples": 600,
  "by_type": {
    "qa": 800,
    "summary": 300,
    "reasoning": 200,
    "general": 200
  },
  "preview_samples": [
    {
      "instruction": "Explain the RAG retrieval step",
      "input": "The system uses hybrid retrieval...",
      "output": "Hybrid retrieval combines BM25...",
      "domain": "domain",
      "type": "qa"
    }
  ]
}
```

### `POST /api/v1/fine-tune/training-data/export`

Export the full instruction-tuning dataset for S3 upload.

**Query Parameters:** `dataset_id` (required)

**Response `200`:** Same structure as preview but with all `samples` included.

---

## 9. Evaluation

RAGAS evaluation runs, benchmarks, and A/B comparisons.

### `POST /api/v1/evaluations/`

Trigger a RAGAS evaluation run. Runs synchronously.

**Request Body:**

```json
{
  "run_type": "baseline",
  "model_id": "qwen2.5-14b",
  "model_variant": "base",
  "job_id": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `run_type` | string | Yes | `baseline`, `post_training`, `weekly_regression`, `comparison`, `benchmark` |
| `model_id` | string\|null | No | Model to evaluate (defaults to base) |
| `model_variant` | string | No | `base` or `finetuned` (default: `"base"`) |
| `job_id` | string\|null | No | Link to fine-tuning job (for `post_training`) |

**Response `201`:**

```json
{
  "id": "eval-uuid-1",
  "run_type": "baseline",
  "status": "completed",
  "model_id": "qwen2.5-14b",
  "model_variant": "base",
  "job_id": null,
  "metrics": {
    "faithfulness": 0.91,
    "context_relevance": 0.87,
    "answer_relevance": 0.93,
    "context_recall": 0.85
  },
  "per_sample_scores": [
    {
      "question": "What is RAG?",
      "faithfulness": 0.95,
      "context_relevance": 0.90,
      "answer_relevance": 0.92,
      "context_recall": 0.88
    }
  ],
  "benchmark_config": null,
  "dataset_size": 50,
  "duration_seconds": 124.5,
  "error_message": null,
  "created_at": "2026-06-04T12:00:00Z",
  "updated_at": "2026-06-04T12:02:04Z"
}
```

### `GET /api/v1/evaluations/`

List evaluation run history.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `run_type` | string\|null | `null` | Filter by run type |
| `status` | string\|null | `null` | Filter by status |
| `offset` | int | `0` | Pagination offset |
| `limit` | int | `20` | Max results (1–100) |

**Response `200`:**

```json
{
  "evaluations": [...],
  "total": 15
}
```

### `GET /api/v1/evaluations/{eval_id}`

Get details of a specific evaluation run, including per-sample scores.

**Response `200`:** Single `EvaluationRunResponse`.

### `POST /api/v1/evaluations/benchmark`

Run a benchmark across multiple models from the MODEL_CATALOG.

**Request Body:**

```json
{
  "model_ids": ["qwen2.5-7b", "qwen2.5-14b", "llama3.1-8b"],
  "model_variant": "base",
  "job_id": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_ids` | list[string] | Yes | 1–5 model catalog IDs |
| `model_variant` | string | No | `base` or `finetuned` |
| `job_id` | string\|null | No | Fine-tuning job ID |

**Response `201`:**

```json
{
  "benchmark_id": "bm-20260604-abc",
  "results": [
    {
      "model_id": "qwen2.5-7b",
      "model_name": "Qwen 2.5 7B",
      "eval_run_id": "eval-uuid-2",
      "metrics": {
        "faithfulness": 0.88,
        "context_relevance": 0.82,
        "answer_relevance": 0.90,
        "context_recall": 0.80
      },
      "duration_seconds": 98.2,
      "status": "completed"
    }
  ],
  "total_models": 3,
  "created_at": "2026-06-04T12:00:00Z"
}
```

### `POST /api/v1/evaluations/compare`

A/B comparison between two completed evaluation runs.

**Request Body:**

```json
{
  "base_eval_id": "eval-uuid-1",
  "candidate_eval_id": "eval-uuid-2"
}
```

**Response `200`:**

```json
{
  "base_eval_id": "eval-uuid-1",
  "candidate_eval_id": "eval-uuid-2",
  "base_metrics": {
    "faithfulness": 0.85,
    "context_relevance": 0.80,
    "answer_relevance": 0.88,
    "context_recall": 0.78
  },
  "candidate_metrics": {
    "faithfulness": 0.92,
    "context_relevance": 0.88,
    "answer_relevance": 0.90,
    "context_recall": 0.85
  },
  "deltas": {
    "faithfulness_delta": 0.07,
    "context_relevance_delta": 0.08,
    "answer_relevance_delta": 0.02,
    "context_recall_delta": 0.07
  },
  "winner": "candidate"
}
```

---

## 10. Comparison

Side-by-side model comparison and dataset staleness detection.

### `POST /api/v1/compare`

Compare base vs. fine-tuned model responses for the same query.

**Request Body:**

```json
{
  "query": "Explain the retrieval-augmented generation pipeline",
  "base_model_id": "qwen2.5-14b",
  "finetuned_model_id": "qwen2.5-14b"
}
```

**Response `200`:**

```json
{
  "query": "Explain the retrieval-augmented generation pipeline",
  "base": {
    "variant": "base",
    "response": "RAG is a technique that...",
    "citations": [{"source": "Paper.pdf", "page": 2}],
    "latency_ms": 950,
    "token_count": 145
  },
  "finetuned": {
    "variant": "finetuned",
    "response": "The RAG pipeline consists of...",
    "citations": [{"source": "Paper.pdf", "page": 2}],
    "latency_ms": 820,
    "token_count": 162
  },
  "comparison": {
    "latency_delta_ms": -130,
    "token_count_delta": 17,
    "citation_overlap": 0.85,
    "response_length_delta": 17
  }
}
```

### `GET /api/v1/datasets/{dataset_id}/staleness`

Check whether a dataset has new sources since the last fine-tuning job.

**Response `200`:**

```json
{
  "dataset_id": "ds-uuid-1",
  "current_version": 5,
  "last_ft_version": 3,
  "sources_since_ft": 4,
  "is_stale": true,
  "message": "Dataset has 4 new sources since last fine-tune (v3 → v5). Re-training is recommended."
}
```

---

## 11. Analytics

Aggregated dashboard data for the frontend.

### `GET /api/v1/analytics/overview`

Combined overview of all analytics data. Aggregates metrics trend, job stats, chat stats, and budget trend in a single request.

**Response `200`:**

```json
{
  "metrics_trend": { "points": [...], "latest": {...} },
  "job_stats": { "total_jobs": 5, "completed": 3, ... },
  "chat_stats": { "total_sessions": 12, "total_messages": 87, ... },
  "budget_trend": { "points": [...], "current_spend": 12.50, ... }
}
```

### `GET /api/v1/analytics/metrics/trend`

RAGAS metrics over time for charting.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `20` | Max data points (1–100) |

**Response `200`:**

```json
{
  "points": [
    {
      "date": "2026-06-01T10:00:00Z",
      "run_type": "baseline",
      "faithfulness": 0.85,
      "context_relevance": 0.80,
      "answer_relevance": 0.88,
      "context_recall": 0.78
    }
  ],
  "latest": {
    "faithfulness": 0.92,
    "context_relevance": 0.88,
    "answer_relevance": 0.90,
    "context_recall": 0.85,
    "run_type": "post_training",
    "date": "2026-06-04T12:00:00Z"
  }
}
```

### `GET /api/v1/analytics/jobs/stats`

Fine-tuning job statistics for the authenticated user.

**Response `200`:**

```json
{
  "total_jobs": 5,
  "completed": 3,
  "failed": 1,
  "queued": 1,
  "total_cost": 24.50,
  "avg_cost_per_job": 4.90,
  "avg_duration_minutes": 32.5
}
```

### `GET /api/v1/analytics/chat/stats`

Chat usage statistics for the authenticated user.

**Response `200`:**

```json
{
  "total_sessions": 12,
  "total_messages": 87,
  "user_messages": 43,
  "assistant_messages": 44,
  "avg_latency_ms": 1200.0
}
```

### `GET /api/v1/analytics/budget/trend`

Monthly budget usage for the past N months.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `months` | int | `6` | Number of months (1–12) |

**Response `200`:**

```json
{
  "points": [
    {
      "month": "2026-01",
      "total_spend": 18.50,
      "job_count": 4
    }
  ],
  "current_spend": 12.50,
  "budget_limit": 30.00
}
```

---

## 12. WebSocket

Real-time fine-tuning job metrics relay.

### `WS /ws/fine-tune/{job_id}`

WebSocket endpoint for streaming fine-tuning job progress.

**Connection:**

```
ws://localhost:8000/ws/fine-tune/{job_id}?token=<jwt_token>
```

**Authentication:** JWT token passed as `token` query parameter.

**Initial Message (server → client):**

```json
{
  "type": "connected",
  "job_id": "job-uuid-1",
  "data": {
    "status": "training",
    "model_id": "qwen2.5-14b",
    "dataset_id": "ds-uuid-1",
    "queue_position": null,
    "training_metrics": null,
    "eval_report": null
  }
}
```

**Server-Sent Event Types:**

| Type | Payload | Description |
|------|---------|-------------|
| `step` | `{step, loss, learning_rate, epoch}` | Training step progress |
| `epoch` | `{epoch, avg_loss, eval_loss}` | Epoch completion summary |
| `eval` | `{faithfulness, context_relevance, answer_relevance, context_recall}` | RAGAS eval results |
| `complete` | `{final_loss, adapter_path, cost, duration_seconds}` | Job completed |
| `error` | `{message, stage}` | Job failed |

**Keepalive:** Client can send `"ping"`; server responds with `{"type": "pong"}`.

**Close Codes:**

| Code | Reason |
|------|--------|
| `4001` | Authentication required |
| `4004` | Job not found |

---

## Usage Examples

### cURL — Upload a Document

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/document.pdf" \
  -F "title=Research Paper"
```

### cURL — Send a Chat Query (SSE)

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?", "model_variant": "base"}'
```

### cURL — Trigger Fine-Tuning

```bash
curl -X POST http://localhost:8000/api/v1/fine-tune/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "qwen2.5-14b", "dataset_id": "ds-uuid-1"}'
```

### cURL — Run Evaluation

```bash
curl -X POST http://localhost:8000/api/v1/evaluations/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"run_type": "baseline", "model_id": "qwen2.5-14b", "model_variant": "base"}'
```

### cURL — Budget Check

```bash
curl http://localhost:8000/api/v1/budget/ \
  -H "Authorization: Bearer <token>"
```

### Python — WebSocket Fine-Tune Monitor

```python
import asyncio
import websockets

async def monitor_job(job_id: str, token: str):
    uri = f"ws://localhost:8000/ws/fine-tune/{job_id}?token={token}"
    async with websockets.connect(uri) as ws:
        async for message in ws:
            print(message)

asyncio.run(monitor_job("job-uuid-1", "<jwt_token>"))
```
