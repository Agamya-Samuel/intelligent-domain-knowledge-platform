# Project Initiation Documentation (PID)
## Intelligent Domain Knowledge Platform (IDKP)
### Approach: Fine-tuning + Advanced RAG

---

> **Document Version:** 1.3
> **Date:** June 3, 2026
> **Status:** Draft — Awaiting Stakeholder Approval
> **Prepared By:** Project Initiation Team
> **Classification:** Internal / Confidential   

---

## Table of Contents

1. [Document 1 — Business Case](#document-1--business-case)
2. [Document 2 — Project Brief](#document-2--project-brief)
3. [Document 3 — Scope Statement](#document-3--scope-statement)

---

---

# DOCUMENT 1 — BUSINESS CASE

---

## 1.1 Executive Summary

Large Language Models (LLMs) possess a hard training data cutoff — they cannot answer questions about documentation, policies, regulations, or knowledge that post-dates their training. For organizations with living, frequently updated corpora, this makes raw LLMs unreliable and dangerous to deploy.

This Business Case proposes building the **Intelligent Domain Knowledge Platform (IDKP)** — a production-grade, 100% open-source AI system that combines **domain-specific Fine-tuning** with an **Advanced Retrieval-Augmented Generation (RAG)** pipeline. The system will serve a mixed corpus of 10–100+ documents across diverse formats (PDFs, Microsoft Office files, Markdown, HTML, code repositories, database records, images with OCR, EPubs, and more) that updates daily to near-real-time, and must answer complex queries across fact lookup, summarization, multi-document reasoning, technical support, and compliance/legal analysis — with precise source citations. Document conversion is unified through **MarkItDown** (Microsoft), providing a single ingestion interface for 10+ file formats with LLM-optimized Markdown output.

The recommended approach combines Fine-tuning + Advanced RAG because each solves a different class of problem: Fine-tuning instills domain vocabulary, tone, and reasoning patterns into the model permanently; RAG keeps the knowledge layer current without retraining, retrieves grounding evidence, and enables citations. Neither alone meets all stated requirements.

---

## 1.2 Problem Statement

### 1.2.1 The Core Problem: LLM Knowledge Cutoff

Every LLM is trained on a fixed snapshot of the internet and published documents. After training, the model's internal knowledge is frozen. This creates three concrete failure modes:

| Failure Mode | Impact |
|---|---|
| **Stale answers** — the model answers from outdated training data when newer documentation exists | Wrong information delivered with high confidence |
| **Hallucination** — the model invents plausible-sounding but fabricated details to fill gaps | Trust erosion, compliance and legal risk |
| **Domain blindness** — the model lacks the vocabulary, conventions, and context of your specific domain | Low-quality, generic responses unusable in production |

### 1.2.2 Specific Constraints That Amplify the Problem

The following requirements each narrow the solution space significantly:

- **Daily-to-real-time knowledge changes** — rules out retraining or periodic fine-tuning as the primary knowledge update mechanism
- **10–100+ mixed-format documents** — rules out simple prompt stuffing (context window overflow); demands a proper retrieval layer with unified document conversion via MarkItDown
- **Multi-document reasoning and compliance/legal analysis** — rules out naive single-chunk retrieval; demands cross-document synthesis
- **Mandatory citations** ("According to page 14 of the source...") — rules out generation-only approaches with no retrieval grounding
- **Open-source only, no proprietary APIs** — rules out OpenAI, Anthropic, Cohere, and similar managed services
- **Accuracy + Speed as co-equal priorities** — rules out any single-component approach that sacrifices one for the other

### 1.2.3 Why Existing Partial Solutions Are Insufficient

| Approach | Why It Falls Short |
|---|---|
| **Prompt engineering alone** | Cannot fit 10–100 full documents in context; no citations; no real-time update mechanism |
| **Fine-tuning alone** | Excellent domain adaptation, but retraining required for every document update (daily); cannot reliably cite specific pages |
| **Naive RAG alone** | Retrieves the right chunks but the base model lacks domain knowledge; poor reasoning quality on technical/legal queries |
| **Simple keyword search + LLM** | Misses semantic queries; no cross-document reasoning; citation quality is poor |
| **Closed-source APIs** | Violates the open-source constraint; data privacy risk; unpredictable cost at scale |

---

## 1.3 Proposed Solution

### 1.3.1 Hybrid Architecture: Fine-tuning + Advanced RAG

The proposed solution is a two-layer architecture that separates **what the model knows** (fine-tuning) from **what the model retrieves** (RAG).

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 1 — FINE-TUNED LLM                     │
│  Primary: Qwen 2.5 14B-Instruct  |  Method: QLoRA (4-bit)      │
│  Tier 0-3 candidates: 7B → 72B   |  GPU: A10G–A100 on Modal   │
│  Trains on: domain Q&A pairs, document summaries, reasoning     │
│  cadence: one-time + periodic re-tune (budget permitting)       │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                     Augmented prompt
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  LAYER 2 — ADVANCED RAG PIPELINE                │
│                                                                 │
│  Ingestion ─► Chunking ─► Embedding ─► Vector DB                │
│        (S3-triggered)                  (Qdrant)                       │
│                                                                 │
│  Query ─► Query Expansion ─► Hybrid Retrieval ─► Reranking      │
│           (HyDE + multi-query)    (BM25 + Dense)     (Cross-encoder)   │
│                                                                 │
│  Metadata Filter ─► Citation Extraction ─► Context Assembly     │
│                                                                 │
│  cadence: near-real-time on document change                     │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
                ┌─────────────┴──────────────┐
                │  LAYER 3 — COMPARISON     │
                │  (API + UI + Auto-eval)  │
                │                           │
                │  POST /api/compare       │
                │  Toggle: Base ↔ FT       │
                │  Weekly diff reports     │
                │  Stored in S3           │
                └───────────────────────────┘
```

**Why this split works:**

- Fine-tuning bakes in domain vocabulary, output format, reasoning style, and citation behaviour. The model learns **how to think** in this domain.
- RAG brings the **latest facts**. Every document update is ingested, re-chunked, re-embedded, and available for retrieval within minutes — no retraining required.
- Together: a model that reasons like a domain expert and cites the most current version of your documents.

### 1.3.2 Open-Source Technology Stack

| Component | Selected Technology | Rationale |
|---|---|---|
| **Base LLM (Tier 1 — primary)** | Qwen 2.5 14B-Instruct, Mistral Ministral 3 14B-Instruct, DeepSeek-R1 Distill Qwen 14B | Strong reasoning across all domains; Apache 2.0 / MIT; fits on A10G (24 GB) with QLoRA |
| **Base LLM (Tier 0 — compact)** | Qwen 2.5 7B-Instruct, Gemma 4 E4B | Fastest training/inference; good baseline for RAG |
| **Base LLM (Tier 2 — enhanced)** | Qwen 2.5 32B-Instruct, Gemma 4 31B, DeepSeek-R1 Distill Qwen 32B | Near-70B quality at half the VRAM; requires L40S or A100-40GB |
| **Base LLM (Tier 3 — maximum)** | Qwen 2.5 72B-Instruct, Llama 3.3 70B-Instruct | Maximum quality; requires A100-80GB; limited to 0-1 FT runs/month on $30 budget |
| **Fine-tuning method** | QLoRA via PEFT + Unsloth | 4-bit quantization; 70% less VRAM; 2x faster training |
| **Embedding model** | BGE-M3 or E5-Large-v2 | State-of-the-art open-source retrieval embeddings |
| **Sparse retrieval** | BM25 (via Elasticsearch / OpenSearch or BM25s) | Exact token matching for IDs, codes, names |
| **Vector database** | Qdrant or Weaviate | OSS-first; production-grade; metadata filtering support |
| **Reranker** | BGE-Reranker-v2-m3 (Cross-Encoder) | Token-level late interaction; 30%+ relevance gains on hybrid results |
| **Orchestration** | LlamaIndex + LangChain | Modular; 300+ integrations; agent workflow support |
| **Document processing** | MarkItDown (Microsoft) + Tree-sitter | Unified conversion for 10+ formats (PDF, DOCX, PPTX, XLSX, HTML, Images/OCR, Audio, EPub, CSV/JSON/XML); Tree-sitter retained for deep code parsing |
| **GPU compute (fine-tuning)** | Modal.com (serverless A10G / L40S / A100-80GB) | Pay-per-second billing; scale-to-zero; GPU tier matched to model tier; $30 free tier sufficient for development |
| **GPU compute (inference)** | Modal.com (serverless A10G, full scale-to-zero) | Full scale-to-zero at < 100 queries/day; cold start ~30s acceptable; ~$2-5/month inference cost |
| **LLM serving** | vLLM (on Modal.com) | High-throughput, low-latency open-source inference server; LoRA hot-swap for model comparison |
| **Model comparison API** | vLLM LoRA hot-swap + `/api/compare` endpoint | Enables stakeholders to compare base vs. fine-tuned model; single vLLM instance serves both variants via LoRA adapter hot-loading |
| **Model selection UI** | Chainlit custom page + budget tracking API | Authenticated users can browse available models and trigger fine-tuning within $30 budget; hard block prevents overspend |
| **Budget tracking service** | PostgreSQL `budget_tracking` table + API | Tracks cumulative spend; hard block at $30; queue-based single-job execution |
| **Object storage** | AWS S3 (self-provisioned bucket) | Raw documents (source), converted Markdown output, fine-tuning checkpoints, evaluation datasets; S3 event notifications trigger ingestion |
| **Evaluation** | RAGAS + custom domain benchmark | RAG Triad + domain-specific Q&A + cost/latency benchmarks + automated comparative evaluation (base vs. fine-tuned) |
| **Monitoring** | OpenTelemetry + Langfuse | OSS tracing and observability; diff reports visible in dashboard |
| **Chat UI** | Chainlit or Open WebUI | Production-ready OSS chatbot interfaces; model toggle switch for stakeholders; model selection page for authenticated users |

---

## 1.4 Strategic Value

### 1.4.1 Organisational Benefits

**Accuracy and Trust**
The combination of Fine-tuning + Advanced RAG with mandatory citations reduces hallucination by grounding every response in retrieved evidence. Studies show retrieval augmentation reduces unsupported statements by approximately 60% compared to generation-only baselines.

**Data Sovereignty**
By running entirely on open-source models and self-hosted infrastructure, all document content and user queries remain within the organisation's own environment. No data is sent to third-party APIs.

**Cost Control**
Eliminating per-token API costs and owning the infrastructure means the marginal cost of additional queries approaches zero at scale. QLoRA fine-tuning is achievable on a single high-end GPU, dramatically reducing training compute costs compared to full fine-tuning.

**Adaptability**
The open-source stack means every component is replaceable and upgradeable as better models and techniques emerge, without vendor lock-in.

**Multi-deployment flexibility**
The same backend serves three stated use cases — public chatbot, internal company tool, and agent system — from a single unified API.

---

## 1.5 Cost-Benefit Analysis

### 1.5.1 Estimated Investment

| Cost Category | One-time | Monthly (recurring) |
|---|---|---|
| GPU compute — fine-tuning (Modal.com, A10G or L40S) | ~$2–$15 per training run (model-tier dependent) | ~$5–$25 (from free credits; 1-10 runs depending on model tier) |
| GPU compute — inference (Modal.com, full scale-to-zero) | — | ~$2–$5 (at < 100 queries/day; no keep-warm) |
| GPU compute — embeddings (Modal.com T4, on-demand) | — | ~$0.5–$1 (on ingestion events only) |
| GPU compute — storage (Modal Volume, ~7–15 GB) | — | ~$0.63–$1.35 (persistent model + adapter storage) |
| **Total Modal.com GPU spend** | — | **~$3–$7/month (well within $30 free credits)** |
| AWS S3 storage (raw docs, converted output, checkpoints, eval) | Setup effort | ~$1–$2/month (50–100 GB) |
| Vector database hosting (Qdrant self-hosted) | Setup effort | ~$50–$200 (storage + ops) |
| Engineering (ML + Backend + DevOps) | ~3–4 FTE × 12 weeks | ~0.5–1 FTE ongoing |
| Evaluation and QA dataset creation | ~2–4 weeks of effort | Periodic |

> **Note:** At < 100 queries/day with full scale-to-zero, inference costs are negligible (~$2–5/month). The $30/month free credits are sufficient for all GPU compute (fine-tuning + inference + embeddings + storage) with significant headroom for iterative model development. AWS S3 adds ~$1–2/month for 50–100 GB of document storage (raw + converted + checkpoints + eval). Remaining ~$23–$27/month headroom is allocated to fine-tuning runs, enabling 5–12 runs/month at Tier 1 (14B) on A10G.

### 1.5.2 Cost of Inaction

| Risk of Not Building | Estimated Exposure |
|---|---|
| Manual knowledge lookup time per query | Hours per day per knowledge worker |
| Compliance errors from stale or hallucinated answers | Legal exposure; audit failure risk |
| Inability to scale public chatbot queries | Revenue/reputation impact |
| Continued API dependency on proprietary providers | Escalating per-token costs; data exposure |

### 1.5.3 Return on Investment Drivers

- **Productivity**: Automating fact lookup, summarisation, and technical support queries frees domain experts for higher-value work
- **Accuracy**: Citation-backed answers reduce review and correction cycles
- **Scalability**: Once deployed, the system handles thousands of daily queries with no incremental cost
- **Compliance readiness**: Audit trails via citation tracking and response logging

---

## 1.6 Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Fine-tuning data quality is poor | Medium | High | Invest in Q&A pair curation; use RAGAS evaluation to catch regressions early |
| Real-time ingestion pipeline latency too high | Medium | Medium | Use event-driven ingestion (webhook/watch); set SLA at < 5 min per document change |
| Retrieval precision insufficient for legal/compliance queries | Medium | High | Add metadata filters, cross-encoder reranking, and Self-RAG verification step |
| GPU cold start adds latency to first inference request | Low | Low | Full scale-to-zero is default at < 100 queries/day; cold start (~30s) acceptable for low-traffic deployment; keep-warm can be added in future phase if latency tightens |
| Modal.com pricing changes or service disruption | Low | Medium | Maintain infrastructure abstraction layer; fallback plan to traditional cloud GPU (AWS/GCP) |
| Scope creep (multi-language, new modalities beyond MarkItDown scope) | High | Medium | Lock scope statement before sprint 1; defer to v2 roadmap |
| Model drift after domain corpus changes significantly | Low | High | Set up automated RAGAS evaluation; schedule re-tune trigger on drift threshold |
| Selected model tier too large for $30 budget, limiting iteration cycles | Medium | Medium | Start at Tier 1 (14B); Phase 2 Evaluation Gate includes cost/latency analysis; downgrade path to Tier 0 is low-cost and fast |
| MoE models (Llama 4 Scout, Qwen 3.5 MoE) entice but require multi-GPU | Low | Low | Explicitly excluded from v1 model candidates; defer to v2 if budget increases |
| S3 storage costs grow unexpectedly with large document uploads | Medium | Low | S3 lifecycle policies to transition older docs to Glacier; upload size limits; cost alerts at 50% ($15) usage |
| Budget overrun from multiple users triggering fine-tuning simultaneously | Medium | Medium | Hard block at $30 via budget tracking API; queue-based single-job execution; pre-flight cost check before triggering any job |

---

## 1.7 Recommendation

**Proceed with the Fine-tuning + Advanced RAG approach** as proposed, leveraging **MarkItDown** for unified document ingestion and **Modal.com** for serverless GPU compute. The combination uniquely satisfies all stated requirements: open-source-only, daily-to-real-time document updates across 11+ formats, citation-backed responses, multi-query type support, and triple deployment targets (public chatbot, internal tool, agent system) — delivered in 12 weeks with significantly reduced GPU infrastructure costs.

The investment is justified by the productivity gains, elimination of proprietary API dependency, and the long-term strategic value of owning a domain-adapted AI layer that improves continuously.

---

---

# DOCUMENT 2 — PROJECT BRIEF

---

## 2.1 Project Identity

| Field | Detail |
|---|---|
| **Project Name** | Intelligent Domain Knowledge Platform (IDKP) |
| **Project Code** | IDKP-v1.0 |
| **Date** | June 3, 2026 |
| **Project Sponsor** | To be assigned |
| **Project Manager** | To be assigned |
| **Target Go-Live** | 12 weeks from kickoff |

---

## 2.2 Project Overview

The IDKP project delivers a **production-grade, open-source AI question-answering system** that draws on a continuously updated private knowledge corpus. The platform serves three deployment targets simultaneously: a public-facing chatbot, an internal company tool, and a programmatic agent interface.

Document ingestion is unified through **MarkItDown** (Microsoft), supporting 10+ file formats (PDF, DOCX, PPTX, XLSX, HTML, Images with OCR, EPub, Audio, CSV/JSON/XML, and code repositories) via a single conversion interface that outputs LLM-optimized Markdown. GPU compute for fine-tuning and inference is provided by **Modal.com** serverless infrastructure, enabling pay-per-second billing with scale-to-zero capabilities and eliminating GPU procurement delays. Raw documents and converted output are stored in **AWS S3** with event-driven ingestion (S3 notifications trigger the MarkItDown conversion pipeline), ensuring near-real-time updates as documents change. Stakeholders can compare base vs. fine-tuned model responses via a toggle switch in the chat UI, and any authenticated user can browse available models and trigger fine-tuning jobs within the $30/month budget (hard block prevents overspend).

The system uses a two-layer architecture:

1. **Fine-tuned LLM layer** — A 7B–32B parameter model selected from the candidate pool (Qwen 2.5, Gemma 4, Mistral Ministral 3, DeepSeek-R1 distills) via a structured Phase 2 Model Evaluation Gate. The selected model is adapted to the domain using QLoRA fine-tuning on curated question-answer pairs derived from the document corpus, giving the model deep fluency in domain vocabulary, output formats, and reasoning patterns across legal, healthcare, finance, technology, internal, and education domains.

2. **Advanced RAG layer** — A real-time retrieval pipeline that ingests document updates, indexes them using hybrid sparse + dense search, reranks retrieved chunks using a cross-encoder model, and injects grounded, page-level citations into the generated response.

---

## 2.3 Objectives

| # | Objective | Measurable Success Criterion |
|---|---|---|
| O-01a | Model selection completed via structured benchmark | Phase 2 Evaluation Gate: ≥ 2 candidate models benchmarked across RAGAS triad, domain-specific Q&A, and cost/latency; winner selected with documented rationale |
| O-01b | Model comparison accessible to stakeholders | Model comparison UI deployed with toggle switch and diff view; automated weekly comparative evaluation generating delta reports stored in S3; stakeholders can validate quality improvements before sign-off |
| O-01 | Domain-adapted LLM deployed | Fine-tuned model outperforms base model by ≥ 15% on domain eval benchmark |
| O-02 | Real-time document ingestion pipeline operational | New/updated documents indexed within ≤ 5 minutes of change |
| O-03 | Advanced RAG pipeline deployed with hybrid retrieval and reranking | Retrieval Precision@5 ≥ 85% on held-out evaluation set |
| O-04 | Citation-backed responses with source + page reference | Citation accuracy ≥ 95% on factual queries |
| O-05 | Public chatbot live | P95 response latency ≤ 3 seconds |
| O-06 | Internal API and agent interface deployed | REST API with OpenAPI spec; agent tool wrapper documented |
| O-07 | Evaluation and monitoring in production | RAGAS metrics tracked; alerts on faithfulness drop below 0.85 |
| O-08 | Model selection UI with budget awareness | Authenticated users can browse 4-tier model catalog and trigger fine-tuning jobs; budget tracking API prevents overspend; hard block at $30 monthly limit |

---

## 2.4 Key Deliverables

### Phase 1 — Foundation (Weeks 1–4)

- Document ingestion pipeline powered by **MarkItDown** supporting: PDF, DOCX, PPTX, XLSX, Markdown, HTML, Images (OCR), EPub, CSV/JSON/XML, Audio transcription, and code repositories (via Tree-sitter for deep parsing)
- Markdown Normalization Layer for metadata extraction (source file, document type, page numbers, section headers) from MarkItDown output
- Parsing, cleaning, and metadata extraction per source type
- Semantic chunking strategy implemented and benchmarked
- Vector database provisioned with hybrid index (dense + BM25)
- Baseline RAG pipeline (naive retrieval) with evaluation scaffold (RAGAS)
- Ground-truth evaluation dataset (minimum 200 Q&A pairs) curated from document corpus
- **Modal.com** account provisioned; SDK integrated; initial model download to Modal Volume
- **AWS S3 bucket provisioned** (`idkp-documents-{env}`); IAM roles configured; event-driven ingestion wired (SNS → SQS → Modal worker) for `raw/` prefix notifications
- Model catalog API (`/api/models`) and budget tracking infrastructure (PostgreSQL `budget_tracking` table) implemented; budget tracking service integrated with Modal; hard block at $30 enforced

### Phase 2 — Fine-tuning (Weeks 5–7)

- Model Evaluation Gate: benchmark ≥ 2 candidate models across RAGAS triad, domain-specific Q&A (≥ 50 held-out pairs across all target domains), and cost/latency metrics; select winning model with documented rationale
- Fine-tuning dataset prepared (instruction-tuning format from domain Q&A pairs and document summaries, including ~5–10% general-domain examples to prevent catastrophic forgetting)
- QLoRA training run executed on **Modal.com** (GPU tier matched to selected model: A10G for Tier 0-1, L40S for Tier 2, A100-80GB for Tier 3)
- LoRA adapter evaluated against baseline; domain benchmark report produced
- LoRA adapter persisted to Modal Volume for persistent storage across runs
- Model served via vLLM on Modal with LoRA adapter hot-loading support

### Phase 3 — Advanced RAG (Weeks 8–9)

- Hybrid retrieval implemented (BM25 + dense vector search with Reciprocal Rank Fusion)
- Cross-encoder reranker integrated (BGE-Reranker-v2-m3)
- Query expansion and HyDE (Hypothetical Document Embeddings) implemented
- Metadata filtering operational (source type, date, document ID, page number)
- Citation extraction and injection into responses implemented
- RAGAS evaluation: faithfulness, context relevance, answer relevance tracked end-to-end

### Phase 4 — Integration & Testing (Weeks 10–11)

- Fine-tuned LLM + Advanced RAG pipeline integrated end-to-end on Modal serverless infrastructure
- Public chatbot interface deployed (Chainlit or Open WebUI) with model comparison UI (toggle switch: Base ↔ Fine-tuned; diff panel for stakeholders)
- Internal REST API documented and tested (OpenAPI spec); includes model comparison endpoint `/api/compare` and session state endpoint `/api/session/model-variant`
- Model selection UI deployed: authenticated users can browse 4-tier model catalog; trigger fine-tuning jobs with budget confirmation
- Agent tool wrapper implemented (LangChain/LlamaIndex tool interface)
- Load testing: simulate 100 concurrent users; validate latency SLA (including cold-start scenarios)
- Security review: input sanitisation, rate limiting, prompt injection hardening

### Phase 5 — Deployment & Monitoring (Week 12)

- Production infrastructure provisioned on Modal.com (serverless inference, embedding functions, ingestion workers; full scale-to-zero — no keep-warm for v1)
- CI/CD pipeline for document ingestion (trigger on S3 event notification on `raw/` prefix)
- Automated re-indexing on document update via MarkItDown conversion pipeline; converted output stored to S3 `converted/` prefix
- AWS S3 lifecycle policies configured (transition old docs to Glacier after 90 days; delete after 365 days); bucket versioning enabled
- OpenTelemetry tracing + Langfuse dashboard live (including Modal function metrics)
- Automated RAGAS regression testing on weekly eval batch; comparative evaluation (base vs. fine-tuned) reports stored in S3 `eval/comparisons/` prefix
- Runbooks: Modal deployment, reindexing, model re-tune trigger, rollback procedures
- Modal cost monitoring dashboard with budget alerts (80% of $30 threshold = $24); S3 cost alerts at 50% usage ($15)
- Stakeholder handover and demo

---

## 2.5 Technology Stack Summary

### Core AI Components

| Component | Technology | License |
|---|---|---|
| **Base LLM (Tier 0 — Compact)** | Qwen 2.5 7B-Instruct, Gemma 4 E4B, DeepSeek-R1 Distill Qwen 7B | Apache 2.0 / Gemma / MIT |
| **Base LLM (Tier 1 — Standard)** ⭐ Primary | Qwen 2.5 14B-Instruct, Mistral Ministral 3 14B-Instruct, DeepSeek-R1 Distill Qwen 14B | Apache 2.0 / MIT |
| **Base LLM (Tier 2 — Enhanced)** | Qwen 2.5 32B-Instruct, Gemma 4 31B, DeepSeek-R1 Distill Qwen 32B | Apache 2.0 / Gemma / MIT |
| **Base LLM (Tier 3 — Maximum)** | Qwen 2.5 72B-Instruct, Llama 3.3 70B-Instruct | Apache 2.0 / Llama 3.3 |
| Fine-tuning framework | Unsloth + PEFT (QLoRA) | Apache 2.0 |
| LLM inference | vLLM (on Modal.com) | Apache 2.0 |
| Embedding model | BGE-M3 | MIT |
| Reranker | BGE-Reranker-v2-m3 | MIT |

### GPU Compute Infrastructure

| Component | Technology | Pricing Model |
|---|---|---|
| Fine-tuning GPU (Tier 0–1) | Modal.com A10G (24 GB VRAM) | ~$1.10/hr, pay-per-second, scale-to-zero |
| Fine-tuning GPU (Tier 2) | Modal.com L40S (48 GB VRAM) | ~$1.95/hr, pay-per-second, scale-to-zero |
| Fine-tuning GPU (Tier 3) | Modal.com A100-80GB (80 GB VRAM) | ~$2.50/hr, pay-per-second, scale-to-zero |
| Inference GPU | Modal.com A10G (full scale-to-zero) | ~$1.10/hr active; $0 idle |
| Embedding GPU | Modal.com T4 (16 GB VRAM) | ~$0.59/hr, on-demand for ingestion |
| Persistent storage | Modal Volume | $0.09/GB/month (~7–15 GB for model + adapter) |
| Model pre-download (cold start optimization) | S3 → Modal Volume sync function | ~$0.5–1/month on Modal T4 (per cold start) |
| SDK | Modal Python SDK | MIT |

### Retrieval & Storage

| Component | Technology | License |
|---|---|---|
| Object storage | AWS S3 (self-provisioned bucket) | AWS (infrastructure, not software) |
| Vector database | Qdrant (self-hosted) | Apache 2.0 |
| Sparse retrieval | BM25s or Elasticsearch OSS | Apache 2.0 |
| Hybrid fusion | Reciprocal Rank Fusion (RRF) | Algorithm (no license) |
| Document store | PostgreSQL | PostgreSQL License |

### Ingestion & Processing

| Component | Technology | License |
|---|---|---|
| Unified document conversion | MarkItDown (Microsoft) | MIT |
| PDF parsing | MarkItDown (built-in) | MIT |
| Office documents (DOCX, PPTX, XLSX) | MarkItDown (built-in) | MIT |
| HTML parsing | MarkItDown (built-in) | MIT |
| Image OCR | MarkItDown (built-in) | MIT |
| Audio transcription | MarkItDown (built-in) | MIT |
| EPub parsing | MarkItDown (built-in) | MIT |
| Markdown parsing | Python-Markdown / Mistune | BSD |
| Code repo parsing | Tree-sitter | MIT |
| Chunking | LlamaIndex semantic chunker | MIT |

### Orchestration & Serving

| Component | Technology | License |
|---|---|---|
| RAG orchestration | LlamaIndex + LangChain | MIT |
| Public chatbot UI | Chainlit | Apache 2.0 |
| Internal API | FastAPI | MIT |
| Agent interface | LangGraph / LlamaIndex Agents | MIT |

### Evaluation & Observability

| Component | Technology | License |
|---|---|---|
| RAG evaluation | RAGAS | MIT |
| Tracing | OpenTelemetry + Langfuse | MIT / Apache 2.0 |
| Experiment tracking | MLflow | Apache 2.0 |

---

## 2.6 Stakeholder Map

| Role | Responsibility | Involvement |
|---|---|---|
| **Project Sponsor** | Approves budget; escalation point | Milestone reviews |
| **Product Owner** | Owns requirements and acceptance criteria; prioritises backlog | Weekly |
| **ML Engineer (×1–2)** | Fine-tuning pipeline; model evaluation; RAGAS | Daily |
| **Backend Engineer (×1–2)** | RAG pipeline; ingestion worker; API; agent interface | Daily |
| **DevOps / MLOps Engineer (×1)** | Infrastructure; CI/CD; monitoring; serving | Daily |
| **Domain Expert (×1–2)** | Ground-truth Q&A curation; acceptance testing | Phase 1, 4 |
| **End Users (Public / Internal)** | UAT feedback; define query patterns | Phase 4–5 |

---

## 2.7 High-Level Timeline

```
Week  1  2  3  4  5  6  7  8  9  10  11  12
      │────────────────│
      Phase 1: Foundation
                       │──────────│
                       Phase 2: Fine-tuning (Modal)
                                  │───────│
                                  Phase 3: Advanced RAG
                                          │────────│
                                          Phase 4: Integration
                                                   │────│
                                                   Phase 5: Deploy (Modal)
```

---

## 2.8 Key Assumptions

- **Modal.com** account with $30/month free credits is available. At the projected query volume of < 100 queries/day with full scale-to-zero, total GPU compute costs (fine-tuning + inference + embeddings + storage) are estimated at ~$3–$7/month — well within free credits. The remaining ~$23–$27/month headroom is allocated to iterative fine-tuning runs
- GPU compute via Modal.com (A10G, 24 GB VRAM) is provisionable within Week 1 via serverless functions — no hardware procurement required
- Domain experts are available to curate a minimum of 200 high-quality Q&A evaluation pairs in Phase 1
- Document sources (PDFs, Office files, Markdown, HTML, images, code repositories, DB records) are accessible to the engineering team from the start of Phase 1
- The team has working proficiency in Python, PyTorch, Hugging Face ecosystem, and Modal SDK
- No multi-language requirement in v1 (English only)
- Modal cold start (~30s for model loading) is acceptable for all deployment targets at < 100 queries/day; full scale-to-zero is the default inference strategy for v1 (no keep-warm schedule)

---

## 2.9 Success Metrics Summary

| Metric | Target | Measurement Tool |
|---|---|---|
| Retrieval Precision@5 | ≥ 85% | RAGAS / custom eval harness |
| Answer Faithfulness | ≥ 0.90 | RAGAS faithfulness metric |
| Citation Accuracy | ≥ 95% | Manual spot-check + automated page-reference validation |
| Response Latency (P95) | ≤ 3 seconds (warm) / ≤ 30 seconds (cold start) | Load test + production monitoring |
| Document Ingestion Latency | ≤ 5 minutes | Ingestion pipeline monitoring |
| Fine-tuned model lift over base | ≥ 15% | Domain benchmark (held-out eval set) |
| Cost per query (inference) | ≤ $0.01 | Modal usage dashboard / custom tracking |
| Cold-start latency | ≤ 30 seconds | Load test + Modal cold-start metrics |
| Modal GPU cost efficiency | ≤ $30/month total (within free credits) | Modal usage dashboard + cost alerts (80% threshold = $24) |
| System uptime | ≥ 99.5% (business hours) | Infrastructure monitoring |

---

---

# DOCUMENT 3 — SCOPE STATEMENT

---

## 3.1 Purpose

This Scope Statement defines the authorised boundaries of the IDKP project. It specifies exactly what will and will not be built, the assumptions the plan rests upon, and the constraints that govern all technical and delivery decisions. Any work not listed in Section 3.2 (In Scope) must go through a formal change control process before it can be added to the project.

---

## 3.2 In Scope

### 3.2.1 Document Ingestion Pipeline

Document conversion is unified through **MarkItDown** (Microsoft), providing a single ingestion interface that outputs LLM-optimized Markdown. The following source formats are supported:

- Ingestion of **PDF documents** (text-based and scanned via built-in OCR)
- Ingestion of **Microsoft Office documents**: Word (.docx), PowerPoint (.pptx), Excel (.xlsx)
- Ingestion of **Markdown documents** (including frontmatter metadata)
- Ingestion of **HTML web content** (documentation sites, web archives)
- Ingestion of **image documents** with OCR (scanned documents, diagrams with text; EXIF metadata extraction)
- Ingestion of **audio files** (EXIF metadata + speech transcription)
- Ingestion of **EPub e-books** (technical manuals, documentation)
- Ingestion of **text-based formats**: CSV, JSON, XML (structured data as Markdown)
- Ingestion of **ZIP archives** (automatic iteration over contents)
- Ingestion of **YouTube URLs** (video transcript extraction)
- Ingestion of **code repositories** (Python, JavaScript, and generic text-based formats; parsed with **Tree-sitter** for deep AST-level analysis beyond MarkItDown's text-level conversion)
- **Markdown Normalization Layer**: post-processing step for metadata extraction (source file, document type, creation/update timestamp, page numbers, section headers) from MarkItDown's unified output
- **Real-time/near-real-time update mechanism**: event-driven re-ingestion triggered by S3 Event Notification on `s3:ObjectCreated:*` in AWS S3 bucket `raw/` prefix (SNS → SQS → Modal ingestion worker); alternatively, file system watch, webhook, or database change event; target latency ≤ 5 minutes end-to-end
- Document deduplication and version tracking (new version replaces old vectors for the same document ID; old versions retained in S3 via bucket versioning for audit trail)

### 3.2.2 Fine-tuning Pipeline

- **Model Evaluation Gate (Phase 2, Week 5):** A structured model selection process benchmarks ≥ 2 candidate models across three dimensions:
  1. **RAGAS Quality:** Faithfulness ≥ 0.90, context relevance ≥ 0.85, answer relevance ≥ 0.85
  2. **Domain-Specific Benchmark:** Performance on ≥ 50 held-out domain Q&A pairs (manually curated across all target domains: legal, healthcare, finance, technology, internal company knowledge, education)
  3. **Cost/Latency:** Fine-tuning cost per run, inference latency (P95), and monthly total GPU cost estimate
- **Base model selection:** Model chosen from the candidate pool via the Phase 2 Model Evaluation Gate (see §3.2.2a). Default tier is Tier 1 (14B class), upgradeable to Tier 2 (27–32B) if evaluation justifies and $30 budget permits. Downgrade to Tier 0 (7–9B) if cost or latency constraints require
- **QLoRA fine-tuning** using PEFT + Unsloth on curated domain instruction-tuning dataset, executed on **Modal.com** serverless GPU infrastructure (GPU tier matched to selected model)
- Fine-tuning dataset construction from: domain Q&A pairs, document summaries, multi-document reasoning examples, citation-format examples, plus ~5–10% general-domain examples to prevent catastrophic forgetting
- LoRA adapter training, checkpointing, and evaluation via Modal Functions with explicit GPU type selection (`gpu="A10G"`, `gpu="L40S"`, or `gpu="A100-80GB"` as appropriate)
- **Modal Volume** persistence: base model and final LoRA adapter stored on persistent volume to avoid re-download on cold starts
- **S3 checkpoint storage**: intermediate fine-tuning checkpoints stored to AWS S3 (`s3://idkp-documents-{env}/checkpoints/{job_id}/`) for durability and recovery; final LoRA adapter promoted to Modal Volume for serving
- Function timeouts enforced (`timeout=600`) to prevent runaway costs from bugs
- Domain benchmark evaluation report comparing fine-tuned vs base model
- Adapter merging and serving setup via vLLM on Modal with LoRA hot-loading support

### 3.2.2a Model Tier Selection Framework

The IDKP supports a tiered model selection strategy, allowing the team to choose the optimal model size based on quality requirements, budget constraints, and latency targets. All tiers use QLoRA (4-bit) fine-tuning via Unsloth + PEFT.

| Tier | Model Sizes | Modal GPU | QLoRA VRAM | Est. FT Cost/Run | FT Runs on $25/mo | Inference (scale-to-zero) |
|---|---|---|---|---|---|---|
| **Tier 0 — Compact** | 7–9B (Qwen 2.5 7B, Gemma 4 E4B) | A10G (24 GB) | 5–6.5 GB | $1–$3 | 8–25 runs/mo | Fastest cold start (~15s) |
| **Tier 1 — Standard** ⭐ | 14B (Qwen 2.5 14B, Ministral 3 14B, DeepSeek-R1 Distill 14B) | A10G (24 GB) | 8.5 GB | $2–$5 | 5–12 runs/mo | ~30s cold start |
| **Tier 2 — Enhanced** | 27–32B (Qwen 2.5 32B, Gemma 4 31B, DeepSeek-R1 Distill 32B) | L40S (48 GB) | 22–26 GB | $8–$16 | 2–3 runs/mo | ~45s cold start |
| **Tier 3 — Maximum** | 70B (Qwen 2.5 72B, Llama 3.3 70B) | A100-80GB (80 GB) | 41 GB | $20–$35 | 0–1 run/mo | ~60s cold start |

> **Default:** Tier 1 (14B) is the recommended starting point, offering the best quality-to-cost ratio. The Phase 2 Model Evaluation Gate determines whether to stay at Tier 1, downgrade to Tier 0 (if latency is critical), or upgrade to Tier 2 (if quality justifies the reduced iteration budget).

**Key models per tier (2026 candidates):**

| Tier | Primary Candidate | License | Strengths |
|---|---|---|---|
| Tier 0 | Qwen 2.5 7B-Instruct | Apache 2.0 | Fast training/inference; good baseline for RAG |
| Tier 1 | Qwen 2.5 14B-Instruct | Apache 2.0 | Best quality/cost ratio; strong reasoning across all domains |
| Tier 2 | Qwen 2.5 32B-Instruct | Apache 2.0 | Near-70B quality at half the VRAM cost |
| Tier 3 | Qwen 2.5 72B-Instruct | Apache 2.0 | Maximum quality; limited to 1 FT run/month on $30 |

### 3.2.2b Model Comparison (API + UI + Automated Evaluation)

All components for comparing the base (un-fine-tuned) model with the fine-tuned model are in scope:

**Backend:**
- **Model comparison API (`POST /api/compare`)**: Accepts a query and routes it to both the base model (no LoRA adapter) and the fine-tuned model (LoRA adapter loaded) on the same vLLM instance using LoRA hot-swap. Returns both responses with latency metrics and citation diffs
- **Session state endpoint (`POST /api/session/model-variant`)**: Sets the active model variant (`base` or `finetuned`) for a user session; stored in PostgreSQL session table
- **vLLM LoRA hot-swapping**: Single vLLM instance serves both model variants by dynamically loading/unloading the LoRA adapter per request; no need for two separate deployments

**Frontend (Chainlit):**
- **Model toggle switch**: Toggle widget in the chat UI header — "Base Model" ↔ "Fine-tuned Model". Default: Fine-tuned (when available); falls back to Base if no fine-tuning has been done. On toggle, new queries use the selected variant
- **Color-coded badge**: Visual indicator showing which variant is currently active (e.g., green = fine-tuned, grey = base)

**Automated Comparative Evaluation:**
- Weekly regression eval runs against **both** base and fine-tuned models on the same held-out Q&A set
- Generates diff report per query: faithfulness delta, latency delta, citation accuracy delta
- Reports stored in S3 (`s3://idkp-documents-{env}/eval/comparisons/YYYY-MM-DD-diff.json`)
- Diff reports visible in Langfuse dashboard and model comparison UI

### 3.2.3 Advanced RAG Pipeline

The following advanced RAG components are all in scope:

| Component | Description |
|---|---|
| **Semantic chunking** | Chunk boundaries determined by topic transitions, not fixed token counts |
| **Hybrid retrieval** | Parallel BM25 (sparse) + dense vector search; fused with Reciprocal Rank Fusion (RRF) |
| **Cross-encoder reranking** | Top-N candidates reranked by BGE-Reranker-v2-m3 for final context selection |
| **Query expansion** | HyDE (Hypothetical Document Embeddings) + multi-query generation for ambiguous queries |
| **Metadata filtering** | Filter by document type, date range, source, and page |
| **Citation extraction** | Every response includes exact source document name, page number or section reference |
| **Context compression** | Redundant or low-relevance passages removed before LLM prompt assembly |
| **Self-RAG verification** | Lightweight relevance gate: retrieved context checked before generation |
| **Multi-document reasoning** | Agentic sub-query decomposition for complex queries spanning multiple documents |

### 3.2.4 Deployment Targets

All three deployment targets are in scope:

- **Public chatbot** (primary): Chainlit or Open WebUI-based web interface; accessible via browser; authenticated access
- **Internal company tool**: Same backend; role-based access control (RBAC) layer; internal network deployment
- **Agent system interface**: REST API with OpenAPI 3.1 specification; LangChain and LlamaIndex tool wrappers; supports multi-turn conversation state

### 3.2.4b Model Selection UI

Any authenticated user can browse available models across all four tiers and trigger fine-tuning jobs, subject to the $30 monthly hard budget limit. This feature includes a backend budget tracking service, a fine-tuning job queue, and a Chainlit-based model catalog page.

**API Endpoints:**

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/models` | GET | Returns all available models across Tier 0–3 with metadata (id, tier, name, size, license, estimated_cost_per_run, estimated_training_time, vram_required, quality_rating, gpu_required) |
| `/api/fine-tune` | POST | Triggers a fine-tuning job for a selected model; validates authentication and budget before enqueuing |
| `/api/budget` | GET | Returns current spend, remaining budget, and estimated runs left at current spend rate |
| `/api/fine-tune/status/:job_id` | GET | Returns job status (queued, training, completed, failed) and queue position |

**Budget Tracking Service:**
- PostgreSQL table `budget_tracking` with columns: `id`, `job_id`, `model`, `cost`, `timestamp`, `status`
- Total spend calculated as `SUM(cost WHERE status IN ('completed', 'running'))`
- Hard block logic: if `total_spend + estimated_cost > $30`, the fine-tuning request is rejected with HTTP 403 and a message showing remaining budget
- Budget recalculated on every API call (no caching) to prevent stale-data overruns

**Fine-tuning Queue:**
- Only one fine-tuning job can run at a time (single GPU constraint on Modal.com free tier)
- Queue stored in PostgreSQL with FIFO ordering
- Users can view queue position via the status endpoint; queued jobs automatically start when the running job completes

**Frontend (Chainlit Model Selection Page):**
- Accessible via sidebar navigation; displays a grid of model cards organized by tier
- Each card shows: model name, size, license badge, estimated cost per run, estimated training time, GPU required, and a "Select & Fine-tune" button
- Budget indicator at top of page: "Remaining: $XX.XX of $30.00 (~N runs left)"
- Confirmation modal before triggering: displays model details, estimated cost, new remaining budget after the run, and Confirm/Cancel buttons
- Status page after confirmation: shows job progress (queued → training → completed)
- Budget exceeded state: model cards disabled with "Insufficient budget remaining" message
- Active model indicator in sidebar: shows currently active fine-tuned model with link back to model selection page

### 3.2.5 Evaluation, Monitoring, and Observability

- RAGAS evaluation framework integrated; metrics computed on every evaluation run: faithfulness, context relevance, answer relevance, context recall
- Automated weekly regression evaluation against held-out Q&A set
- Model drift detection: alert triggered when faithfulness drops below 0.85
- OpenTelemetry distributed tracing for all pipeline components
- Langfuse dashboard for query logging, latency breakdown, and retrieval trace visualisation
- MLflow experiment tracking for fine-tuning runs

### 3.2.6 Documentation and Handover

- System architecture documentation
- API reference (OpenAPI spec)
- Operator runbooks: re-indexing, model re-tune trigger, rollback procedures
- Data schema documentation for vector store and document metadata
- Deployment guide for all three targets

---

## 3.3 Out of Scope

The following are explicitly excluded from this project. They may be candidates for a future v2 roadmap.

> **Note:** Modal.com is used as GPU compute infrastructure (serverless hosting for open-source models). This does not violate the open-source constraint as Modal provides compute resources, not proprietary models. All models running on Modal remain 100% open-source.

| Item | Reason for Exclusion |
|---|---|
| **Proprietary LLM APIs** (OpenAI, Anthropic, Cohere, etc.) | Hard constraint: open-source models only; Modal.com is used for compute infrastructure, not proprietary model APIs |
| **Multi-language support** (non-English) | Deferred to v2; increases embedding and evaluation complexity significantly |
| **Voice / audio interfaces** | Distinct product category; separate project |
| **Image or video document processing (advanced)** | Basic image OCR is now in scope via MarkItDown; advanced visual QA, video indexing, and video content analysis deferred to v2 |
| **Full model retraining from scratch** | QLoRA fine-tuning sufficient; full training requires prohibitive compute |
| **Custom UI/UX design** | Functional OSS chatbot UI only; bespoke frontend design deferred |
| **Mobile application** | Web-based chatbot is sufficient for v1 |
| **Integration with external live data feeds** (real-time APIs, stock feeds, etc.) | Only static documents and DB exports are in scope |
| **Multi-tenant SaaS architecture** | Single-tenant deployment only in v1 |
| **GDPR / data residency compliance engineering** | Legal review is the organisation's responsibility; platform is designed to run on-prem to support this, but compliance certification is out of scope |
| **Automated fine-tuning on document updates** | Fine-tuning is periodic/manual; RAG handles real-time knowledge; auto-retraining adds risk of instability |
| **MoE models** (Llama 4 Scout, Qwen 3.5 MoE variants) | Require multi-GPU for fine-tuning (112+ GB VRAM for 4-bit); exceeds $30 budget; defer to v2 if Modal credits increase |

---

## 3.4 Assumptions

The project plan is built on the following assumptions. If any assumption is found to be false, a change request must be raised immediately.

| # | Assumption |
|---|---|
| A-01 | **Modal.com** account with $30/month free credits is available. At < 100 queries/day with full scale-to-zero, total GPU compute costs are ~$3–$7/month — well within free credits. Remaining ~$23–$27/month headroom is allocated to iterative fine-tuning runs |
| A-02 | GPU compute via Modal.com is provisionable within Week 1 via serverless functions — no hardware procurement required. A10G (24 GB) is available by default; L40S (48 GB) and A100-80GB (80 GB) available for higher model tiers |
| A-03 | Domain experts can dedicate ~2–4 hours per week during Phase 1 to curate ground-truth Q&A evaluation pairs |
| A-04 | All documents (PDFs, Office files, Markdown, HTML, images, code repos, DB records) are accessible in a readable, non-DRM-protected format |
| A-05 | The team has working proficiency in Python, PyTorch, Hugging Face ecosystem, and Modal SDK |
| A-06 | A minimum of 200 high-quality Q&A pairs can be curated from the document corpus for evaluation |
| A-07 | An infrastructure environment (cloud or on-prem) with at least 32 GB RAM and 500 GB storage is available for hosting the vector DB (Qdrant) and PostgreSQL document store; Modal handles all GPU workloads |
| A-08 | Document source systems (file system, DB, code repo) can emit change events or be polled; access credentials will be provided before Phase 1 |
| A-09 | v1 documents are in English only |
| A-10 | No existing vendor contracts restrict use of the proposed open-source components |
| A-11 | At < 100 queries/day, a ~30-second cold-start latency is acceptable for all three deployment targets. Full scale-to-zero is the default inference strategy for v1; keep-warm can be added in a future phase if latency requirements tighten |
| A-12 | The fine-tuning dataset includes domain-agnostic examples (~5–10%) to prevent catastrophic forgetting, given the platform's universal multi-domain scope |
| A-13 | Phase 2 Model Evaluation Gate requires ~2–3 hours of GPU time on Modal.com for benchmarking multiple candidate models. This is factored into the $30 monthly budget |
| A-14 | **AWS account** with S3 access is available. An S3 bucket (`idkp-documents-{env}`) with prefixes `raw/`, `converted/`, `checkpoints/`, `eval/comparisons/`, and `logs/` will be provisioned. S3 costs (~$1–2/month for 50–100 GB) are treated as infrastructure, not GPU compute |
| A-15 | **Authentication system** exists or will be provisioned for all three deployment targets (public chatbot, internal company tool, agent API). The model selection UI and fine-tuning trigger endpoints require authenticated access to prevent unauthorized budget consumption |

---

## 3.5 Constraints

| # | Constraint | Impact |
|---|---|---|
| C-01 | **100% open-source software stack** — no proprietary model APIs, no closed-source SaaS | All component selection must verify OSS license (Apache 2.0, MIT, BSD preferred); infrastructure providers (Modal.com, cloud) are exempt as they provide compute resources, not proprietary models |
| C-02 | **No calls to OpenAI, Anthropic, or equivalent APIs** at any point in the pipeline | Evaluation (including LLM-as-judge) must use self-hosted open-source models only; all models run on Modal remain open-source |
| C-03 | **Daily-to-near-real-time document updates** must be reflected in query results | Ingestion pipeline must be event-driven, not batch-nightly; MarkItDown conversion + Modal embedding ensures fast re-indexing |
| C-04 | **Mandatory citations** on all factual responses | RAG pipeline must extract and preserve page/section provenance through the full pipeline |
| C-05 | **Accuracy and Speed are co-equal** | No aggressive context compression that hurts accuracy; no reranking skip that hurts latency; must be benchmarked together |
| C-06 | **Fine-tuning must not regress general language ability** | Training data must include ~5–10% general-domain examples to prevent catastrophic forgetting |
| C-07 | **Modal cost governance** — total monthly GPU spend must remain within the $30 free credit allocation. All GPU functions must specify explicit GPU type (`gpu="A10G"`, `gpu="L40S"`, or `gpu="A100-80GB"` as appropriate), timeout (`timeout=600`), and use full scale-to-zero (no keep-warm). Cost monitoring via Modal dashboard with 80% ($24) budget alert threshold. Any model tier upgrade beyond Tier 1 requires documented cost justification in the Phase 2 Model Selection Report. Fine-tuning jobs are subject to a hard block: if `total_spend + estimated_cost > $30`, the job is rejected (HTTP 403). Only one fine-tuning job runs at a time; additional requests are queued in FIFO order via PostgreSQL. Budget is recalculated on every API call (no caching) | Prevents runaway costs; ensures project stays within zero-cost GPU budget; formal gate for tier upgrades; hard block prevents unauthorized budget overruns from concurrent fine-tuning triggers |

---

## 3.6 Deliverables Register

| ID | Deliverable | Phase | Acceptance Criteria |
|---|---|---|---|
| D-01 | Document ingestion pipeline (11 source types via MarkItDown + Tree-sitter) | 1 | All source types indexed; documents searchable within ≤ 5 min of update |
| D-02 | Ground-truth evaluation dataset (≥ 200 Q&A pairs) | 1 | Reviewed and approved by domain expert |
| D-03 | Baseline RAG evaluation report | 1 | RAGAS metrics established as baseline |
| D-03a | Model Selection Report (Evaluation Gate) | 2 | ≥ 2 models benchmarked across RAGAS + domain Q&A + cost/latency; winning model selected with documented rationale; signed off by ML Engineer and Product Owner |
| D-03b | Model Comparison Feature (API + UI + automated eval) | 4 | `POST /api/compare` returns base and fine-tuned responses; Chainlit toggle switch operational; weekly comparative diff report generated and stored in S3; visible in Langfuse dashboard |
| D-04 | QLoRA fine-tuning run + LoRA adapter (via Modal.com) | 2 | ≥ 15% improvement over base on domain benchmark; adapter persisted to Modal Volume |
| D-05 | Fine-tuned model domain benchmark report | 2 | Signed off by ML Engineer and Product Owner |
| D-06 | Advanced RAG pipeline (all 9 components) | 3 | Retrieval Precision@5 ≥ 85%; citations present in ≥ 95% of factual answers |
| D-07 | End-to-end integrated system (Modal-hosted inference) | 4 | RAGAS faithfulness ≥ 0.90; cold-start latency ≤ 30s |
| D-08 | Public chatbot (live URL) | 4–5 | User acceptance testing passed |
| D-09 | Internal REST API (OpenAPI spec) | 4–5 | API contract reviewed and approved |
| D-10 | Agent tool wrapper | 4–5 | Successfully executes in LangGraph and LlamaIndex agent demos |
| D-11 | Monitoring dashboard (Langfuse + OTel + Modal metrics) | 5 | All defined metrics visible; alert rules active; Modal cost tracking enabled |
| D-12 | Operator runbooks + architecture documentation | 5 | Reviewed and signed off by DevOps and Product Owner |
| D-13 | Modal deployment runbook | 5 | GPU function configs (tier-matched), scale-to-zero strategy, cost monitoring ($24 alert threshold), and fallback procedures documented |
| D-15 | Model Selection UI (catalog + fine-tune trigger + budget tracking) | 4 | `GET /api/models` returns all tier models with metadata; `POST /api/fine-tune` triggers jobs with hard block at $30; Chainlit model selection page with budget indicator deployed; queue-based single-job execution operational |
| D-16 | AWS S3 bucket provisioning and lifecycle policies | 1 | S3 bucket `idkp-documents-{env}` created with prefixes `raw/`, `converted/`, `checkpoints/`, `eval/comparisons/`, `logs/`; lifecycle policies configured; IAM roles for Modal and ingestion workers |

---

## 3.7 Change Control

Any request to add work not listed in Section 3.2, remove a deliverable from Section 3.6, or change a constraint in Section 3.5 must be submitted as a formal **Change Request (CR)** containing:

1. Description of the proposed change
2. Reason / business justification
3. Impact assessment: scope, schedule, cost, risk
4. Recommended disposition: Approve / Defer to v2 / Reject

Change Requests must be reviewed by the Project Sponsor and Product Owner before implementation begins.

---

## 3.8 Definition of Done

A deliverable is considered **Done** when:

- Code is reviewed, merged to main branch, and all CI checks pass
- Automated tests and RAGAS evaluations pass at defined thresholds
- Documentation updated
- Domain expert or Product Owner has signed off on acceptance criteria
- No P0 or P1 bugs open against the deliverable

---

*End of Project Initiation Documentation*

---

> **Document Control**
>
> | Version | Date | Author | Change |
> |---|---|---|---|
> | 0.1 | June 3, 2026 | Project Initiation Team | Initial draft |
> | 1.0 | June 3, 2026 | Project Initiation Team | Integrated MarkItDown (document ingestion) and Modal.com (serverless GPU); expanded ingestion from 4 to 11+ formats; reduced timeline from 14 to 12 weeks; updated cost model |
> | 1.1 | June 3, 2026 | Project Manager | Approved for execution |
> | 1.2 | June 3, 2026 | Project Initiation Team | Multi-domain scope (legal, healthcare, finance, tech, internal, education); multi-tier model selection (Tier 0–3: 7B→72B) with Qwen 2.5, Gemma 4, Ministral 3, DeepSeek-R1 distills; revised cost model for $30/month budget with < 100 queries/day full scale-to-zero; added Model Evaluation Gate (§3.2.2a); updated GPU tiers (A10G/L40S/A100-80GB); removed keep-warm schedule; added comprehensive evaluation framework (RAGAS + domain benchmark + cost/latency); MoE models excluded to v2 |
| 1.3 | June 3, 2026 | Project Initiation Team | AWS S3 storage integration (raw documents, converted output, checkpoints, eval artifacts); base vs. fine-tuned model comparison with toggle switch UI and automated comparative evaluation (§3.2.2b); model selection UI with budget-aware fine-tuning trigger and queue (§3.2.4b); model catalog API (`GET /api/models`, `POST /api/fine-tune`, `GET /api/budget`); hard block at $30 for fine-tuning jobs; S3 event-driven ingestion (SNS → SQS → Modal worker); S3 lifecycle policies and cost alerts; updated constraints (C-07 hard block), assumptions (A-14, A-15), deliverables (D-03b, D-15, D-16) |