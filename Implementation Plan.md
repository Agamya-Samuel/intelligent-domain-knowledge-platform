# Implementation Plan
## Intelligent Domain Knowledge Platform (IDKP) v1.0

---

> **Document Version:** 1.0 
> **Date:** June 3, 2026    
> **Timeline:** 12 Weeks (June 16 – September 5, 2026)  
> **Parent Documents:** PID v1.3, TRD v1.0  
> **Team:** 2 ML Engineers, 2 Backend Engineers, 1 DevOps/MLOps Engineer

---

## Table of Contents

1. [Timeline Overview](#1-timeline-overview)
2. [Phase 1 — Foundation (Weeks 1–4)](#2-phase-1--foundation-weeks-14)
3. [Phase 2 — Fine-tuning (Weeks 5–7)](#3-phase-2--fine-tuning-weeks-57)
4. [Phase 3 — Advanced RAG (Weeks 8–9)](#4-phase-3--advanced-rag-weeks-89)
5. [Phase 4 — Integration & Testing (Weeks 10–11)](#5-phase-4--integration--testing-weeks-1011)
6. [Phase 5 — Deployment & Monitoring (Week 12)](#6-phase-5--deployment--monitoring-week-12)
7. [Resource Allocation Matrix](#7-resource-allocation-matrix)
8. [Critical Path & Dependencies](#8-critical-path--dependencies)
9. [Risk Mitigation Strategies](#9-risk-mitigation-strategies)
10. [Budget Tracking & Cost Monitoring](#10-budget-tracking--cost-monitoring)
11. [Testing & Validation Strategy](#11-testing--validation-strategy)
12. [Milestone Acceptance Criteria](#12-milestone-acceptance-criteria)

---

## 1. Timeline Overview

```
Week  1   2   3   4   5   6   7   8   9   10  11  12
      │───────────────│
      Phase 1: Foundation (W1-W4)
                      │───────────│
                      Phase 2: Fine-tuning (W5-W7)
                                  │───────│
                                  Phase 3: Advanced RAG (W8-W9)
                                          │───────────│
                                          Phase 4: Integration (W10-W11)
                                                      │───────│
                                                      Phase 5: Deploy (W12)

Key Milestones:
  ★ W1: Infra provisioned (VPS, Modal, S3, Qdrant Cloud)
  ★ W2: Ingestion pipeline + DB schema live
  ★ W4: Baseline RAG + eval scaffold + dataset CRUD
  ★ W5: Model Evaluation Gate complete
  ★ W7: QLoRA fine-tuning validated
  ★ W9: All 9 RAG components operational
  ★ W11: End-to-end system integrated
  ★ W12: Production go-live
```

---

## 2. Phase 1 — Foundation (Weeks 1–4)

### Week 1: Infrastructure & Project Scaffolding

**Goal:** All infrastructure provisioned; development environments operational.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Provision VPS; install Docker, Docker Compose, Nginx | DevOps | Running VPS with base stack | §10.1 |
| Set up Docker Compose with PostgreSQL 16, Redis 7, Langfuse | DevOps | All containers running; health checks passing | §10.1 |
| Configure Nginx reverse proxy (HTTP → HTTPS, routing rules) | DevOps | TLS-terminated proxy routing to Next.js and FastAPI | §10.2 |
| Provision Modal.com account; install SDK; verify GPU access (A10G, T4) | ML Eng | `modal run hello_gpu.py` succeeds on A10G | §7.1 |
| Provision Qdrant Cloud free tier cluster | DevOps | Cluster endpoint accessible; API key stored in `.env` | §7.2 |
| Provision AWS S3 bucket `idkp-documents-dev` with prefix structure | DevOps | `raw/`, `converted/`, `checkpoints/`, `datasets/`, `eval/`, `logs/` prefixes created | §5.3 |
| Configure S3 Event Notifications → SNS → SQS for `raw/` prefix | DevOps | SQS queue receives events on object creation | §7.3 |
| Initialize Next.js project (App Router, Tailwind, shadcn/ui) | Backend | Frontend scaffold with dev server running | §3.1 |
| Initialize FastAPI project with project structure, Alembic, SQLAlchemy | Backend | Backend scaffold with `/health` endpoint returning 200 | §3.2 |
| Configure NextAuth.js (Auth.js v5) with Google/GitHub OAuth + credentials | Backend | Login/logout flow working; JWT issued | §6.1, §9.1 |
| Implement JWT validation bridge in FastAPI (`get_current_user` dependency) | Backend | FastAPI validates Auth.js JWT; returns user_id | §7.4 |
| Set up `.env` template with all required variables | DevOps | `.env.example` committed; all secrets documented | §12.A |
| Set up GitHub repo with branch protection, CI (lint + test) | DevOps | GitHub Actions pipeline: lint → test → build | §11.3 |

**Week 1 Exit Criteria:**
- [ ] Developer can: clone repo → `docker compose up` → access frontend at `localhost:3000` and backend at `localhost:8000`
- [ ] User can log in via NextAuth.js and access protected routes
- [ ] Modal GPU function executes successfully on A10G
- [ ] S3 bucket created with correct prefix structure and event notifications

---

### Week 2: Database Schema + Document Ingestion Pipeline

**Goal:** Data models deployed; MarkItDown ingestion pipeline operational for all 11 formats.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Implement PostgreSQL schema (all tables) via Alembic migrations | Backend | Migrations applied; all tables created | §5.1 |
| Tables: `datasets`, `dataset_sources`, `dataset_version_history` | Backend | CRUD operations via SQLAlchemy models | §5.1 |
| Tables: `fine_tuning_jobs`, `budget_tracking` | Backend | Models with all fields and indexes | §5.1 |
| Tables: `chat_sessions`, `chat_messages`, `evaluation_runs` | Backend | Models with JSONB fields for citations/metrics | §5.1 |
| Implement MarkItDown integration layer | ML Eng | Python module wrapping MarkItDown; handles all 11 formats | §4.1 |
| Implement Markdown Normalization Layer | ML Eng | Metadata extraction: source_file, doc_type, page_numbers, sections | §4.1 |
| Implement Tree-sitter code repo parser | ML Eng | Function-level chunks with language detection | §4.1 |
| Implement Semantic Chunking (LlamaIndex SemanticChunker) | ML Eng | Chunking with BGE-M3 similarity; 128-1024 tokens; 64-token overlap | §4.1 |
| Create Modal T4 embedding function (BGE-M3) | ML Eng | Modal function: text → 1024-dim vector; batch processing | §4.1, §7.1 |
| Create Modal ingestion worker function | ML Eng | SQS-triggered: MarkItDown → normalize → chunk → embed → upsert | §4.1, §7.1 |
| Configure Qdrant Cloud collection `idkp_documents` | ML Eng | Collection with dense + sparse vectors; payload indexes | §5.2, §7.2 |
| Wire S3 SQS events to Modal ingestion worker | DevOps | End-to-end: upload to S3 → document searchable in Qdrant | §7.3 |
| Implement manual upload endpoint (`POST /api/datasets/{id}/sources`) | Backend | File upload → S3 `raw/` → triggers ingestion pipeline | §6.2 |

**Week 2 Exit Criteria:**
- [ ] Upload a PDF to S3 → within 5 minutes, chunks are searchable in Qdrant with correct metadata
- [ ] All 11 document formats convert correctly via MarkItDown (test suite passes)
- [ ] Database migrations run cleanly; all tables and indexes created
- [ ] Semantic chunking produces correct boundaries (manual inspection of 3 test docs)

---

### Week 3: Baseline RAG + Dataset Management API

**Goal:** Naive RAG pipeline answers queries; dataset CRUD fully operational.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Implement baseline RAG retrieval (dense search only, no reranking) | ML Eng | Query → Qdrant dense search → top-5 chunks → LLM prompt | §4.3 (partial) |
| Create Modal vLLM inference function (base model, no LoRA) | ML Eng | vLLM serving on A10G; streaming output; scale-to-zero | §4.4, §7.1 |
| Implement chat endpoint (`POST /api/chat`) with SSE streaming | Backend | Query → RAG retrieval → vLLM generation → SSE stream | §6.6 |
| Implement SSE event protocol: `token`, `citation`, `done` | Backend | Frontend receives structured streaming events | §6.6 |
| Implement dataset CRUD API (all 8 endpoints) | Backend | Full REST API with validation and error handling | §6.2 |
| Implement dataset versioning logic | Backend | Auto-increment on source add; manifest.json generation | §4.6 |
| Implement dataset source processing (upload, S3, text, URL) | Backend | All 4 source types processed and stored to S3 `datasets/` | §4.6, §6.2 |
| Implement archive (soft-delete) with validation | Backend | Archived datasets rejected for FT; hidden from selection | §6.2 |
| Implement budget API (`GET /api/budget`) | Backend | Spend calculation; remaining budget; estimated runs | §6.5 |
| Build dataset list page (Next.js) | Frontend | Table with name, version, source_count, status, actions | §12.B |
| Build dataset detail page (Next.js) | Frontend | Sources list, version history, add source (4 methods), archive | §12.B |
| Build dataset create modal (Next.js) | Frontend | Name + description form; validation; success redirect | §12.B |

**Week 3 Exit Criteria:**
- [ ] User can create dataset → add sources (upload, URL, text, S3) → see version history
- [ ] Chat endpoint returns streaming response with at least basic retrieval (dense search)
- [ ] Budget API returns correct spend and remaining calculations
- [ ] All dataset API endpoints pass integration tests

---

### Week 4: Evaluation Scaffold + Model Catalog + Auth Integration

**Goal:** RAGAS evaluation running; model catalog served; full auth-protected frontend.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Curate ground-truth evaluation dataset (200+ Q&A pairs) | ML Eng + Domain Expert | JSON dataset with question, ground_truth, source references | §4.1 |
| Implement RAGAS evaluation harness | ML Eng | Compute faithfulness, context_relevance, answer_relevance, context_recall | §4.3 |
| Run baseline RAGAS evaluation | ML Eng | Baseline metrics report generated and stored | — |
| Implement model catalog API (`GET /api/models`, `GET /api/models/{id}`) | Backend | Static MODEL_CATALOG served with all metadata fields | §4.2, §6.3 |
| Implement fine-tune trigger API skeleton (`POST /api/fine-tune`) | Backend | Auth check → dataset validation → budget check → enqueue | §6.4 |
| Implement budget hard block logic | Backend | Reject with HTTP 403 if total_spend + est_cost > $30 | §4.7, §6.4 |
| Implement fine-tuning job queue (PostgreSQL FIFO) | Backend | Only one job runs at a time; queue_position tracked | §4.7 |
| Build login page (Next.js + NextAuth.js) | Frontend | OAuth buttons (Google, GitHub) + credentials form | §9.1 |
| Build protected route middleware | Frontend | Redirect to /login if unauthenticated; session refresh | §9.1 |
| Build model catalog page (Next.js) | Frontend | 4-tier grid of model cards with metadata | §12.B |
| Build chat interface (Next.js) | Frontend | SSE streaming; message history; citation rendering | §12.B |
| Set up OpenTelemetry tracing in FastAPI | DevOps | Traces exported to Langfuse; query spans visible | §11.2 |
| Configure Langfuse dashboard | DevOps | Dashboard with query logging, latency, retrieval traces | §11.2 |

**Week 4 Exit Criteria (Phase 1 Gate):**
- [ ] RAGAS baseline established: metrics computed on 200+ Q&A pairs
- [ ] Model catalog page displays all 9 models across 4 tiers
- [ ] Full auth flow: login → protected pages → API authorization
- [ ] Chat UI streams responses with basic citations
- [ ] Fine-tune API skeleton validates auth, dataset, and budget
- [ ] Langfuse shows distributed traces for chat queries

---

## 3. Phase 2 — Fine-tuning (Weeks 5–7)

### Week 5: Model Evaluation Gate + Training Data Preparation

**Goal:** Winning model selected; training dataset prepared; QLoRA pipeline ready.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| **Model Evaluation Gate:** Benchmark ≥ 2 Tier 1 candidates | ML Eng | RAGAS triad + domain Q&A + cost/latency per model | §4.2 |
| Prepare 50+ held-out domain Q&A pairs (across all domains) | ML Eng + Domain Expert | Evaluation set: legal, healthcare, finance, tech, education | §4.2 |
| Run benchmarks on Modal A10G for each candidate | ML Eng | Per-model metrics: faithfulness, latency, VRAM, cost | §4.2 |
| Generate Model Selection Report | ML Eng | Signed-off report with winner rationale | PID §D-03a |
| Prepare fine-tuning dataset from curated dataset | ML Eng | Instruction-tuning format: Q&A pairs, summaries, reasoning | §4.2 |
| Add ~5-10% general-domain examples (prevent catastrophic forgetting) | ML Eng | Mixed dataset with domain + general examples | §4.2 |
| Implement dataset-to-training-format pipeline | ML Eng | Dataset sources → processed → instruction-tuning JSON | §4.6 |
| Implement QLoRA training script (Unsloth + PEFT) | ML Eng | Training script with tier-specific hyperparameters | §4.2 |
| Create Modal fine-tuning function | ML Eng | GPU-tier matched; timeout=600; Volume mounts; metrics output | §4.2, §7.1 |
| Implement Modal Volume persistence for base model | ML Eng | Model downloaded once; persisted across cold starts | §4.4 |
| Implement checkpoint saving to S3 | ML Eng | Checkpoints every N steps → `s3://.../checkpoints/{job_id}/` | §5.3 |
| Build fine-tuning trigger page (Next.js) | Frontend | Step flow: select model → select dataset → cost preview → confirm | §12.B |
| Implement cost estimation preview in UI | Frontend | Show estimated cost, remaining budget after run | §6.4 |

**Week 5 Exit Criteria:**
- [ ] Model Selection Report signed off; winning model identified (default: Qwen 2.5 14B)
- [ ] Training dataset prepared in instruction-tuning format (~500+ examples)
- [ ] QLoRA training script runs locally on Modal with sample data (1 epoch, no errors)
- [ ] Fine-tuning trigger UI shows model → dataset → cost preview flow

---

### Week 6: QLoRA Training + Real-time Metrics

**Goal:** First complete fine-tuning run; real-time WebSocket metrics in UI.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Execute first QLoRA training run on Modal (full dataset, 3 epochs) | ML Eng | LoRA adapter trained; checkpoints saved to S3 | §4.2 |
| Implement real-time metrics emission from Modal function | ML Eng | Training step data (loss, lr, epoch) → Modal output stream | §4.2, §7.1 |
| Implement WebSocket endpoint (`WS /ws/fine-tune/{job_id}`) | Backend | Real-time metric relay from Modal → backend → frontend | §6.9 |
| Implement WebSocket message types: step, epoch, eval, complete, error | Backend | All 5 message types with correct schemas | §6.9 |
| Build fine-tuning job detail page (Next.js) | Frontend | Live loss chart (Recharts); epoch progress; eval scores | §12.B |
| Implement WebSocket client in Next.js | Frontend | Connect to WS; render live charts; handle disconnects | §6.9 |
| Evaluate LoRA adapter against base model | ML Eng | Domain benchmark: ≥ 15% improvement on held-out set | §4.2 |
| Generate domain benchmark report | ML Eng | Comparison: base vs. fine-tuned on all metrics | PID §D-05 |
| Persist LoRA adapter to Modal Volume | ML Eng | Adapter available for inference without re-download | §4.4 |
| Implement job status tracking (queued → training → evaluating → completed) | Backend | State machine with proper transitions | §6.4 |
| Implement job history API (`GET /api/fine-tune/history`) | Backend | User's FT job list with status, cost, duration | §6.4 |

**Week 6 Exit Criteria:**
- [ ] QLoRA training run completes; LoRA adapter saved to Modal Volume + S3
- [ ] WebSocket streams live loss curves to the frontend
- [ ] Fine-tuned model shows ≥ 15% improvement on domain benchmark
- [ ] Job detail page shows complete training metrics (loss curve, eval scores, cost)

---

### Week 7: LoRA Serving + Model Comparison + Dataset Staleness

**Goal:** vLLM serves fine-tuned model; comparison system operational; dataset notifications work.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Configure vLLM on Modal with LoRA hot-loading | ML Eng | Single vLLM instance; dynamic adapter load/unload | §4.4, §7.1 |
| Implement LoRA hot-swap per request | ML Eng | Base and fine-tuned responses from same vLLM instance | §4.5 |
| Implement model comparison API (`POST /api/compare`) | Backend | Same query → both models → diff response with metrics | §4.5, §6.7 |
| Implement session model variant (`POST /api/session/model-variant`) | Backend | Per-session variant state in PostgreSQL | §4.5, §6.6 |
| Build chat toggle switch (Base ↔ Fine-tuned) | Frontend | Toggle in chat header; color-coded badge; state persistence | §4.5 |
| Build comparison diff panel | Frontend | Side-by-side response view with metric deltas | §4.5 |
| Implement dataset staleness detection | Backend | Compare dataset version vs. last FT job's dataset_version | §2.5 |
| Build staleness notification banner | Frontend | "N new sources since last fine-tune. [Re-train now]" | §2.5 |
| Implement automated comparative evaluation pipeline | ML Eng | Weekly regression: both models on held-out set → diff report | §4.5 |
| Store comparison reports in S3 `eval/comparisons/` | DevOps | JSON reports with faithfulness delta, latency delta, citation overlap | §5.3 |
| End-to-end test: chat with fine-tuned model + RAG | All | Full pipeline: query → retrieval → fine-tuned generation → citations | — |

**Week 7 Exit Criteria (Phase 2 Gate):**
- [ ] vLLM serves both base and fine-tuned models via LoRA hot-swap
- [ ] `/api/compare` returns side-by-side responses with metric diffs
- [ ] Chat toggle switch works; users can compare models in real-time
- [ ] Dataset staleness banner appears when sources added post-fine-tune
- [ ] End-to-end chat test passes: query → RAG retrieval → fine-tuned response with citations

---

## 4. Phase 3 — Advanced RAG (Weeks 8–9)

### Week 8: RAG Components 1–5 (Retrieval Core)

**Goal:** Hybrid retrieval, reranking, and query expansion operational.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| **C1: Semantic Chunking** — Validate and tune chunking | ML Eng | Breakpoint percentile tuned; chunk quality verified on 10+ docs | §4.3 |
| **C2: Hybrid Retrieval** — Implement BM25 (BM25s library) | ML Eng | Sparse index built; BM25 search parallel to dense | §4.3 |
| **C2: Hybrid Retrieval** — Configure Qdrant sparse vectors | ML Eng | BM25 token frequencies stored as sparse vectors in Qdrant | §5.2 |
| **C3: Reciprocal Rank Fusion** | ML Eng | RRF (k=60) merges BM25 + dense top-20 rankings | §4.3 |
| **C4: Cross-encoder Reranking** | ML Eng | BGE-Reranker-v2-m3 on Modal T4; top-5 output | §4.3 |
| Create Modal T4 reranker function | ML Eng | Batch reranking; ≤ 500ms for 20 candidates | §7.1 |
| **C5: Query Expansion (HyDE)** | ML Eng | HyDEQueryTransform: hypothetical answer → embed → retrieve | §4.3 |
| **C6: Multi-query Generation** | ML Eng | LLM generates 3-5 query variants per user query | §4.3 |
| Integrate all retrieval components into unified pipeline | ML Eng | Single `retrieve(query)` function: expand → hybrid → fuse → rerank | §4.3 |
| Benchmark hybrid retrieval vs. baseline dense-only | ML Eng | Precision@5 comparison; confirm ≥ 85% target | §8.2 |
| Implement metadata filtering (Qdrant payload filters) | Backend | Filter by doc_type, date_range, source_id, page, section | §4.3, §6.6 |

**Week 8 Exit Criteria:**
- [ ] Hybrid retrieval (BM25 + dense + RRF) outperforms dense-only on eval set
- [ ] Cross-encoder reranking improves Precision@5 by measurable margin
- [ ] HyDE + multi-query generates correct query variants
- [ ] Full retrieval pipeline (all 6 components) executes in < 2 seconds

---

### Week 9: RAG Components 6–9 (Verification + Citations + Context)

**Goal:** All 9 RAG components operational; full RAG pipeline validated.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| **C7: Metadata Filtering** — Wire to chat API | Backend | Optional filters in chat request: doc_type, date, source | §6.6 |
| **C8: Citation Extraction** — Implement post-generation mapping | ML Eng | Every factual claim → source doc + page/section reference | §4.3 |
| **C8: Citation Extraction** — Inject into SSE stream | Backend | `citation` events interspersed with `token` events | §6.6 |
| **C9: Self-RAG Verification** | ML Eng | Relevance gate: score retrieved chunks; drop low-score before LLM | §4.3 |
| Implement context compression | ML Eng | Remove near-duplicates (cosine > 0.95); truncate to 4096 tokens | §4.3 |
| Implement context assembly (pre-LLM prompt construction) | ML Eng | System prompt + context blocks + user query + instructions | §4.3 |
| Run full RAGAS evaluation with all 9 components | ML Eng | Compare against baseline: expect significant metric lift | §8.2 |
| Verify citation accuracy on 50+ factual queries | ML Eng | ≥ 95% citation accuracy; manual spot-check | §8.2 |
| Implement multi-document reasoning (agentic sub-queries) | ML Eng | Complex queries decomposed into sub-queries per document | §4.3 |
| Performance tune: ensure full RAG pipeline P95 ≤ 3s (warm) | ML Eng + DevOps | Profile each component; optimize bottlenecks | §8.1 |
| Run full RAGAS evaluation; compare to Phase 1 baseline | ML Eng | Final RAG metrics report: faithfulness ≥ 0.90 | §8.2 |

**Week 9 Exit Criteria (Phase 3 Gate):**
- [ ] All 9 RAG components operational and integrated
- [ ] RAGAS faithfulness ≥ 0.90; context relevance ≥ 0.85
- [ ] Citation accuracy ≥ 95% on factual queries (spot-check validated)
- [ ] Full RAG pipeline P95 latency ≤ 3 seconds (warm inference)
- [ ] Multi-document reasoning works on cross-document queries

---

## 5. Phase 4 — Integration & Testing (Weeks 10–11)

### Week 10: Full System Integration + Frontend Completion

**Goal:** All components wired end-to-end; all frontend pages complete.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Integrate fine-tuned LLM + Advanced RAG end-to-end | ML Eng + Backend | Query → 9-component RAG → fine-tuned vLLM → streaming response | §2.2 |
| Build analytics/eval dashboard (Next.js) | Frontend | RAGAS metrics over time; retrieval analytics | §4.8, §12.B |
| Build model comparison reports page | Frontend | Weekly diff reports; side-by-side metrics | §4.8, §12.B |
| Build fine-tuning history page | Frontend | All FT runs; loss curves; eval scores; cost | §4.8, §12.B |
| Build cost tracking dashboard | Frontend | GPU spend; S3 spend; remaining budget; projections | §4.8, §12.B |
| Build settings page | Frontend | User profile; model preferences | §12.B |
| Implement analytics API endpoints (all 4) | Backend | Evaluations, comparisons, retrieval, cost data | §6.8 |
| Wire all frontend pages to backend APIs | Frontend | All pages fetch and display real data | — |
| Implement rate limiting (60/min chat, 10/min fine-tune) | Backend | Per-user rate limits via Redis | §9.2 |
| Implement input validation and sanitization | Backend | Max 4096 chars; file type whitelist; SSRF protection | §9.2 |
| Implement prompt injection hardening | ML Eng | Delimited prompts; output filtering | §9.4 |
| Build agent tool wrapper (LangChain/LlamaIndex) | Backend | Tool interface for external agent integration | PID §D-10 |
| Generate OpenAPI spec from FastAPI | Backend | Auto-generated; reviewed for completeness | §6 |

**Week 10 Exit Criteria:**
- [ ] All frontend pages built and wired to backend APIs
- [ ] Full pipeline: login → create dataset → select model → fine-tune → chat with citations
- [ ] Analytics dashboard shows RAGAS metrics and cost tracking
- [ ] OpenAPI spec generated; all endpoints documented
- [ ] Rate limiting and input validation active

---

### Week 11: Load Testing + Security Review + Staging

**Goal:** System validated under load; security hardened; staging environment ready.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Load test: simulate 100 concurrent chat users | DevOps | Locust/k6 script; latency SLA validated | §8.2 |
| Load test: cold-start scenarios | DevOps | Measure cold-start latency across all model tiers | §8.1 |
| Security review: input sanitization audit | Backend | All inputs sanitized; no injection vectors | §9.2 |
| Security review: prompt injection testing | ML Eng | Red-team 20+ injection attempts; document bypass rate | §9.4 |
| Security review: auth/authorization audit | Backend | Verify resource isolation; no cross-user access | §9.1 |
| Set up staging environment | DevOps | Separate Docker Compose + S3 bucket `idkp-documents-staging` | §10.3 |
| Deploy full system to staging | DevOps | Staging mirrors production; all services running | §10.1 |
| Run integration test suite on staging | All | All API endpoints; WebSocket; SSE streaming; auth flow | — |
| Test dataset management end-to-end on staging | Frontend + Backend | Create → add sources → version → archive → FT trigger | §4.6 |
| Test fine-tuning flow end-to-end on staging | ML Eng | Select model → select dataset → train → monitor → chat | §4.2 |
| Validate budget hard block on staging | Backend | Attempt overspend → confirm HTTP 403 rejection | §4.7 |
| Fix bugs from testing; stabilize | All | P0/P1 bugs resolved | §12 |

**Week 11 Exit Criteria (Phase 4 Gate):**
- [ ] Load test passes: 100 concurrent users; P95 ≤ 3s (warm)
- [ ] Cold-start latency documented per tier (≤ 30s for Tier 1)
- [ ] Security audit complete; no P0/P1 vulnerabilities
- [ ] Staging environment fully operational; all integration tests pass
- [ ] Budget hard block validated: overspend attempts rejected
- [ ] No P0/P1 bugs open

---

## 6. Phase 5 — Deployment & Monitoring (Week 12)

### Week 12: Production Deployment + Handover

**Goal:** Production system live; monitoring active; handover complete.

| Task | Owner | Deliverable | TRD Reference |
|---|---|---|---|
| Set up production VPS environment | DevOps | Docker Compose + Nginx + SSL (Let's Encrypt) | §10.1, §10.2 |
| Deploy production PostgreSQL with WAL archiving | DevOps | Database with backup strategy | §11.1 |
| Configure S3 lifecycle policies | DevOps | Glacier at 90d; delete at 365d; versioning enabled | §7.3 |
| Deploy production Docker Compose stack | DevOps | All services running; health checks green | §10.1 |
| Configure Modal production functions | ML Eng | Inference (A10G), embeddings (T4), reranker (T4) | §7.1 |
| Set up Modal cost monitoring | DevOps | Budget alerts at 80% ($24); hard block at $30 | §8.3, §10 |
| Configure S3 cost alerts | DevOps | Alert at 50% usage ($15) | PID §1.6 |
| Deploy OpenTelemetry + Langfuse to production | DevOps | Full tracing; dashboard accessible | §11.2 |
| Set up automated weekly RAGAS regression | ML Eng | Cron job: run eval → store report → alert on drift | §4.5 |
| Set up automated comparative evaluation (weekly) | ML Eng | Base vs. FT diff reports → S3 → Langfuse | §4.5 |
| Write operator runbooks | DevOps | Re-indexing, model re-tune, rollback, Modal deployment | PID §D-12, §D-13 |
| Write API documentation | Backend | OpenAPI spec + usage examples | PID §D-09 |
| Write architecture documentation | All | System diagrams; data flows; component descriptions | PID §D-12 |
| Stakeholder demo | All | Full walkthrough: all features, all pages | PID §2.4 |
| Production smoke test | All | End-to-end validation on live system | — |

**Week 12 Exit Criteria (Go-Live Gate):**
- [ ] Production system live at domain; SSL active
- [ ] All monitoring dashboards accessible; alerts configured
- [ ] Weekly RAGAS regression + comparative evaluation automated
- [ ] Operator runbooks reviewed and signed off
- [ ] Stakeholder demo completed successfully
- [ ] No P0/P1 bugs; system stable under production traffic

---

## 7. Resource Allocation Matrix

### Role Assignments per Phase

| Phase | ML Engineer (×2) | Backend Engineer (×2) | DevOps/MLOps (×1) |
|---|---|---|---|
| **W1** | Modal setup; GPU validation | FastAPI/Next.js scaffold; Auth.js | VPS, Docker, Nginx, S3, Qdrant |
| **W2** | MarkItDown; chunking; embeddings; Qdrant | DB schema; dataset CRUD API | S3 events; SQS wiring; CI/CD |
| **W3** | Baseline RAG; vLLM inference function | Chat API; SSE streaming; dataset versioning; budget API | Langfuse setup; OpenTelemetry |
| **W4** | RAGAS eval harness; ground-truth dataset | FT trigger skeleton; model catalog API; hard block | Langfuse dashboard; monitoring |
| **W5** | Model Eval Gate; training data; QLoRA script | FT trigger UI integration; cost preview UI | Modal Volume setup; checkpoint S3 |
| **W6** | QLoRA training run; adapter evaluation; metrics | WebSocket endpoint; job state machine | WS infra; staging prep |
| **W7** | vLLM LoRA hot-swap; comparative eval | Compare API; session variant; staleness logic | Comparison S3 reports |
| **W8** | BM25; RRF; reranker; HyDE; multi-query | Metadata filtering API | Reranker Modal function |
| **W9** | Citations; Self-RAG; context compression; eval | Citation SSE events; multi-doc reasoning | Performance profiling |
| **W10** | Prompt injection hardening; agent wrapper | Analytics APIs; rate limiting; OpenAPI spec | All frontend pages completed |
| **W11** | Security review (prompt injection); load test support | Security audit; integration tests; bug fixes | Load testing; staging deploy |
| **W12** | Production Modal config; weekly eval automation | API docs; architecture docs; smoke test | Production deploy; runbooks; monitoring |

### Effort Distribution (Approximate FTE-Weeks)

| Role | Phase 1 (W1-4) | Phase 2 (W5-7) | Phase 3 (W8-9) | Phase 4 (W10-11) | Phase 5 (W12) | Total |
|---|---|---|---|---|---|---|
| ML Engineer (×2) | 4 | 5 | 4 | 2 | 1 | 16 |
| Backend Engineer (×2) | 5 | 2 | 1 | 3 | 1 | 12 |
| DevOps/MLOps (×1) | 3 | 1 | 1 | 2 | 2 | 9 |
| **Total** | **12** | **8** | **6** | **7** | **4** | **37** |

---

## 8. Critical Path & Dependencies

### Critical Path (Longest Dependency Chain)

```
W1: Modal + S3 provisioned
    ↓
W2: MarkItDown ingestion + Qdrant collection
    ↓
W3: Baseline RAG + vLLM inference
    ↓
W4: RAGAS evaluation scaffold
    ↓
W5: Model Evaluation Gate (depends on eval harness)
    ↓
W6: QLoRA training run (depends on model selection + training data)
    ↓
W7: vLLM LoRA serving (depends on trained adapter)
    ↓
W8-9: Advanced RAG (can partially parallel with W7)
    ↓
W10: End-to-end integration (depends on all components)
    ↓
W11: Load test + security (depends on integrated system)
    ↓
W12: Production deploy (depends on all gates passed)
```

### Dependency Graph

| Dependency | Blocks | Mitigation |
|---|---|---|
| Modal.com account provisioning | All GPU work (FT, inference, embeddings, reranker) | Start Day 1; escalation path if delayed |
| S3 bucket + event notifications | Ingestion pipeline (W2) | Provision in W1; test with mock events |
| Qdrant Cloud cluster | RAG retrieval (W3+) | Free tier instant provisioning; provision W1 |
| Ground-truth Q&A pairs (200+) | RAGAS evaluation (W4) | Start curation W1 with domain experts |
| Model Evaluation Gate (W5) | QLoRA training (W6) | Pre-stage 2-3 candidates; parallel benchmark |
| QLoRA adapter (W6) | LoRA serving (W7) | Checkpoint recovery if training fails |
| All 9 RAG components (W8-9) | End-to-end integration (W10) | Components 1-6 in W8; 7-9 in W9; parallelizable |
| Staging validation (W11) | Production deploy (W12) | Fix-forward strategy; rollback plan documented |

### Parallelization Opportunities

| Parallel Track A | Parallel Track B | Notes |
|---|---|---|
| W2: MarkItDown + ingestion | W2: DB schema + dataset API | Independent; merge at W3 |
| W5: Training data prep | W5: QLoRA script development | Independent until training run |
| W7: LoRA serving setup | W7: Dataset staleness logic | Independent features |
| W8: RAG components 1-6 | W8: Frontend analytics pages | ML vs. frontend work |
| W10: Security hardening | W10: Agent tool wrapper | Independent |

### Potential Bottlenecks

| Bottleneck | Impact | Mitigation |
|---|---|---|
| Modal GPU availability (A10G/L40S) | Training delays | Pre-book capacity; fallback to alternate GPU tier |
| Domain expert availability for Q&A curation | Eval dataset incomplete | Start early (W1); minimum 200 pairs; augment with synthetic |
| vLLM LoRA hot-swap stability | Comparison feature broken | Fallback: two separate vLLM instances (doubles cost but viable) |
| RAG latency with all 9 components | P95 > 3 seconds | Profile each component; skip HyDE for simple queries; cache embeddings |
| Qdrant Cloud free tier limits | Vector count exceeded | Monitor usage; upgrade path to paid tier if needed |

---

## 9. Risk Mitigation Strategies

| Risk (from PID §1.6) | Likelihood | Mitigation Strategy | Owner | Trigger |
|---|---|---|---|---|
| Fine-tuning data quality poor | Medium | Curate Q&A pairs iteratively; RAGAS eval catches regressions early (W4); add diversity checks | ML Eng | RAGAS faithfulness < 0.85 post-training |
| Ingestion latency > 5 min | Medium | Event-driven architecture (S3→SQS→Modal); monitor pipeline lag; alert on SLA breach | DevOps | Ingestion monitoring alert |
| Retrieval precision insufficient | Medium | All 9 RAG components; cross-encoder reranking; Self-RAG verification gate | ML Eng | Precision@5 < 85% on eval |
| Modal cold start too slow | Low | Scale-to-zero acceptable for v1 (< 100 queries/day); Modal Volume persists models; document cold-start latency per tier | DevOps | User complaints; P95 > 30s cold |
| Modal pricing changes | Low | Infrastructure abstraction layer; document fallback to AWS/GCP GPU | DevOps | Modal pricing announcement |
| Scope creep | High | Locked TRD; all changes via formal CR process (PID §3.7) | PM | Any request outside TRD scope |
| Model drift | Low | Weekly automated RAGAS regression; alert on faithfulness drop; re-trune trigger documented | ML Eng | Faithfulness < 0.85 for 2 consecutive weeks |
| Budget overrun | Medium | Hard block at $30 in API; queue-based single-job; pre-flight cost check; alerts at 80% | Backend | Budget API shows > $24 spend |
| S3 costs unexpected | Medium | Lifecycle policies (Glacier at 90d); upload size limits (100 MB); cost alerts at $15 | DevOps | AWS billing alert |
| FT model on stale dataset | Low | UI shows dataset version + last updated; staleness banner prompts re-train | Frontend | Dataset version > FT job's dataset_version |

---

## 10. Budget Tracking & Cost Monitoring

### Implementation per TRD §4.7, §6.5

**Budget Tracking Service (Backend):**
```
Phase: W3-W4 (skeleton) → W5-W6 (full integration with FT jobs)

Components:
1. PostgreSQL `budget_tracking` table (W2)
2. Spend calculation: SUM(cost WHERE status IN ('completed', 'running'))
3. Pre-flight check: total_spend + estimated_cost > $30 → HTTP 403
4. Budget API: GET /api/budget → spend, remaining, runs left
5. Monthly reset: auto-clear completed jobs older than current period
6. No caching: recalculate on every API call
```

**Cost Monitoring Dashboard (Frontend, W10):**
```
Components:
1. Modal GPU spend breakdown (by job, by model tier)
2. S3 storage costs (estimated from bucket size)
3. Remaining budget with progress bar ($X.XX of $30.00)
4. Projected run rate: "At current pace, ~N more runs this month"
5. Budget alert indicator: yellow at 80% ($24), red at 95% ($28.50)
```

**Automated Alerts (DevOps, W12):**
```
1. Modal dashboard alert at 80% ($24)
2. S3 billing alert at $15 (50% of estimated budget)
3. Webhook to Slack/email on threshold breach
4. Hard block validated: overspend → HTTP 403 with clear message
```

**Cost Tracking per FT Job:**
```
Before job: estimated_cost from MODEL_CATALOG[model_id].est_cost
During job: track GPU seconds × hourly rate (Modal API)
After job: record actual cost in budget_tracking.cost
Dashboard: show estimated vs. actual cost per job
```

---

## 11. Testing & Validation Strategy

### Testing Pyramid

```
           ┌───────────┐
           │  E2E Tests │  ← Playwright/Cypress: full user flows
           ├───────────┤
           │Integration│  ← pytest + httpx: API contracts, DB interactions
           ├───────────┤
           │ Unit Tests │  ← pytest + jest: individual functions, components
           └───────────┘
```

### Testing per Component

| Component | Test Type | Tool | Phase | Pass Criteria |
|---|---|---|---|---|
| **MarkItDown Ingestion** | Unit + Integration | pytest | W2 | All 11 formats convert correctly; metadata extracted |
| **Semantic Chunking** | Unit | pytest | W2 | Chunk boundaries align with topic transitions; size within bounds |
| **Qdrant Upsert** | Integration | pytest | W2 | Vectors + metadata searchable; dedup works |
| **Dataset CRUD** | Integration | pytest + httpx | W3 | All 8 endpoints; version auto-increment; archive works |
| **Budget Tracking** | Integration | pytest | W3-W4 | Spend calculation correct; hard block triggers at $30 |
| **Auth Flow** | E2E | Playwright | W4 | Login → session → protected API access → logout |
| **Baseline RAG** | ML Eval | RAGAS | W4 | Baseline metrics established on 200+ Q&A pairs |
| **Model Eval Gate** | ML Eval | RAGAS + custom | W5 | ≥ 2 models benchmarked; winner selected with report |
| **QLoRA Training** | ML Eval | RAGAS + domain benchmark | W6 | ≥ 15% improvement over base; adapter persisted |
| **WebSocket Metrics** | Integration | pytest + WS client | W6 | All 5 message types delivered; reconnect works |
| **LoRA Hot-swap** | Integration | pytest | W7 | Base and FT responses from same vLLM; correct adapter loaded |
| **Model Comparison** | E2E | Playwright | W7 | Toggle switch → correct model; compare API returns diff |
| **All 9 RAG Components** | ML Eval | RAGAS | W9 | Faithfulness ≥ 0.90; Precision@5 ≥ 85%; citations ≥ 95% |
| **Full Chat Pipeline** | E2E | Playwright | W10 | Login → chat → streaming response with citations |
| **Dataset + FT Flow** | E2E | Playwright | W10 | Create dataset → add sources → select model → trigger FT |
| **Analytics Dashboards** | E2E | Playwright | W10 | Metrics display correctly; charts render |
| **Load Test** | Performance | Locust/k6 | W11 | 100 concurrent users; P95 ≤ 3s warm; ≤ 30s cold |
| **Security Audit** | Manual + automated | OWASP ZAP + manual | W11 | No P0/P1 vulnerabilities; prompt injection resisted |
| **Budget Hard Block** | Integration | pytest | W11 | Overspend rejected; queue FIFO; cost preview accurate |
| **Production Smoke** | E2E | Manual + script | W12 | All features work on production; monitoring active |

### ML Evaluation Checkpoints

| Checkpoint | When | Metrics | Gate |
|---|---|---|---|
| Baseline RAG | W4 | RAGAS triad on 200+ pairs | Establishes baseline numbers |
| Model Selection | W5 | RAGAS + 50 domain Q&A + cost/latency | Winner selected; report signed off |
| Post-Training | W6 | RAGAS + domain benchmark vs. base | ≥ 15% improvement required |
| Post-Advanced-RAG | W9 | Full RAGAS + citation accuracy | Faithfulness ≥ 0.90; citations ≥ 95% |
| Weekly Regression | W12+ | Automated RAGAS on held-out set | Alert if faithfulness < 0.85 |

---

## 12. Milestone Acceptance Criteria

### Phase Gates (Go/No-Go)

| Gate | Week | Criteria | Sign-off By |
|---|---|---|---|
| **Phase 1 Gate** | W4 | RAGAS baseline; dataset CRUD live; auth working; chat with basic RAG; Langfuse active | ML Eng + Backend + DevOps |
| **Phase 2 Gate** | W7 | Model selected; QLoRA validated (≥ 15% lift); vLLM LoRA serving; comparison UI; staleness banner | ML Eng + Product Owner |
| **Phase 3 Gate** | W9 | All 9 RAG components; faithfulness ≥ 0.90; citations ≥ 95%; P95 ≤ 3s | ML Eng + Product Owner |
| **Phase 4 Gate** | W11 | Load test passed; security audit clear; staging green; no P0/P1 bugs | All + Product Owner |
| **Go-Live Gate** | W12 | Production live; monitoring active; runbooks signed; demo complete | Project Sponsor + Product Owner |

### Deliverable-to-Milestone Mapping

| PID Deliverable | TRD Section | Phase | Acceptance |
|---|---|---|---|
| D-01: Ingestion pipeline (11 formats) | §4.1 | W2 | All formats indexed; ≤ 5 min latency |
| D-02: Ground-truth eval dataset (200+) | §4.1 | W4 | Domain expert approved |
| D-03: Baseline RAG eval report | §4.3 | W4 | RAGAS metrics established |
| D-03a: Model Selection Report | §4.2 | W5 | ≥ 2 models benchmarked; winner signed off |
| D-03b: Model Comparison Feature | §4.5, §6.7 | W7 | API + UI + weekly diff reports operational |
| D-04: QLoRA fine-tuning + adapter | §4.2 | W6 | ≥ 15% improvement; adapter on Modal Volume |
| D-05: Domain benchmark report | §4.2 | W6 | Signed off by ML Eng + Product Owner |
| D-06: Advanced RAG (9 components) | §4.3 | W9 | Precision@5 ≥ 85%; citations ≥ 95% |
| D-07: End-to-end system | §2 | W10 | Faithfulness ≥ 0.90; cold start ≤ 30s |
| D-08: Public chatbot | §12.B | W12 | UAT passed; live URL |
| D-09: REST API (OpenAPI) | §6 | W10 | Spec reviewed and approved |
| D-10: Agent tool wrapper | — | W10 | LangChain + LlamaIndex demos pass |
| D-11: Monitoring dashboard | §11.2 | W12 | All metrics visible; alerts active |
| D-12: Runbooks + architecture docs | — | W12 | Signed off by DevOps + Product Owner |
| D-13: Modal deployment runbook | §10 | W12 | GPU configs, scale-to-zero, cost monitoring documented |
| D-15: Model Selection UI | §4.2, §6.3 | W5-W7 | Catalog page; FT trigger with budget; queue operational |
| D-16: S3 provisioning | §5.3, §7.3 | W1 | Bucket created; lifecycle policies; IAM roles |
| D-17: Dataset Management System | §4.6, §6.2 | W2-W4 | CRUD API; versioning; S3 storage; no deletion; FT linkage |

---

*End of Implementation Plan*
