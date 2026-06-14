# Intelligent Domain Knowledge Platform (IDKP)

A production-grade, AI question-answering system combining **domain-specific fine-tuning** with an **Advanced Retrieval-Augmented Generation (RAG)** pipeline. IDKP processes diverse document formats, delivers precise source-cited responses, and continuously improves through automated QLoRA fine-tuning — all governed by strict budget controls and comprehensive observability.

## Table of Contents

- [System Overview](#system-overview)
  - [Context Data Flow Diagram (DFD L0)](#context-data-flow-diagram-dfd-l0)
  - [Use Case Diagram](#use-case-diagram)
- [Data Flow & Architecture](#data-flow--architecture)
  - [Decomposed Data Flow Diagram (DFD L1)](#decomposed-data-flow-diagram-dfd-l1)
  - [Entity Relationship Diagram (ERD)](#entity-relationship-diagram-erd)
- [Core Workflows](#core-workflows)
  - [RAG Chat Activity Diagram](#rag-chat-activity-diagram)
  - [Document Ingestion Activity Diagram](#document-ingestion-activity-diagram)
  - [Fine-Tuning Activity Diagram](#fine-tuning-activity-diagram)
- [Architecture & Design](#architecture--design)
  - [Infrastructure Design](#infrastructure-design)
  - [RAG Pipeline Design](#rag-pipeline-design)
  - [Fine-Tuning Architecture Design](#fine-tuning-architecture-design)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Available Services & Ports](#available-services--ports)
- [Development Commands](#development-commands)
- [Documentation](#documentation)
- [Environment Variables](#environment-variables)
- [License](#license)
- [Budget & Cost](#budget--cost)
- [Contributing](#contributing)

---

## System Overview

### Context Data Flow Diagram (DFD L0)

This diagram illustrates the high-level system context, showing external actors — End Users, Admins, Fine-Tune Managers, and API Consumers — and their primary interactions with the IDKP System. External cloud dependencies (Modal.com GPU, AWS S3, Qdrant Cloud) are also depicted, providing compute, storage, and vector search capabilities.

```mermaid
graph LR
  EU["End User"]
  ADM["Admin"]
  FTM["Fine-Tune Manager"]
  AGT["Agent / API Consumer"]
  IDKP(["IDKP System"])
  MODAL["Modal.com GPU"]
  S3["AWS S3"]
  QDRANT["Qdrant Cloud"]

  EU -->|"Query / Upload / Login"| IDKP
  IDKP -->|"Streaming Answer + Citations"| EU
  ADM -->|"Eval / Analytics Request"| IDKP
  IDKP -->|"RAGAS Reports / Metrics"| ADM
  FTM -->|"Fine-tune Trigger"| IDKP
  IDKP -->|"Training Progress / Budget Status"| FTM
  AGT -->|"REST API Call"| IDKP
  IDKP -->|"JSON Response + Citations"| AGT
  IDKP -->|"Training Jobs / Inference Requests"| MODAL
  MODAL -->|"Generated Text / Embeddings / Training Metrics"| IDKP
  IDKP -->|"Store Raw Docs / Checkpoints / Datasets"| S3
  S3 -->|"Retrieved Files / Datasets"| IDKP
  IDKP -->|"Vector Upsert / Search Queries"| QDRANT
  QDRANT -->|"Ranked Chunks with Metadata"| IDKP
```

### Use Case Diagram

This diagram maps the complete functional surface of IDKP across four actor roles: End Users perform core document and query operations; Admins manage evaluations, analytics, and budget oversight; Fine-Tune Managers handle datasets and model customization; and external Agents/Consumers interact via REST API. System-level concerns such as rate limiting, budget enforcement, and observability are automated.

```mermaid
graph LR
  EU["End User"]
  ADM["Admin"]
  FTM["Fine-Tune Manager"]
  AGT["Agent / API Consumer"]
  SYS["System"]

  UC1(["Login via OAuth or Credentials"])
  UC2(["Upload Document"])
  UC3(["Send RAG Chat Query"])
  UC4(["View Chat History and Sessions"])
  UC5(["Check Document Processing Status"])
  UC6(["View Analytics Dashboard"])
  UC7(["Run RAGAS Evaluation"])
  UC8(["Run A/B Model Comparison"])
  UC9(["Manage and Delete Documents"])
  UC10(["View Monthly Budget Status"])
  UC11(["Create and Manage Datasets"])
  UC12(["Add Dataset Sources and Versioning"])
  UC13(["Trigger QLoRA Fine-tuning Job"])
  UC14(["Monitor Training via WebSocket"])
  UC15(["View Evaluation Reports and Metrics"])
  UC16(["Select Model Tier T0 to T3"])
  UC17(["Query via REST API"])
  UC18(["Invoke as LangChain or LlamaIndex Tool"])
  UC19(["Receive Streaming SSE Response"])
  UC20(["Rate Limit Enforcement: Redis Sliding Window"])
  UC21(["Budget Hard Block: HTTP 403 at $30"])
  UC22(["Auto RAGAS Eval Post-Training"])
  UC23(["OTel Trace Export to Langfuse"])

  EU --> UC1
  EU --> UC2
  EU --> UC3
  EU --> UC4
  EU --> UC5

  ADM --> UC1
  ADM --> UC6
  ADM --> UC7
  ADM --> UC8
  ADM --> UC9
  ADM --> UC10

  FTM --> UC1
  FTM --> UC11
  FTM --> UC12
  FTM --> UC13
  FTM --> UC14
  FTM --> UC15
  FTM --> UC16

  AGT --> UC17
  AGT --> UC18
  AGT --> UC19

  SYS --> UC20
  SYS --> UC21
  SYS --> UC22
  SYS --> UC23
```

---

## Data Flow & Architecture

### Decomposed Data Flow Diagram (DFD L1)

This diagram decomposes the IDKP System into six major processes: Authentication & Session management, Document Ingestion, RAG Query Pipeline, Fine-Tuning Pipeline, Evaluation & Analytics, and Budget Governance. Data stores include PostgreSQL (relational data), Qdrant (vector embeddings), AWS S3 (object storage), Redis (rate limiting), and Modal Volume (model checkpoints).

```mermaid
graph LR
  EU["End User"]
  ADM["Admin"]
  FTM["Fine-Tune Manager"]
  AGT["Agent"]

  P1(("P1: Auth + Session"))
  P2(("P2: Document Ingestion"))
  P3(("P3: RAG Query Pipeline"))
  P4(("P4: Fine-Tuning Pipeline"))
  P5(("P5: Evaluation + Analytics"))
  P6(("P6: Budget Governance"))

  D1[("PostgreSQL")]
  D2[("Qdrant Vectors")]
  D3[("AWS S3")]
  D4[("Redis Cache")]
  D5[("Modal Volume")]
  MODAL["Modal GPU"]

  EU -->|"Login"| P1
  P1 -->|"JWT Token"| EU
  P1 -->|"Write User / Session"| D1
  D1 -->|"Read Session"| P1

  EU -->|"Upload Document"| P2
  P2 -->|"Store Raw File"| D3
  P2 -->|"Embed Request"| MODAL
  MODAL -->|"Chunk Vectors"| P2
  P2 -->|"Upsert Vectors + BM25"| D2
  P2 -->|"Doc Metadata + Chunk Records"| D1

  EU -->|"Chat Query"| P3
  AGT -->|"API Query"| P3
  P3 -->|"Retrieve Top-K Chunks"| D2
  P3 -->|"LLM Generate Request"| MODAL
  MODAL -->|"Streaming Tokens"| P3
  P3 -->|"Streaming Response"| EU
  P3 -->|"JSON + Citations"| AGT
  P3 -->|"Store Messages + Citations"| D1
  D4 -->|"Rate Limit Window"| P3

  FTM -->|"Trigger Fine-tune Job"| P4
  P4 -->|"Pre-check Budget"| P6
  P6 -->|"Approve or Block"| P4
  P4 -->|"Dispatch Training Job"| MODAL
  MODAL -->|"LoRA Adapter + Metrics"| P4
  P4 -->|"Persist LoRA Adapter"| D5
  P4 -->|"Write Job Record"| D1
  D3 -->|"Training Dataset Files"| P4

  ADM -->|"Run Evaluation"| P5
  P5 -->|"LLM-as-Judge Request"| MODAL
  P5 -->|"Store Eval Results"| D1
  P5 -->|"Read Eval Runs"| P5
  D1 -->|"RAGAS Scores + Reports"| ADM

  ADM -->|"Budget Query"| P6
  P6 -->|"Read Spend Records"| D1
  P6 -->|"Budget Status"| FTM
```

### Entity Relationship Diagram (ERD)

This diagram captures the full relational data model of IDKP, spanning user management, document processing, knowledge graph extraction, chat sessions, dataset versioning, fine-tuning jobs, evaluation runs, and budget tracking.

```mermaid
erDiagram
    User {
        string id PK
        string email
        string name
        string image_url
        datetime created_at
        datetime updated_at
    }
    Document {
        string id PK
        string user_id FK
        string title
        string file_name
        string file_type
        string status
        string s3_key
        string processing_error
        int chunk_count
        datetime created_at
        datetime updated_at
    }
    DocumentChunk {
        string id PK
        string document_id FK
        int chunk_index
        string content
        string content_hash
        int token_count
        json metadata_
        datetime created_at
    }
    KnowledgeEntity {
        string id PK
        string document_id FK
        string entity_type
        string name
        json attributes
        datetime created_at
    }
    KnowledgeRelation {
        string id PK
        string source_entity_id FK
        string target_entity_id FK
        string relation_type
        datetime created_at
    }
    ChatSession {
        string id PK
        string user_id FK
        string title
        string model_variant
        datetime created_at
        datetime updated_at
    }
    ChatMessage {
        string id PK
        string session_id FK
        string role
        string content
        json citations
        int latency_ms
        int token_count
        datetime created_at
    }
    Dataset {
        string id PK
        string user_id FK
        string name
        string description
        string status
        int current_version
        datetime created_at
        datetime updated_at
    }
    DatasetSource {
        string id PK
        string dataset_id FK
        string source_type
        json source_config
        datetime created_at
    }
    DatasetVersionHistory {
        string id PK
        string dataset_id FK
        int version
        string change_description
        datetime created_at
    }
    FineTuningJob {
        string id PK
        string user_id FK
        string dataset_id FK
        string model_id
        string status
        float cost
        int duration_seconds
        string adapter_path
        json training_metrics
        datetime created_at
        datetime updated_at
    }
    EvaluationRun {
        string id PK
        string user_id FK
        string job_id FK
        string run_type
        string model_id
        string model_variant
        float faithfulness
        float context_relevance
        float answer_relevance
        float context_recall
        json per_sample_scores
        string status
        datetime created_at
    }
    BudgetTracking {
        string id PK
        string job_id FK
        float amount
        string period
        datetime created_at
    }

    User ||--o{ Document : "uploads"
    User ||--o{ ChatSession : "owns"
    User ||--o{ Dataset : "manages"
    User ||--o{ FineTuningJob : "triggers"
    User ||--o{ EvaluationRun : "runs"
    Document ||--o{ DocumentChunk : "splits into"
    Document ||--o{ KnowledgeEntity : "extracts"
    KnowledgeEntity ||--o{ KnowledgeRelation : "source of"
    KnowledgeEntity ||--o{ KnowledgeRelation : "target of"
    ChatSession ||--o{ ChatMessage : "contains"
    Dataset ||--o{ DatasetSource : "has"
    Dataset ||--o{ DatasetVersionHistory : "tracks"
    Dataset ||--o{ FineTuningJob : "used by"
    FineTuningJob ||--o{ EvaluationRun : "evaluated by"
    FineTuningJob ||--o| BudgetTracking : "tracked in"
```

---

## Core Workflows

### RAG Chat Activity Diagram

This diagram models the end-to-end RAG chat pipeline. After authentication and rate-limit checks, the query undergoes HyDE-based expansion plus multi-query variants, hybrid BM25 + dense vector retrieval, Reciprocal Rank Fusion, cross-encoder reranking, Self-RAG relevance gates, cosine deduplication, and token compression. The final prompt is sent to vLLM on Modal GPU, returning streaming SSE responses with extracted citations, while full pipeline traces are exported to Langfuse.

```mermaid
flowchart TD
  S([" Start "]) --> A{"Authenticated?"}
  A -->|"No"| R1["Return 401 Unauthorized"]
  A -->|"Yes"| B{"Rate Limit OK?"}
  B -->|"No"| R2["Return 429 Too Many Requests"]
  B -->|"Yes"| C["Create or Resume Chat Session in PostgreSQL"]
  C --> D["Store User Message: role=user, token_count"]
  D --> E["Query Expansion: HyDE hypothesis + 3x Multi-Query variants"]
  E --> F["BM25 Sparse Search: top-k=20 from Qdrant"]
  E --> G["Dense Vector Search: BGE-M3 1024-dim top-k=20 from Qdrant"]
  F --> H["Reciprocal Rank Fusion: k=60, merge BM25 + dense candidates"]
  G --> H
  H --> I["Cross-Encoder Reranking: BGE-Reranker-v2-m3, top-k=5"]
  I --> J["Metadata Filtering: Qdrant payload filters applied"]
  J --> K{"Self-RAG Relevance Gate: score each chunk"}
  K -->|"Low-relevance chunks removed"| L["Context Assembly: cosine dedup above 0.95 + token compression to 4096"]
  K -->|"All chunks pass threshold"| L
  L --> M["Prompt Builder: inject verified context + user query into RAG template"]
  M --> N["vLLM Inference on Modal GPU: fine-tuned or base LLM"]
  N --> O["Stream SSE Events to Client: token, citation, done, error types"]
  O --> P["Post-generation Citation Extraction with accuracy scoring"]
  P --> Q["Store Assistant Message: content, citations, latency_ms, token_count"]
  Q --> T["Export OTel Span to Langfuse: trace full pipeline"]
  T --> Z([" End "])
  R1 --> Z
  R2 --> Z
```

### Document Ingestion Activity Diagram

This diagram traces the lifecycle of a document from upload through vector storage. Files are streamed to S3, queued via SNS/SQS, processed by Modal workers using MarkItDown (with Tree-sitter parsing for code repos), chunked via LlamaIndex semantic splitting, embedded using BGE-M3 on Modal T4 GPUs, and upserted into Qdrant with both dense vectors and BM25 sparse indexes. Duplicate detection via content hash prevents redundant processing.

```mermaid
flowchart TD
  S([" Start "]) --> A{"Authenticated?"}
  A -->|"No"| R1["Return 401 Unauthorized"]
  A -->|"Yes"| B["POST /api/v1/documents/upload: multipart/form-data"]
  B --> C["Stream Raw File to AWS S3: raw/ prefix"]
  C --> D["Create Document Record in PostgreSQL: status=pending"]
  D --> E["S3 Put Event fires SNS notification on raw/ prefix"]
  E --> F["SNS delivers message to SQS ingestion queue"]
  F --> G["Modal Ingestion Worker polls SQS and picks up job"]
  G --> H["MarkItDown Conversion: PDF, DOCX, XLSX, HTML, MD, EPub, image OCR, code repos"]
  H --> I["Markdown Normalization: extract source_file, doc_type, page_numbers, section headings"]
  I --> J{"Is source a code repository?"}
  J -->|"Yes"| K["Tree-sitter AST Parse: extract functions, classes, docstrings"]
  J -->|"No"| L["Semantic Chunking via LlamaIndex: overlap-aware splits"]
  K --> L
  L --> M{"Content Hash match in DocumentChunk table?"}
  M -->|"Yes: duplicate detected"| N["Skip ingestion, update updated_at timestamp"]
  M -->|"No: new content"| O["BGE-M3 Embedding on Modal T4 GPU: 1024-dim dense vectors"]
  O --> P["Upsert to Qdrant: dense vectors + BM25 sparse index + metadata payload"]
  P --> Q["Store Converted Markdown to S3: converted/ prefix"]
  Q --> R["Update Document Record: status=completed, chunk_count populated"]
  R --> Z([" End "])
  N --> Z
  R1 --> Z
```

### Fine-Tuning Activity Diagram

This diagram details the QLoRA fine-tuning workflow. After Bearer JWT authentication, the BudgetService verifies the $30 monthly cap, the dataset record is validated in PostgreSQL, and a single-job FIFO queue ensures sequential execution. Training runs on Modal GPU tiers (A10G / L40S / A100) using Unsloth + PEFT with 4-bit quantization. Step metrics stream via WebSocket, epoch checkpoints persist to S3, and the final LoRA adapter lands on a persistent Modal Volume. An automatic post-training RAGAS evaluation scores faithfulness, context relevance, answer relevance, and context recall before the job is marked complete.

```mermaid
flowchart TD
  S([" Start "]) --> A["POST /api/v1/fine-tune: body has model_id and dataset_id"]
  A --> B{"Authenticated via Bearer JWT?"}
  B -->|"No"| E1["Return 401 Unauthorized"]
  B -->|"Yes"| C{"BudgetService: monthly_spend + estimated_cost within $30?"}
  C -->|"Over $30 hard limit"| E2["Return 403 Forbidden: budget cap exceeded"]
  C -->|"Within budget"| D{"Dataset record: exists in PostgreSQL and status=active?"}
  D -->|"Not found or archived"| E3["Return 400 Bad Request: invalid dataset"]
  D -->|"Valid"| F{"Is another FineTuningJob currently running?"}
  F -->|"Yes"| G["Insert Job with status=queued in PostgreSQL FIFO queue"]
  F -->|"No"| I
  G --> H["Poll queue: job dequeued when previous job completes"]
  H --> I
  I["Start Modal Fine-Tuning Function on GPU tier matched to model"] --> J["Load training data from S3: datasets/dataset_id/v-version/ prefix"]
  J --> K["QLoRA training step: Unsloth + PEFT, 4-bit BnB quantization"]
  K --> L["Push step metrics via WebSocket: step, loss, learning_rate, epoch"]
  L --> M["Save checkpoint to S3: checkpoints/job_id/ after each epoch"]
  M --> N{"All training epochs complete?"}
  N -->|"No: continue training"| K
  N -->|"Yes"| O["Save final LoRA adapter to Modal Volume: persistent across cold starts"]
  O --> P["BudgetService.record_spend: write GPU cost to BudgetTracking table"]
  P --> Q["Auto-trigger post-training RAGAS Evaluation: LLM-as-judge scoring"]
  Q --> R["Store EvaluationRun record: faithfulness, context_relevance, answer_relevance, context_recall"]
  R --> T["Update FineTuningJob: status=completed, adapter_path, duration_seconds"]
  T --> U["Send WebSocket event type=complete to Admin UI"]
  U --> Z([" End "])
  E1 --> Z
  E2 --> Z
  E3 --> Z
```

---

## Architecture & Design

### Infrastructure Design

This infrastructure diagram shows the deployment topology. A single VPS runs Docker Compose with Nginx (reverse proxy), Next.js 15 frontend, FastAPI backend, PostgreSQL 16, Redis 7, and Langfuse 2. External services — Modal.com (serverless GPU), Qdrant Cloud (vector database), and AWS S3 (object storage) — integrate via the backend. Observability is achieved through OpenTelemetry gRPC traces exported to Langfuse.

```mermaid
graph TB
  Browser["User Browser"]

  subgraph "Single VPS — Docker Compose"
    NX["Nginx :80 / :443"]
    FE["Next.js 15 Frontend :3000"]
    BE["FastAPI Backend :8000"]
    PG[("PostgreSQL 16 :5432")]
    RD[("Redis 7 :6379")]
    LF["Langfuse 2 :3001"]
  end

  subgraph "External Cloud Services"
    MODAL["Modal.com — Serverless GPU Compute"]
    QDR["Qdrant Cloud — Vector DB Free Tier"]
    S3["AWS S3 — Object Storage"]
  end

  Browser -->|"HTTPS TLS"| NX
  NX -->|"/* Next.js pages"| FE
  NX -->|"/api/* and /ws/* proxy"| BE
  FE -->|"fetch /api/v1/*"| BE
  BE --- PG
  BE --- RD
  BE -->|"OTLP gRPC traces"| LF
  LF --- PG
  BE -->|"Inference + Fine-tune jobs"| MODAL
  MODAL -->|"Generated text + adapters"| BE
  BE -->|"Vector upsert + ANN search"| QDR
  QDR -->|"Ranked chunk results"| BE
  BE -->|"Put raw + converted + checkpoints"| S3
  S3 -->|"Get files + datasets"| BE
```

### RAG Pipeline Design

This pipeline diagram details the 9-stage retrieval-augmented generation flow. After query expansion via HyDE and multi-query variants, the system performs hybrid BM25 + BGE-M3 dense vector search. Results are merged using Reciprocal Rank Fusion, reranked with BGE-Reranker-v2-m3, filtered by metadata and Self-RAG relevance gates, deduped via cosine similarity, and compressed to 4096 tokens. The final prompt is sent to vLLM on Modal GPU, returning streaming SSE responses with extracted citations.

```mermaid
graph LR
  Q["User Query"] --> QE["1. Query Expansion: HyDE + Multi-Query x3"]
  QE --> BM25["2a. BM25 Sparse Search: top-k=20"]
  QE --> DVS["2b. Dense Vector Search: BGE-M3 1024-dim top-k=20"]
  BM25 --> RRF["3. Reciprocal Rank Fusion: k=60 merges sparse + dense"]
  DVS --> RRF
  RRF --> RRNK["4. Cross-Encoder Reranking: BGE-Reranker-v2-m3 top-k=5"]
  RRNK --> MTAF["5. Metadata Filtering: Qdrant payload filter on doc_type, page, etc"]
  MTAF --> SRAG["6. Self-RAG Relevance Gate: score threshold filters irrelevant chunks"]
  SRAG --> CTX["7. Context Assembly: cosine dedup above 0.95 + compress to 4096 tokens"]
  CTX --> PRMT["8. Prompt Builder: RAG system prompt + context + query"]
  PRMT --> VLLM["9. vLLM Inference on Modal GPU: base or fine-tuned LLM variant"]
  VLLM -->|"SSE: token + citation + done"| CITE["Citation Extractor: post-generation with accuracy score"]
  CITE --> RESP["Streaming SSE Response to Client"]

  QDR[("Qdrant Cloud: Dense Vectors + BM25 + Metadata")] -->|"top-k=20"| BM25
  QDR -->|"top-k=20"| DVS
```

### Fine-Tuning Architecture Design

This design diagram illustrates the fine-tuning architecture spanning the Admin UI, FastAPI backend, and Modal GPU runtime. The backend enforces budget caps ($30 monthly limit) and validates datasets before enqueueing jobs in a PostgreSQL FIFO queue. Modal executes QLoRA training (Unsloth + PEFT at rank=64, alpha=128, 4-bit) with live WebSocket metrics streaming back to the UI. Checkpoints save to S3, the final LoRA adapter persists to Modal Volume, and post-training RAGAS evaluation scores all four metrics before the BudgetTracking record is written.

```mermaid
graph TB
  UI["Admin UI: Next.js /models page"] -->|"POST /api/v1/fine-tune"| API["FastAPI fine_tune endpoint"]
  API --> BG["BudgetService.get_monthly_spend: check spend + estimate"]
  API --> DV["Dataset Validator: query PostgreSQL for dataset record"]
  BG -->|"Approved: within $30 cap"| QUEUE["PostgreSQL FIFO Queue: status=queued, single-job execution"]
  DV -->|"Dataset active and valid"| QUEUE
  BG -->|"Rejected: over $30"| BLOCK["HTTP 403 Forbidden returned to caller"]
  QUEUE -->|"Dispatch when slot free"| MFT["Modal Fine-Tuning Function: GPU tier A10G L40S A100"]

  subgraph "Modal GPU — Training Loop"
    LOAD["Load Dataset from S3: datasets/id/v-version/"]
    QLRA["QLoRA Training: Unsloth + PEFT rank=64 alpha=128 4-bit"]
    PEVA["Auto RAGAS Evaluation: LLM-as-judge all 4 metrics"]
    LOAD --> QLRA --> PEVA
  end

  MFT --> LOAD
  QLRA -->|"Epoch checkpoints saved"| S3C["S3: checkpoints/job_id/"]
  QLRA -->|"step + loss + epoch metrics"| WS["WebSocket relay: type=step, epoch, eval, complete"]
  WS -->|"Live metrics"| UI
  PEVA -->|"Final LoRA adapter"| MVOL["Modal Volume: persistent adapter store across cold starts"]
  PEVA -->|"faithfulness + context_relevance + answer_relevance + context_recall"| PGDB["PostgreSQL: EvaluationRun record"]
  PGDB --> BTR["BudgetTracking: record GPU spend for calendar month"]
```

---

## Features

- **Hybrid Fine-tuning + RAG Architecture** — Domain adaptation via QLoRA fine-tuning combined with real-time knowledge retrieval
- **Multi-format Document Ingestion** — Unified conversion via MarkItDown supporting 11+ formats
- **Advanced RAG Pipeline** — 9 components including hybrid retrieval, cross-encoder reranking, query expansion, and citation extraction
- **Model Comparison System** — Toggle between base and fine-tuned models with automated comparative evaluation
- **Versioned Dataset Management** — Create, version, and manage training datasets without data loss
- **Budget-aware Fine-tuning** — $30/month GPU budget via Modal.com serverless infrastructure
- **Real-time Monitoring** — OpenTelemetry + Langfuse for distributed tracing and evaluation metrics
- **Multi-deployment Support** — Public chatbot, internal tool, and agent interface from single codebase

## Technology Stack

### Frontend
- **Framework:** Next.js 16 (App Router)
- **Styling:** Tailwind CSS 4 + shadcn/ui
- **Auth:** NextAuth.js v5 (OAuth + Credentials)
- **State:** React Context / Zustand
- **Charts:** Recharts

### Backend
- **Framework:** FastAPI with async support
- **Database:** PostgreSQL 16 (SQLAlchemy 2.0 async)
- **Cache:** Redis 7
- **Auth Integration:** JWT bridge with NextAuth.js
- **Document Processing:** MarkItDown + Tree-sitter
- **RAG:** LlamaIndex + LangChain
- **Embeddings:** BGE-M3 (HuggingFace)
- **Vector DB:** Qdrant Cloud
- **Evaluation:** RAGAS + custom benchmarks
- **Tracing:** OpenTelemetry + Langfuse

### Infrastructure
- **GPU Compute:** Modal.com (serverless, A10G/L40S/A100-80GB)
- **Object Storage:** AWS S3
- **Container Orchestration:** Docker Compose
- **Reverse Proxy:** Nginx
- **Monitoring:** Langfuse (self-hosted)

## Prerequisites

- Python >= 3.11
- Node.js >= 20
- Docker & Docker Compose
- AWS Account (for S3)
- Qdrant Cloud account (free tier)
- Modal.com account (with $30 free credits)

## Quick Start

### 1. Clone the repository

```bash
git clone <repository-url>
cd fine-tune-llm
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values:

```bash
# Auth
AUTH_SECRET=$(openssl rand -base64 32)

# Database (default values work for local development)
DATABASE_URL=postgresql+asyncpg://idkp:idkp_secret@localhost:5432/idkp

# Modal.com (serverless GPU)
MODAL_TOKEN_ID=your-modal-token-id
MODAL_TOKEN_SECRET=your-modal-secret

# AWS S3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=idkp-documents-dev

# Qdrant Cloud
QDRANT_URL=https://your-cluster.qdrant.cloud
QDRANT_API_KEY=your-qdrant-api-key

# Langfuse
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
```

### 3. Start infrastructure services

```bash
docker compose up -d
```

This starts PostgreSQL, Redis, Langfuse, and Nginx.

### 4. Set up the backend

```bash
cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### 5. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

### 6. Access the application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000 (Swagger docs at `/docs`)
- **Langfuse Dashboard:** http://localhost:3001

## Project Structure

```
fine-tune-llm/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Security, config
│   │   ├── db/             # Database session
│   │   ├── models/         # ORM models
│   │   └── main.py         # FastAPI app
│   ├── alembic/            # Database migrations
│   ├── tests/              # Pytest tests
│   └── pyproject.toml      # Python dependencies
├── frontend/               # Next.js frontend
│   ├── app/                # App Router pages
│   ├── components/         # React components
│   ├── lib/                # Utilities
│   └── package.json        # Node dependencies
├── docs/                   # Project documentation
│   ├── PROJECT_INITIATION_DOCUMENTATION.md
│   ├── TECHNICAL_REQUIREMENTS_DOCUMENT.md
│   └── IMPLEMENTATION_PLAN.md
├── nginx/                  # Nginx configuration
├── scripts/                # Deployment & utility scripts
├── docker-compose.yml      # Development stack
└── README.md               # This file
```

## Available Services & Ports

| Service | Port | Description |
|---------|------|-------------|
| Next.js Frontend | 3000 | Web application |
| FastAPI Backend | 8000 | REST API |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache & sessions |
| Langfuse | 3001 | Observability dashboard |
| Nginx | 80 | Reverse proxy |

## Development Commands

### Backend

```bash
# Install dependencies
cd backend && uv sync --all-extras

# Run development server
uv run uvicorn app.main:app --reload --port 8000

# Run tests
uv run pytest tests/ -v

# Run linting
uv run ruff check app/

# Format code
uv run ruff format app/

# Create database migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```

### Frontend

```bash
# Install dependencies
cd frontend && npm install

# Run development server
npm run dev

# Build for production
npm run build

# Run production build
npm start

# Run linting
npm run lint
```

## Documentation

- **[Project Initiation Documentation](docs/PROJECT_INITIATION_DOCUMENTATION.md)** — Business case, project brief, scope statement
- **[Technical Requirements Document](docs/TECHNICAL_REQUIREMENTS_DOCUMENT.md)** — System architecture, API specifications, data models
- **[Implementation Plan](docs/IMPLEMENTATION_PLAN.md)** — 12-week roadmap, resource allocation, risk mitigation

## Environment Variables

See `.env.example` for the complete list. Key variables:

- `AUTH_SECRET` — Shared secret for JWT signing (generate with `openssl rand -base64 32`)
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` — Modal.com authentication
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — AWS S3 credentials
- `QDRANT_URL` / `QDRANT_API_KEY` — Qdrant Cloud configuration
- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` — Langfuse tracing credentials

## License

This project uses open-source components. See individual package licenses for details:

- **Frontend:** MIT (Next.js, React)
- **Backend:** MIT/Apache 2.0 (FastAPI, most dependencies)
- **Models:** Apache 2.0 / MIT (Qwen, Gemma, Mistral, DeepSeek)
- **LLM Serving:** Apache 2.0 (vLLM, Unsloth)

## Budget & Cost

- **GPU Compute:** ≤ $30/month via Modal.com (free credits)
- **S3 Storage:** ~$1–2/month (50–100 GB)
- **Inference:** ≤ $0.01 per query (scale-to-zero)

## Contributing

See the [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) for detailed development guidelines and phase-based contribution opportunities.
