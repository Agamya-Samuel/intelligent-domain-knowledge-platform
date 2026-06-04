# Intelligent Domain Knowledge Platform (IDKP)

A production-grade, open-source AI question-answering system that combines **domain-specific fine-tuning** with an **Advanced Retrieval-Augmented Generation (RAG)** pipeline. IDKP serves mixed corpora of 10–100+ documents across diverse formats (PDFs, Office files, Markdown, HTML, code repositories, images, audio, and more) with precise source citations.

## Features

- **Hybrid Fine-tuning + RAG Architecture** — Domain adaptation via QLoRA fine-tuning combined with real-time knowledge retrieval
- **Multi-format Document Ingestion** — Unified conversion via MarkItDown supporting 11+ formats
- **Advanced RAG Pipeline** — 9 components including hybrid retrieval, cross-encoder reranking, query expansion, and citation extraction
- **Model Comparison System** — Toggle between base and fine-tuned models with automated comparative evaluation
- **Versioned Dataset Management** — Create, version, and manage training datasets without data loss
- **Budget-aware Fine-tuning** — $30/month GPU budget via Modal.com serverless infrastructure
- **Real-time Monitoring** — OpenTelemetry + Langfuse for distributed tracing and evaluation metrics
- **Multi-deployment Support** — Public chatbot, internal tool, and agent interface from single codebase

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                                 │
│                    Next.js Frontend (SSR)                           │
│  Auth.js │ Chat UI │ Dataset Mgmt │ Model Select │ Analytics/Eval   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS + WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SINGLE VPS (Docker Compose)                     │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐  ┌──────────────┐              │
│  │   Next.js    │   │   FastAPI    │  │  PostgreSQL  │              │
│  │   Frontend   │   │   Backend    │  │  (Self-host) │              │
│  │   :3000      │   │   :8000      │  │  :5432       │              │
│  └──────────────┘   └──────┬───────┘  └──────────────┘              │
│                            │                                        │
│  ┌─────────────────────────┼─────────────────────────────┐          │
│  │  Nginx Reverse Proxy (:80/:443)                       │          │
│  │  / → Next.js  |  /api/* → FastAPI  |  /ws/* → FastAPI │          │
│  └───────────────────────────────────────────────────────┘          │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
      ┌────────────────────┼────────────────────┐
      ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Modal.com      │  │   Qdrant Cloud   │  │   AWS S3         │
│   (GPU Compute)  │  │   (Vector DB)    │  │   (Object Store) │
│                  │  │   Free Tier      │  │                  │
│ • Fine-tuning    │  │                  │  │ • raw/           │
│ • Inference      │  │ • Dense vectors  │  │ • converted/     │
│ • Embeddings     │  │ • BM25 index     │  │ • checkpoints/   │
│ • Ingestion      │  │ • Metadata       │  │ • datasets/      │
│                  │  │                  │  │ • eval/          │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

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