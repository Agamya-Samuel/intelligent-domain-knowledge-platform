# Project Initiation Documentation (PID)
## Intelligent Domain Knowledge Platform (IDKP)
### Approach: Fine-tuning + Advanced RAG

---

> **Document Version:** 1.0
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

This Business Case proposes building the **Intelligent Domain Knowledge Platform (IDKP)** — a production-grade, 100% open-source AI system that combines **domain-specific Fine-tuning** with an **Advanced Retrieval-Augmented Generation (RAG)** pipeline. The system will serve a mixed corpus of 10–100 documents (PDFs, Markdown, code repositories, database records) that updates daily to near-real-time, and must answer complex queries across fact lookup, summarization, multi-document reasoning, technical support, and compliance/legal analysis — with precise source citations.

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
- **10–100 mixed-format documents** — rules out simple prompt stuffing (context window overflow); demands a proper retrieval layer
- **Multi-document reasoning and compliance/legal analysis** — rules out naive single-chunk retrieval; demands cross-document synthesis
- **Mandatory citations** ("According to page 14 of the PDF...") — rules out generation-only approaches with no retrieval grounding
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
│  Base: Llama 3.1 8B / Mistral 7B  |  Method: QLoRA (4-bit)      │
│  Trains on: domain Q&A pairs, document summaries, reasoning     │
│  cadence: one-time + periodic re-tune (monthly or on drift)     │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                     Augmented prompt
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  LAYER 2 — ADVANCED RAG PIPELINE                │
│                                                                 │
│  Ingestion ─► Chunking ─► Embedding ─► Vector DB                │
│                                                                 │
│  Query ─► Query Expansion ─► Hybrid Retrieval ─► Reranking      │
│                           (BM25 + Dense)     (Cross-encoder)    │
│                                                                 │
│  Metadata Filter ─► Citation Extraction ─► Context Assembly     │
│                                                                 │
│  cadence: near-real-time on document change                     │
└─────────────────────────────────────────────────────────────────┘
```

**Why this split works:**

- Fine-tuning bakes in domain vocabulary, output format, reasoning style, and citation behaviour. The model learns **how to think** in this domain.
- RAG brings the **latest facts**. Every document update is ingested, re-chunked, re-embedded, and available for retrieval within minutes — no retraining required.
- Together: a model that reasons like a domain expert and cites the most current version of your documents.

### 1.3.2 Open-Source Technology Stack

| Component | Selected Technology | Rationale |
|---|---|---|
| **Base LLM** | Llama 3.1 8B-Instruct or Mistral 7B-Instruct | Strong instruction following; Apache 2.0 / MIT licensed |
| **Fine-tuning method** | QLoRA via PEFT + Unsloth | 4-bit quantization; single 24GB GPU sufficient |
| **Embedding model** | BGE-M3 or E5-Large-v2 | State-of-the-art open-source retrieval embeddings |
| **Sparse retrieval** | BM25 (via Elasticsearch / OpenSearch or BM25s) | Exact token matching for IDs, codes, names |
| **Vector database** | Qdrant or Weaviate | OSS-first; production-grade; metadata filtering support |
| **Reranker** | BGE-Reranker-v2-m3 (Cross-Encoder) | Token-level late interaction; 30%+ relevance gains on hybrid results |
| **Orchestration** | LlamaIndex + LangChain | Modular; 300+ integrations; agent workflow support |
| **Document processing** | Unstructured.io + PyMuPDF + Tree-sitter | PDFs, Markdown, code repos, DB records |
| **LLM serving** | vLLM | High-throughput, low-latency open-source inference server |
| **Evaluation** | RAGAS | RAG Triad: context relevance, groundedness, answer relevance |
| **Monitoring** | OpenTelemetry + Langfuse | OSS tracing and observability |
| **Chat UI** | Chainlit or Open WebUI | Production-ready OSS chatbot interfaces |

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
| GPU compute (fine-tuning, A100/H100 cloud or on-prem) | ~$800–$2,500 per training run | ~$200–$600 (periodic re-tune) |
| Inference server (vLLM on 2× A10G or equivalent) | Hardware or cloud provisioning | ~$500–$1,200 |
| Vector database hosting (Qdrant self-hosted) | Setup effort | ~$50–$200 (storage + ops) |
| Engineering (ML + Backend + DevOps) | ~3–4 FTE × 14 weeks | ~0.5–1 FTE ongoing |
| Evaluation and QA dataset creation | ~2–4 weeks of effort | Periodic |

> Note: Figures are indicative and depend heavily on infrastructure choices (cloud vs on-prem), team seniority, and document volume growth.

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
| GPU availability for training runs | Low | Medium | Pre-book cloud GPU instances; use QLoRA to reduce VRAM requirements |
| Scope creep (multi-language, audio, images) | High | Medium | Lock scope statement before sprint 1; defer to v2 roadmap |
| Model drift after domain corpus changes significantly | Low | High | Set up automated RAGAS evaluation; schedule re-tune trigger on drift threshold |

---

## 1.7 Recommendation

**Proceed with the Fine-tuning + Advanced RAG approach** as proposed. The combination uniquely satisfies all stated requirements: open-source-only, daily-to-real-time document updates, citation-backed responses, multi-query type support, and triple deployment targets (public chatbot, internal tool, agent system).

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
| **Target Go-Live** | 14 weeks from kickoff |

---

## 2.2 Project Overview

The IDKP project delivers a **production-grade, open-source AI question-answering system** that draws on a continuously updated private knowledge corpus. The platform serves three deployment targets simultaneously: a public-facing chatbot, an internal company tool, and a programmatic agent interface.

The system uses a two-layer architecture:

1. **Fine-tuned LLM layer** — A Llama 3.1 8B or Mistral 7B model, adapted to the domain using QLoRA fine-tuning on curated question-answer pairs derived from the document corpus. This gives the model deep fluency in domain vocabulary, output formats, and reasoning patterns.

2. **Advanced RAG layer** — A real-time retrieval pipeline that ingests document updates, indexes them using hybrid sparse + dense search, reranks retrieved chunks using a cross-encoder model, and injects grounded, page-level citations into the generated response.

---

## 2.3 Objectives

| # | Objective | Measurable Success Criterion |
|---|---|---|
| O-01 | Domain-adapted LLM deployed | Fine-tuned model outperforms base model by ≥ 15% on domain eval benchmark |
| O-02 | Real-time document ingestion pipeline operational | New/updated documents indexed within ≤ 5 minutes of change |
| O-03 | Advanced RAG pipeline deployed with hybrid retrieval and reranking | Retrieval Precision@5 ≥ 85% on held-out evaluation set |
| O-04 | Citation-backed responses with source + page reference | Citation accuracy ≥ 95% on factual queries |
| O-05 | Public chatbot live | P95 response latency ≤ 3 seconds |
| O-06 | Internal API and agent interface deployed | REST API with OpenAPI spec; agent tool wrapper documented |
| O-07 | Evaluation and monitoring in production | RAGAS metrics tracked; alerts on faithfulness drop below 0.85 |

---

## 2.4 Key Deliverables

### Phase 1 — Foundation (Weeks 1–4)

- Document ingestion pipeline supporting PDF, Markdown, code repositories, and database records
- Parsing, cleaning, and metadata extraction per source type
- Semantic chunking strategy implemented and benchmarked
- Vector database provisioned with hybrid index (dense + BM25)
- Baseline RAG pipeline (naive retrieval) with evaluation scaffold (RAGAS)
- Ground-truth evaluation dataset (minimum 200 Q&A pairs) curated from document corpus

### Phase 2 — Fine-tuning (Weeks 5–7)

- Fine-tuning dataset prepared (instruction-tuning format from domain Q&A pairs and document summaries)
- QLoRA training run executed on selected base model (Llama 3.1 8B or Mistral 7B)
- LoRA adapter evaluated against baseline; domain benchmark report produced
- Model served via vLLM with LoRA adapter loading support

### Phase 3 — Advanced RAG (Weeks 8–10)

- Hybrid retrieval implemented (BM25 + dense vector search with Reciprocal Rank Fusion)
- Cross-encoder reranker integrated (BGE-Reranker-v2-m3)
- Query expansion and HyDE (Hypothetical Document Embeddings) implemented
- Metadata filtering operational (source type, date, document ID, page number)
- Citation extraction and injection into responses implemented
- RAGAS evaluation: faithfulness, context relevance, answer relevance tracked end-to-end

### Phase 4 — Integration & Testing (Weeks 11–12)

- Fine-tuned LLM + Advanced RAG pipeline integrated end-to-end
- Public chatbot interface deployed (Chainlit or Open WebUI)
- Internal REST API documented and tested (OpenAPI spec)
- Agent tool wrapper implemented (LangChain/LlamaIndex tool interface)
- Load testing: simulate 100 concurrent users; validate latency SLA
- Security review: input sanitisation, rate limiting, prompt injection hardening

### Phase 5 — Deployment & Monitoring (Weeks 13–14)

- Production infrastructure provisioned (inference server, vector DB, ingestion worker)
- CI/CD pipeline for document ingestion (trigger on file change / DB event)
- Automated re-indexing on document update
- OpenTelemetry tracing + Langfuse dashboard live
- Automated RAGAS regression testing on weekly eval batch
- Runbooks: deployment, reindexing, model re-tune trigger, rollback procedures
- Stakeholder handover and demo

---

## 2.5 Technology Stack Summary

### Core AI Components

| Component | Technology | License |
|---|---|---|
| Base LLM | Llama 3.1 8B-Instruct | Meta Llama 3.1 Community License |
| Fine-tuning framework | Unsloth + PEFT (QLoRA) | Apache 2.0 |
| LLM inference | vLLM | Apache 2.0 |
| Embedding model | BGE-M3 | MIT |
| Reranker | BGE-Reranker-v2-m3 | MIT |

### Retrieval & Storage

| Component | Technology | License |
|---|---|---|
| Vector database | Qdrant (self-hosted) | Apache 2.0 |
| Sparse retrieval | BM25s or Elasticsearch OSS | Apache 2.0 |
| Hybrid fusion | Reciprocal Rank Fusion (RRF) | Algorithm (no license) |
| Document store | PostgreSQL | PostgreSQL License |

### Ingestion & Processing

| Component | Technology | License |
|---|---|---|
| PDF parsing | PyMuPDF + Unstructured.io | AGPL (OSS) |
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
Week  1  2  3  4  5  6  7  8  9  10  11  12  13  14
      │────────────────│
      Phase 1: Foundation
                       │──────────│
                       Phase 2: Fine-tuning
                                  │──────────│
                                  Phase 3: Advanced RAG
                                             │───────────│
                                             Phase 4: Integration
                                                          │────────│
                                                          Phase 5: Deploy
```

---

## 2.8 Key Assumptions

- GPU compute (minimum 24 GB VRAM, e.g., NVIDIA A10G / RTX 4090) is available or can be provisioned for fine-tuning within Week 1
- Domain experts are available to curate a minimum of 200 high-quality Q&A evaluation pairs in Phase 1
- Document sources (PDFs, Markdown files, code repositories, DB records) are accessible to the engineering team from the start of Phase 1
- The team has working proficiency in Python, PyTorch, and Hugging Face ecosystem
- No multi-language requirement in v1 (English only)

---

## 2.9 Success Metrics Summary

| Metric | Target | Measurement Tool |
|---|---|---|
| Retrieval Precision@5 | ≥ 85% | RAGAS / custom eval harness |
| Answer Faithfulness | ≥ 0.90 | RAGAS faithfulness metric |
| Citation Accuracy | ≥ 95% | Manual spot-check + automated page-reference validation |
| Response Latency (P95) | ≤ 3 seconds | Load test + production monitoring |
| Document Ingestion Latency | ≤ 5 minutes | Ingestion pipeline monitoring |
| Fine-tuned model lift over base | ≥ 15% | Domain benchmark (held-out eval set) |
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

- Ingestion of **PDF documents** (text-based; scanned PDFs with OCR as stretch goal)
- Ingestion of **Markdown documents** (including frontmatter metadata)
- Ingestion of **code repositories** (Python, JavaScript, and generic text-based formats; parsed with Tree-sitter)
- Ingestion of **database records** (structured data exported or streamed as JSON/CSV; ingested as text chunks with metadata)
- Metadata extraction per document: source file, document type, creation/update timestamp, page numbers, section headers
- **Real-time/near-real-time update mechanism**: event-driven re-ingestion triggered by file system watch, webhook, or database change event; target latency ≤ 5 minutes end-to-end
- Document deduplication and version tracking (new version replaces old vectors for the same document ID)

### 3.2.2 Fine-tuning Pipeline

- **Base model selection**: Llama 3.1 8B-Instruct or Mistral 7B-Instruct (evaluated and chosen in Phase 2)
- **QLoRA fine-tuning** using PEFT + Unsloth on curated domain instruction-tuning dataset
- Fine-tuning dataset construction from: domain Q&A pairs, document summaries, multi-document reasoning examples, citation-format examples
- LoRA adapter training, checkpointing, and evaluation
- Domain benchmark evaluation report comparing fine-tuned vs base model
- Adapter merging and serving setup via vLLM with LoRA hot-loading

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

| Item | Reason for Exclusion |
|---|---|
| **Proprietary LLM APIs** (OpenAI, Anthropic, Cohere, etc.) | Hard constraint: open-source only |
| **Multi-language support** (non-English) | Deferred to v2; increases embedding and evaluation complexity significantly |
| **Voice / audio interfaces** | Distinct product category; separate project |
| **Image or video document processing** | Scanned PDF OCR is a stretch goal only; no visual QA or video indexing |
| **Full model retraining from scratch** | QLoRA fine-tuning sufficient; full training requires prohibitive compute |
| **Custom UI/UX design** | Functional OSS chatbot UI only; bespoke frontend design deferred |
| **Mobile application** | Web-based chatbot is sufficient for v1 |
| **Integration with external live data feeds** (real-time APIs, stock feeds, etc.) | Only static documents and DB exports are in scope |
| **Multi-tenant SaaS architecture** | Single-tenant deployment only in v1 |
| **GDPR / data residency compliance engineering** | Legal review is the organisation's responsibility; platform is designed to run on-prem to support this, but compliance certification is out of scope |
| **Automated fine-tuning on document updates** | Fine-tuning is periodic/manual; RAG handles real-time knowledge; auto-retraining adds risk of instability |

---

## 3.4 Assumptions

The project plan is built on the following assumptions. If any assumption is found to be false, a change request must be raised immediately.

| # | Assumption |
|---|---|
| A-01 | GPU compute with ≥ 24 GB VRAM (e.g., NVIDIA A10G, A100, or RTX 4090) is available or provisionable by the start of Phase 2 |
| A-02 | Domain experts can dedicate ~2–4 hours per week during Phase 1 to curate ground-truth Q&A evaluation pairs |
| A-03 | All documents (PDFs, Markdown, code repos, DB records) are accessible in a readable, non-DRM-protected format |
| A-04 | The team has working proficiency in Python, PyTorch, Hugging Face Transformers, and FastAPI |
| A-05 | A minimum of 200 high-quality Q&A pairs can be curated from the document corpus for evaluation |
| A-06 | An infrastructure environment (cloud or on-prem) with at least 32 GB RAM and 500 GB storage is available for hosting the vector DB and inference server |
| A-07 | Document source systems (file system, DB, code repo) can emit change events or be polled; access credentials will be provided before Phase 1 |
| A-08 | v1 documents are in English only |
| A-09 | No existing vendor contracts restrict use of the proposed open-source components |

---

## 3.5 Constraints

| # | Constraint | Impact |
|---|---|---|
| C-01 | **100% open-source stack** — no proprietary model APIs, no closed-source SaaS | All component selection must verify OSS license (Apache 2.0, MIT, BSD preferred) |
| C-02 | **No calls to OpenAI, Anthropic, or equivalent APIs** at any point in the pipeline | Evaluation (including LLM-as-judge) must use self-hosted open-source models only |
| C-03 | **Daily-to-near-real-time document updates** must be reflected in query results | Ingestion pipeline must be event-driven, not batch-nightly |
| C-04 | **Mandatory citations** on all factual responses | RAG pipeline must extract and preserve page/section provenance through the full pipeline |
| C-05 | **Accuracy and Speed are co-equal** | No aggressive context compression that hurts accuracy; no reranking skip that hurts latency; must be benchmarked together |
| C-06 | **Fine-tuning must not regress general language ability** | Training data must include ~5–10% general-domain examples to prevent catastrophic forgetting |

---

## 3.6 Deliverables Register

| ID | Deliverable | Phase | Acceptance Criteria |
|---|---|---|---|
| D-01 | Document ingestion pipeline (all 4 source types) | 1 | All source types indexed; documents searchable within ≤ 5 min of update |
| D-02 | Ground-truth evaluation dataset (≥ 200 Q&A pairs) | 1 | Reviewed and approved by domain expert |
| D-03 | Baseline RAG evaluation report | 1 | RAGAS metrics established as baseline |
| D-04 | QLoRA fine-tuning run + LoRA adapter | 2 | ≥ 15% improvement over base on domain benchmark |
| D-05 | Fine-tuned model domain benchmark report | 2 | Signed off by ML Engineer and Product Owner |
| D-06 | Advanced RAG pipeline (all 9 components) | 3 | Retrieval Precision@5 ≥ 85%; citations present in ≥ 95% of factual answers |
| D-07 | End-to-end integrated system | 4 | RAGAS faithfulness ≥ 0.90; P95 latency ≤ 3 s under load |
| D-08 | Public chatbot (live URL) | 4–5 | User acceptance testing passed |
| D-09 | Internal REST API (OpenAPI spec) | 4–5 | API contract reviewed and approved |
| D-10 | Agent tool wrapper | 4–5 | Successfully executes in LangGraph and LlamaIndex agent demos |
| D-11 | Monitoring dashboard (Langfuse + OTel) | 5 | All defined metrics visible; alert rules active |
| D-12 | Operator runbooks + architecture documentation | 5 | Reviewed and signed off by DevOps and Product Owner |

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
> | 1.0 | TBD | Project Manager | Approved for execution |