# Week 4 Evaluation Scaffold

## Intelligent Domain Knowledge Platform (IDKP) v1.0

---

> **Document Version:** 1.0
> **Date:** June 3, 2026
> **Phase:** Phase 1 Gate
> **Owner:** Engineering Team
> **Reviewers:** ML Engineer, Backend Engineer, DevOps/MLOps, Product Owner

---

## Table of Contents

1. [Overview](#1-overview)
2. [Week 4 Deliverables Summary](#2-week-4-deliverables-summary)
3. [Evaluation Framework](#3-evaluation-framework)
4. [Key Metrics](#4-key-metrics)
5. [Assessment Criteria](#5-assessment-criteria)
6. [Feedback Gathering Process](#6-feedback-gathering-process)
7. [Exit Criteria Validation](#7-exit-criteria-validation)
8. [Risk Assessment](#8-risk-assessment)
9. [Reporting Template](#9-reporting-template)

---

## 1. Overview

### 1.1 Purpose

This Evaluation Scaffold provides a structured framework for assessing the completion, quality, and readiness of Week 4 deliverables for the IDKP Phase 1 Gate. It defines quantitative metrics, qualitative criteria, and a systematic feedback collection process to ensure all deliverables meet the Technical Requirements Document (TRD) standards before proceeding to Phase 2.

### 1.2 Week 4 Context

**Goal:** Establish baseline RAG evaluation capabilities, complete model catalog infrastructure, and achieve full authentication integration across the application stack.

**Critical Path Position:** Week 4 represents the Phase 1 Gate - all foundational components must be operational and validated before advancing to fine-tuning activities in Phase 2.

**Success Definition:** All exit criteria met, RAGAS baseline established for future model comparisons, and auth-protected frontend fully functional.

### 1.3 Evaluation Scope

This scaffold evaluates:
- RAGAS evaluation harness implementation
- Ground-truth evaluation dataset quality
- Model catalog API completeness
- Fine-tuning trigger API skeleton
- Budget hard block logic validation
- Authentication flow end-to-end
- Model catalog frontend integration
- Chat interface streaming capability
- OpenTelemetry/Langfuse observability

**Out of Scope:** Advanced RAG components (Weeks 8-9), fine-tuning execution (Week 6), production deployment optimizations (Week 12)

---

## 2. Week 4 Deliverables Summary

| ID | Deliverable | Owner | Completion Target | TRD Reference |
|---|---|---|---|---|
| D4.1 | Ground-truth evaluation dataset (200+ Q&A pairs) | ML Eng + Domain Expert | Day 3 | §4.1 |
| D4.2 | RAGAS evaluation harness | ML Eng | Day 4 | §4.3 |
| D4.3 | Baseline RAGAS evaluation report | ML Eng | Day 5 | §4.3 |
| D4.4 | Model catalog API (`/api/models`, `/api/models/{id}`) | Backend | Day 2 | §6.3 |
| D4.5 | Fine-tune trigger API skeleton | Backend | Day 3 | §6.4 |
| D4.6 | Budget hard block logic ($30 limit) | Backend | Day 3 | §4.7 |
| D4.7 | Fine-tuning job queue (PostgreSQL FIFO) | Backend | Day 4 | §4.7 |
| D4.8 | Login page (NextAuth.js OAuth) | Frontend | Day 3 | §9.1 |
| D4.9 | Protected route middleware | Frontend | Day 4 | §9.1 |
| D4.10 | Model catalog page (4-tier grid) | Frontend | Day 4 | §12.B |
| D4.11 | Chat interface (SSE streaming + citations) | Frontend | Day 5 | §12.B |
| D4.12 | OpenTelemetry tracing configuration | DevOps | Day 4 | §11.2 |
| D4.13 | Langfuse dashboard setup | DevOps | Day 5 | §11.2 |

---

## 3. Evaluation Framework

### 3.1 Evaluation Timeline

```
Week 4 Schedule:
├── Day 1: Evaluation scaffold review + metric validation
├── Day 2: Early deliverable assessment (Model catalog API)
├── Day 3: Mid-week check (Auth flow, FT trigger skeleton)
├── Day 4: Pre-gate validation (RAGAS harness, job queue)
└── Day 5: Final gate assessment + report generation
```

### 3.2 Evaluation Layers

| Layer | Focus | Evaluation Method | Reviewer |
|---|---|---|---|
| **L1 - Code Quality** | Clean code, tests, documentation | Automated (lint, test coverage) + Code review | Peer Engineer |
| **L2 - Functional Completeness** | TRD requirements met | Integration tests + Manual validation | Component Owner |
| **L3 - System Integration** | End-to-end flows work | E2E test suite + smoke tests | Team Lead |
| **L4 - Production Readiness** | Performance, security, observability | Load tests + Security audit + Metrics review | DevOps/MLOps |

### 3.3 Evaluation Weighting

| Deliverable Category | Weight | Rationale |
|---|---|---|
| RAGAS Evaluation (D4.1-4.3) | 25% | Critical baseline for all future model comparisons |
| Model Catalog + FT API (D4.4-4.7) | 20% | Infrastructure for Phase 2 fine-tuning |
| Authentication (D4.8-4.9) | 20% | Security prerequisite for all protected features |
| Frontend Integration (D4.10-4.11) | 20% | User-facing validation of backend systems |
| Observability (D4.12-4.13) | 15% | Debugging and monitoring foundation |

---

## 4. Key Metrics

### 4.1 RAGAS Evaluation Metrics

| Metric | Target | Measurement Method | Data Source |
|---|---|---|---|
| **Dataset Size** | ≥ 200 Q&A pairs | Count unique question IDs | `eval/ground_truth/eval_dataset.json` |
| **Domain Coverage** | ≥ 3 domains covered | Manual audit of tags | Dataset metadata |
| **Question Diversity** | ≥ 80% unique intent types | Semantic clustering analysis | RAGAS dashboard |
| **Ground-truth Completeness** | 100% have answers + sources | Automated validation | Dataset schema check |
| **Faithfulness Score** | Baseline value (no target) | RAGAS automated evaluation | RAGAS output |
| **Context Relevance** | Baseline value (no target) | RAGAS automated evaluation | RAGAS output |
| **Answer Relevance** | Baseline value (no target) | RAGAS automated evaluation | RAGAS output |
| **Context Recall** | Baseline value (no target) | RAGAS automated evaluation | RAGAS output |
| **Evaluation Runtime** | ≤ 30 min for full dataset | Time measurement | RAGAS harness logs |
| **Result Persistence** | 100% saved to PostgreSQL + S3 | Database + S3 verification | `evaluation_runs` table + S3 |

### 4.2 Model Catalog API Metrics

| Metric | Target | Measurement Method | Data Source |
|---|---|---|---|
| **Model Count** | Exactly 9 models | Automated test count | `/api/models` response |
| **Tier Distribution** | 2 Tier 0, 3 Tier 1, 2 Tier 2, 2 Tier 3 | Schema validation | MODEL_CATALOG config |
| **API Response Time (GET /api/models)** | ≤ 100ms (P95) | Load test | Locust/k6 results |
| **API Response Time (GET /api/models/{id})** | ≤ 50ms (P95) | Load test | Locust/k6 results |
| **Metadata Completeness** | 100% fields populated per model | Schema validation | API response validation |
| **OpenAPI Spec Coverage** | 100% endpoints documented | Auto-generated spec review | FastAPI /docs |
| **Error Handling** | 404 for invalid IDs | Negative test suite | pytest results |

### 4.3 Fine-Tune Trigger API Metrics

| Metric | Target | Measurement Method | Data Source |
|---|---|---|---|
| **Auth Validation Success** | 100% blocked for unauthenticated | Negative test suite | API test logs |
| **Dataset Validation** | 100% rejected for archived datasets | Negative test suite | API test logs |
| **Budget Check Accuracy** | 0 false positives/negatives | Test suite with mock data | API test logs |
| **Hard Block Trigger** | HTTP 403 at $30.01+ | Budget overrun test | API response verification |
| **Queue Enqueue Rate** | 100% of requests queued when job running | Concurrency test | API + DB verification |
| **Queue Position Accuracy** | FIFO ordering maintained | Multi-request test | `queue_position` field validation |
| **Response Time** | ≤ 200ms (P95) | Load test | Locust/k6 results |

### 4.4 Budget Logic Metrics

| Metric | Target | Measurement Method | Data Source |
|---|---|---|---|
| **Spend Calculation Accuracy** | ±$0.01 variance vs. actual | Reconciliation test | Budget API vs. Modal billing |
| **Hard Block Threshold** | Block at $30.01, allow at $30.00 | Boundary value test | API test suite |
| **Queue Concurrency** | Max 1 job running | Concurrency stress test | `fine_tuning_jobs.status` query |
| **Budget Reset Logic** | Correct period boundary handling | Time simulation test | Budget API monthly reset |
| **No Caching** | 100% recalculation per request | Response variability test | Budget API monitoring |

### 4.5 Authentication Flow Metrics

| Metric | Target | Measurement Method | Data Source |
|---|---|---|---|
| **OAuth Provider Success (Google)** | ≥ 95% successful logins | User test session | Langfuse auth logs |
| **OAuth Provider Success (GitHub)** | ≥ 95% successful logins | User test session | Langfuse auth logs |
| **Session JWT Validation** | 100% valid tokens accepted | Backend dependency test | FastAPI auth logs |
| **Protected Route Block** | 100% redirect unauthenticated | Negative test suite | Playwright E2E tests |
| **Session Refresh Rate** | ≤ 1s refresh time | Performance test | NextAuth session API |
| **Logout Success** | 100% session termination | User test session | Playwright E2E tests |
| **Auth-to-API Handoff** | 0 auth failures in API calls | Integration test | FastAPI JWT dependency |

### 4.6 Frontend Integration Metrics

| Metric | Target | Measurement Method | Data Source |
|---|---|---|---|
| **Model Catalog Page Load** | ≤ 2s (FCP) | Lighthouse audit | Lighthouse report |
| **Model Card Render Count** | 9 cards displayed | Visual regression test | Percy/Cypress screenshots |
| **Chat SSE Connection** | 100% successful connections | Manual + automated test | WebSocket/SSE client logs |
| **Streaming Token Latency** | ≤ 100ms first token | Performance test | Browser devtools |
| **Citation Render Accuracy** | 100% citations visible in UI | Visual test + E2E | Playwright screenshot |
| **Chat Message Persistence** | 100% saved to PostgreSQL | DB query verification | `chat_messages` table |
| **Auth Redirect Success** | 100% redirect to login on protected routes | E2E test | Playwright test suite |

### 4.7 Observability Metrics

| Metric | Target | Measurement Method | Data Source |
|---|---|---|---|
| **Span Export Success Rate** | ≥ 99% traces exported | Langfuse dashboard | Langfuse trace count |
| **Query Trace Coverage** | 100% chat queries traced | Langfuse dashboard | Langfuse trace list |
| **Trace Link Completeness** | All 9 RAG components spanned | Trace validation | Langfuse span hierarchy |
| **Latency P95 Visibility** | 100% latency metrics captured | Langfuse metrics | Langfuse dashboard |
| **Error Trace Visibility** | 100% errors traced and tagged | Error injection test | Langfuse error list |
| **Dashboard Accessibility** | 100% team access to Langfuse | Access control audit | DevOps access logs |
| **Trace Retention** | ≥ 30 days retention | Langfuse config | Langfuse settings |

---

## 5. Assessment Criteria

### 5.1 D4.1: Ground-truth Evaluation Dataset

#### Pass Criteria
- [ ] **Quantity:** ≥ 200 unique Q&A pairs in `eval_dataset.json`
- [ ] **Schema Compliance:** Each entry has `{question, ground_truth_answer, source_references, domain_tags, difficulty_level}`
- [ ] **Source References:** 100% include valid `{document_id, page_number, section}` citations
- [ ] **Domain Diversity:** Covers ≥ 3 distinct domains (e.g., legal, healthcare, finance, tech, education)
- [ ] **Difficulty Distribution:** 40% easy, 40% medium, 20% hard (manual validation)
- [ ] **Question Types:** Mix of factual, analytical, multi-document reasoning questions
- [ ] **No Duplication:** ≤ 5% semantic similarity between questions
- [ ] **S3 Persistence:** Successfully uploaded to `s3://idkp-documents-dev/eval/ground_truth/eval_dataset.json`

#### Fail Criteria
- ❌ Dataset size < 200 pairs
- ❌ Missing required schema fields in > 10% of entries
- ❌ Duplicate or near-duplicate questions > 5%
- ❌ Invalid or broken source references > 5%
- ❌ Single domain coverage (no diversity)

#### Quality Score Calculation
```
Dataset Quality Score = (Size Score × 0.3) + (Schema Score × 0.2) + (Diversity Score × 0.2) + (Source Accuracy × 0.2) + (Citation Accuracy × 0.1)
Minimum Passing Score: 0.80
```

### 5.2 D4.2: RAGAS Evaluation Harness

#### Pass Criteria
- [ ] **Framework Installation:** RAGAS library integrated in backend dependencies
- [ ] **Metrics Computation:** Implements faithfulness, context_relevance, answer_relevance, context_recall
- [ ] **Baseline RAG Pipeline:** Integrates with Week 3 baseline RAG (dense search only)
- [ ] **Batch Processing:** Evaluates full dataset in single run
- [ ] **Result Persistence:** Saves metrics to `evaluation_runs` table + S3 JSON
- [ ] **Error Handling:** Graceful failure on individual questions (continues evaluation)
- [ ] **Runtime:** Completes ≥ 200 questions in ≤ 30 minutes on Modal T4
- [ ] **Unit Tests:** ≥ 80% coverage of evaluation harness functions

#### Fail Criteria
- ❌ Metrics not computed for RAGAS triad
- ❌ Evaluation crashes on invalid data
- ❌ Results not persisted to database
- ❌ No error handling for retrieval failures

#### Technical Validation Checklist
```python
# Evaluation Harness Validation Steps
[ ] 1. Load ground-truth dataset from S3
[ ] 2. Initialize baseline RAG retriever (Qdrant dense search)
[ ] 3. For each question in dataset:
[ ]     a. Retrieve top-5 chunks via baseline RAG
[ ]     b. Generate answer via vLLM (base model)
[ ]     c. Compute RAGAS triad metrics
[ ]     d. Store per-question results
[ ] 4. Aggregate metrics (mean, median, P25, P75)
[ ] 5. Insert row into evaluation_runs table
[ ] 6. Upload detailed JSON to S3 eval/baselines/{timestamp}.json
[ ] 7. Return summary report
```

### 5.3 D4.3: Baseline RAGAS Evaluation Report

#### Pass Criteria
- [ ] **Metrics Aggregation:** Includes mean, median, std, P25, P75 for all 4 RAGAS metrics
- [ ] **Per-Question Breakdown:** CSV/JSON with individual question scores
- [ ] **Fail Analysis:** Lists questions scoring < 0.5 on any metric
- [ ] **Latency Metrics:** Includes P50, P95, P99 retrieval + generation latency
- [ ] **Citation Accuracy:** % of answers with correct source references
- [ ] **Version Metadata:** Links to dataset version, model used, evaluation timestamp
- [ ] **S3 Storage:** Persisted to `s3://idkp-documents-dev/eval/baselines/{YYYY-MM-DD}-baseline.json`
- [ ] **Langfuse Integration:** Evaluation run logged as trace with metrics

#### Report Template
```json
{
  "evaluation_id": "uuid",
  "run_type": "baseline",
  "dataset_id": "uuid",
  "dataset_version": 1,
  "model_id": "qwen2.5-14b",
  "model_variant": "base",
  "timestamp": "2026-06-28T14:30:00Z",
  "dataset_size": 200,
  "metrics": {
    "faithfulness": {
      "mean": 0.82,
      "median": 0.85,
      "std": 0.12,
      "p25": 0.75,
      "p75": 0.90
    },
    "context_relevance": { /* ... */ },
    "answer_relevance": { /* ... */ },
    "context_recall": { /* ... */ }
  },
  "latency": {
    "retrieval_p50_ms": 250,
    "retrieval_p95_ms": 450,
    "generation_p50_ms": 1200,
    "generation_p95_ms": 1800
  },
  "citation_accuracy": 0.78,
  "failed_questions": [
    {"question_id": 1, "reasons": ["low_faithfulness", "no_citation"]},
    /* ... */
  ],
  "s3_report_path": "s3://idkp-documents-dev/eval/baselines/2026-06-28-baseline.json",
  "langfuse_trace_id": "trace-uuid"
}
```

### 5.4 D4.4: Model Catalog API

#### Pass Criteria
- [ ] **GET /api/models:** Returns array of 9 models with all metadata fields
- [ ] **GET /api/models/{id}:** Returns single model or 404 for invalid ID
- [ ] **Metadata Fields:** id, name, tier, size, gpu, vram_gb, est_cost, est_time_min, license, quality_rating, available
- [ ] **Tier Grouping:** Models correctly classified into Tiers 0-3
- [ ] **Response Time:** P95 ≤ 100ms for list, ≤ 50ms for detail
- [ ] **OpenAPI Documentation:** Auto-generated at `/docs`
- [ ] **Auth Middleware:** Returns 401 for unauthenticated requests
- [ ] **CORS:** Configured for frontend domain

#### API Contract Validation
```bash
# Test Commands
curl -X GET http://localhost:8000/api/models \
  -H "Authorization: Bearer <token>" \
  | jq '.models | length'  # Expect: 9

curl -X GET http://localhost:8000/api/models/qwen2.5-14b \
  -H "Authorization: Bearer <token>" \
  | jq '.tier'  # Expect: 1

curl -X GET http://localhost:8000/api/models/invalid-id \
  -H "Authorization: Bearer <token>" \
  # Expect: 404 Not Found
```

### 5.5 D4.5-D4.7: Fine-Tune Trigger API + Budget + Queue

#### Pass Criteria

**D4.5: Fine-Tune Trigger API Skeleton**
- [ ] **POST /api/fine-tune:** Accepts `{model_id, dataset_id}` JSON
- [ ] **Auth Validation:** Rejects unauthenticated with 401
- [ ] **Dataset Validation:** Checks dataset exists, active, not archived
- [ ] **Model Validation:** Validates model_id in MODEL_CATALOG
- [ ] **Queue Check:** Returns queue_position if job running
- [ ] **Immediate Start:** Returns 202 with job_id if queue empty
- [ ] **Error Responses:** Clear error messages for all failure cases

**D4.6: Budget Hard Block Logic**
- [ ] **Pre-Flight Check:** Calculates `total_spend + estimated_cost`
- [ ] **Hard Block:** Returns 403 if > $30
- [ ] **Budget API:** GET /api/budget returns spend, remaining, runs_left
- [ ] **Accumulation:** Correctly sums completed + running job costs
- [ ] **Estimation:** Uses MODEL_CATALOG[model_id].est_cost

**D4.7: Fine-Tuning Job Queue**
- [ ] **FIFO Ordering:** Jobs processed in order of creation
- [ ] **Concurrency Control:** Only one job with status='running'
- [ ] **Queue Position:** Tracks position for enqueued jobs
- [ ] **Status Transitions:** queued → training → evaluating → completed/failed
- [ ] **Job Metadata:** Links to dataset_version, model_id, modal_function_id

#### Integration Test Scenario
```python
def test_ft_trigger_with_budget_block():
    # Setup: Create dataset with $25 total spend
    # Attempt: Trigger FT with $6 estimated cost ($25 + $6 = $31 > $30)
    response = client.post("/api/fine-tune", json={
        "model_id": "qwen2.5-14b",  # est_cost: $3.50
        "dataset_id": dataset_id
    })
    assert response.status_code == 403
    assert "budget" in response.json()["detail"].lower()

def test_ft_queue_concurrency():
    # Trigger 2 FT jobs simultaneously
    job1 = trigger_ft("model1", "dataset1")
    job2 = trigger_ft("model2", "dataset2")

    # Verify: One running, one queued
    assert job1["status"] in ["running", "queued"]
    assert job2["status"] in ["running", "queued"]
    running_jobs = count_jobs_with_status("running")
    assert running_jobs == 1
```

### 5.6 D4.8-D4.9: Authentication Flow

#### Pass Criteria

**D4.8: Login Page**
- [ ] **OAuth Buttons:** Google + GitHub login buttons functional
- [ ] **OAuth Redirect:** Successful OAuth redirects to dashboard
- [ ] **Session Creation:** NextAuth session created on login
- [ ] **JWT Generation:** JWT token issued with correct claims
- [ ] **Error Handling:** OAuth errors display user-friendly messages
- [ ] **Logout Flow:** Logout button terminates session and redirects to login

**D4.9: Protected Route Middleware**
- [ ] **Middleware:** Applied to all dashboard routes
- [ ] **Unauthenticated Redirect:** Redirects to `/login` if no session
- [ ] **Session Refresh:** Auto-refreshes expired sessions
- [ ] **API Integration:** JWT passed to FastAPI in Authorization header
- [ ] **Cross-Domain:** Session persists across frontend and API

#### E2E Test Scenario (Playwright)
```typescript
test('auth flow end-to-end', async ({ page }) => {
  // 1. Access protected route unauthenticated
  await page.goto('/datasets');
  await expect(page).toHaveURL('/login');

  // 2. Login via Google OAuth
  await page.click('button:has-text("Sign in with Google")');
  // Mock OAuth redirect
  await page.goto('/api/auth/callback/google?code=mock_code');
  await expect(page).toHaveURL('/datasets');

  // 3. Access API with JWT
  const session = await page.evaluate(() => fetch('/api/auth/session'));
  const token = session.accessToken;

  const response = await fetch('http://localhost:8000/api/models', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  await expect(response.ok()).toBeTruthy();

  // 4. Logout
  await page.click('button:has-text("Sign out")');
  await expect(page).toHaveURL('/login');
});
```

### 5.7 D4.10: Model Catalog Page

#### Pass Criteria
- [ ] **4-Tier Grid:** Models grouped by tier (Tier 0, 1, 2, 3)
- [ ] **Model Cards:** Each card displays name, size, cost, GPU, license
- [ ] **Tier Badges:** Visual indicators for tier level
- [ ] **Availability Status:** Shows available/unavailable status
- [ ] **Responsive Design:** Grid adapts to mobile, tablet, desktop
- [ ] **Loading State:** Skeleton loaders during API fetch
- [ ] **Error Handling:** Graceful error message on API failure
- [ ] **Auth Protection:** Redirects to login if unauthenticated

#### Visual Validation Checklist
```
Tier 0 (Compact):
┌─────────────┐ ┌─────────────┐
│ Qwen 2.5 7B │ │ Gemma 4 E4B │
│ $2.00, 30m  │ │ $1.00, 20m  │
│ A10G        │ │ A10G        │
└─────────────┘ └─────────────┘

Tier 1 (Standard):
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Qwen 2.5 14B │ │ Ministral 3 │ │ DeepSeek-R1 │
│ $3.50, 60m  │ │ $4.00, 65m  │ │ $3.50, 55m  │
│ A10G        │ │ A10G        │ │ A10G        │
└─────────────┘ └─────────────┘ └─────────────┘
```

### 5.8 D4.11: Chat Interface

#### Pass Criteria
- [ ] **SSE Connection:** Establishes connection to `/api/chat`
- [ ] **Streaming Response:** Renders tokens as they arrive
- [ ] **Message History:** Displays user + assistant messages
- [ ] **Citation Rendering:** Shows citations inline with response
- [ ] **Citation Hover:** Hovering citation shows source + page
- [ ] **Loading State:** Typing indicator during generation
- [ ] **Error Handling:** Displays error message if stream fails
- [ ] **Message Persistence:** Saves to `chat_sessions` + `chat_messages`

#### SSE Event Validation
```typescript
// SSE Event Stream Verification
const eventSource = new EventSource('/api/chat?session_id=uuid');

eventSource.addEventListener('token', (e) => {
  const data = JSON.parse(e.data);
  // Expect: { content: "some text", citations: null }
  appendToken(data.content);
});

eventSource.addEventListener('citation', (e) => {
  const data = JSON.parse(e.data);
  // Expect: { source: "doc.pdf", page: 14, section: "Section 4" }
  renderCitation(data);
});

eventSource.addEventListener('done', (e) => {
  const data = JSON.parse(e.data);
  // Expect: { latency_ms: 1243, model_variant: "base", citations_count: 3 }
  showCompletionStats(data);
});
```

### 5.9 D4.12-D4.13: Observability

#### Pass Criteria

**D4.12: OpenTelemetry Tracing**
- [ ] **Span Creation:** All API endpoints create spans
- [ ] **Trace Propagation:** Trace IDs propagated to Modal functions
- [ ] **Span Hierarchy:** Parent-child spans for RAG components
- [ ] **Attribute Tagging:** Key metadata in span attributes (user_id, query, model_id)
- [ ] **Export Configuration:** Traces exported to Langfuse endpoint
- [ ] **Sampling:** 100% sampling rate for dev environment

**D4.13: Langfuse Dashboard**
- [ ] **Dashboard Access:** Team can access at `http://localhost:3000`
- [ ] **Trace List:** Shows recent chat queries with metadata
- [ ] **Span Detail:** Click-through to individual span details
- [ ] **Metrics Visualization:** Latency, error rate charts
- [ ] **Trace Search:** Filter by user_id, model_id, date range
- [ ] **Trace Download:** Export traces for analysis

#### Trace Validation Example
```
Expected Trace Hierarchy:
Chat Query (root)
├── Auth Validation
├── Query Expansion (HyDE)
├── Hybrid Retrieval
│   ├── Dense Search (Qdrant)
│   └── BM25 Search
├── Reciprocal Rank Fusion
├── Reranking (BGE-Reranker)
├── Context Compression
├── LLM Generation (vLLM)
└── Citation Extraction
```

---

## 6. Feedback Gathering Process

### 6.1 Stakeholder Feedback Channels

| Stakeholder | Feedback Method | Frequency | Owner |
|---|---|---|---|
| **ML Engineer** | Technical review (RAGAS, Modal) | Daily standup + Day 5 gate review | ML Eng Lead |
| **Backend Engineer** | API contract validation | Continuous + E2E test review | Backend Lead |
| **Frontend Engineer** | UX flow validation | Daily + usability testing | Frontend Lead |
| **DevOps/MLOps** | Infrastructure review | Day 4 + deployment validation | DevOps |
| **Domain Expert** | Dataset quality review | Day 3 (ground-truth) | Product Owner |
| **Product Owner** | Feature completeness | Day 5 gate review | Product Owner |

### 6.2 Feedback Collection Workflow

```
Day 1-4: Continuous Feedback Loop
├── Daily Standup (15 min)
│   ├── Blockers reported
│   ├── Progress against checklist
│   ├── Risk escalation
│   └── Action item assignment
├── Code Review (async)
│   ├── Pull request feedback
│   ├── Lint/test status checks
│   └── Approvals before merge
└── Integration Testing (continuous)
    ├── Automated test failures reported
    ├── E2E test results shared
    └── Bug ticket creation

Day 5: Gate Review (2 hours)
├── Deliverable walkthrough
├── Metrics presentation
├── Stakeholder Q&A
├── Go/No-Go decision
└── Action items for Phase 2
```

### 6.3 Feedback Forms

#### Technical Review Form (Daily)
```
Component: ______________________________
Reviewer: _______________________________  Date: ________

[ ] Code quality standards met
[ ] Tests passing (unit + integration)
[ ] Documentation complete
[ ] TRD requirements satisfied
[ ] No known blockers

Comments:
_________________________________________________________
_________________________________________________________
```

#### Gate Review Form (Day 5)
```
Deliverable: ______________________________
Reviewer: _______________________________  Date: ________

Completeness: [ ] Fully complete  [ ] Partially complete  [ ] Not started
Quality:      [ ] Production-ready  [ ] Needs refinement  [ ] Not acceptable
Risks:        [ ] None identified  [ ] Mitigable  [ ] Critical

Metric Validation:
[ ] All target metrics met
[ ] Performance SLAs met
[ ] Security requirements met
[ ] Observability configured

Go/No-Go Recommendation: [ ] GO  [ ] NO-GO
Rationale:
_________________________________________________________
_________________________________________________________
```

### 6.4 Issue Tracking and Resolution

| Issue Severity | Response Time | Resolution SLA | Escalation Path |
|---|---|---|---|
| **P0 (Blocker)** | Immediate | 4 hours | Engineering Lead → Product Owner |
| **P1 (Critical)** | 2 hours | 1 day | Component Owner → Team Lead |
| **P2 (Important)** | 4 hours | 2 days | Assignee → Daily Standup |
| **P3 (Nice-to-have)** | Next day | Phase 2 | Backlog for later |

### 6.5 Feedback Integration

**Feedback → Action Loop:**
```
1. Feedback collected via form/meeting
2. Issue created in tracking system (Jira/GitHub Issues)
3. Assignee notified with context
4. Resolution tracked in daily standup
5. Verification included in gate review
6. Closure documented in evaluation report
```

---

## 7. Exit Criteria Validation

### 7.1 Week 4 Exit Criteria Checklist

From Implementation Plan §164:

#### RAGAS Baseline
- [ ] **EC4.1:** RAGAS baseline established with metrics computed on 200+ Q&A pairs
  - Validation: `evaluation_runs` table row exists with `run_type='baseline'`
  - Evidence: Baseline report in S3 `eval/baselines/`

#### Model Catalog
- [ ] **EC4.2:** Model catalog page displays all 9 models across 4 tiers
  - Validation: Frontend screenshot showing 9 model cards
  - Evidence: `/api/models` returns 9 models, frontend renders correctly

#### Auth Flow
- [ ] **EC4.3:** Full auth flow: login → protected pages → API authorization
  - Validation: E2E test passes (Playwright)
  - Evidence: Test execution logs + screenshot

#### Chat UI
- [ ] **EC4.4:** Chat UI streams responses with basic citations
  - Validation: Manual test + SSE event logs
  - Evidence: Chat session in `chat_messages` table with citations

#### Fine-Tune API
- [ ] **EC4.5:** Fine-tune API skeleton validates auth, dataset, and budget
  - Validation: Integration test suite passes
  - Evidence: Test coverage report

#### Langfuse
- [ ] **EC4.6:** Langfuse shows distributed traces for chat queries
  - Validation: Langfuse trace list shows recent queries
  - Evidence: Screenshot of Langfuse dashboard

### 7.2 Gate Decision Framework

#### GO Decision Conditions
- [ ] All 6 exit criteria validated (100% completion)
- [ ] No P0 or P1 issues open
- [ ] All key metrics within target ranges
- [ ] Stakeholder approval received
- [ ] Documentation complete (baseline report, API docs)

#### NO-GO Decision Triggers
- [ ] Any exit criterion not met
- [ ] P0 or P1 blocker unresolved
- [ ] Critical metric failure (> 20% variance)
- [ ] Security vulnerability identified
- [ ] Stakeholder veto

#### CONDITIONAL GO Decision
- [ ] All exit criteria met except minor UI polish
- [ ] P2 issues with mitigations documented
- [ ] Technical debt identified with Phase 2 remediation plan
- [ ] Stakeholder approval with conditions

### 7.3 Gate Review Agenda

**Preparation (Day 5 Morning):**
- Generate evaluation report (Section 9 template)
- Collect all evidence (screenshots, logs, reports)
- Prepare slide deck (10-15 slides)

**Meeting (Day 5 Afternoon, 90 minutes):**
```
0:00-0:10: Introduction and agenda
0:10-0:30: Deliverable walkthrough (13 deliverables, ~1 min each)
0:30-0:40: Metrics presentation (key results vs. targets)
0:40-0:50: Demo walkthrough (auth flow, chat, model catalog)
0:50-0:60: Q&A and concerns
0:60-0:70: Risk assessment and mitigation
0:70-0:80: Go/No-Go discussion
0:80-0:90: Decision and action items
```

**Participants:**
- ML Engineer (2)
- Backend Engineer (2)
- DevOps/MLOps (1)
- Frontend Engineer (1)
- Product Owner (Gate Approver)

---

## 8. Risk Assessment

### 8.1 Week 4 Risks

| Risk ID | Risk Description | Likelihood | Impact | Mitigation Strategy | Owner |
|---|---|---|---|---|---|
| **R4.1** | Ground-truth dataset not ready by Day 3 | Medium | High | Start curation Week 1; have 100 pairs as minimum viable; supplement with synthetic | ML Eng |
| **R4.2** | RAGAS evaluation fails on baseline RAG | Low | High | Test RAGAS harness on small sample (10 questions) first; debug retrieval pipeline | ML Eng |
| **R4.3** | Modal GPU availability for evaluation | Low | Medium | Pre-book T4 GPU; have local fallback for testing | DevOps |
| **R4.4** | Auth.js JWT validation mismatch with FastAPI | Medium | High | Document JWT payload schema early; write integration test Day 2 | Backend |
| **R4.5** | SSE streaming not working in chat UI | Medium | Medium | Prototype SSE client Day 1; use standard EventSource API | Frontend |
| **R4.6** | Langfuse dashboard not accessible | Low | Medium | Test Langfuse setup Day 2; have fallback log aggregation | DevOps |
| **R4.7** | Budget calculation errors | Low | High | Write unit tests with edge cases ($29.99, $30.01, $0) | Backend |
| **R4.8** | Scope creep (extra features) | High | Medium | Locked TRD; any scope changes require formal CR | PM |

### 8.2 Risk Monitoring

**Daily Risk Review:**
```
Standup Question: "Any new or escalated risks?"
- New risks added to table
- Likelihood/impact reassessed
- Mitigation status updated
- Escalation if mitigation failing
```

**Risk Escalation Path:**
```
Day 1-2: Component owner mitigates
Day 3: Team lead escalates if mitigation failing
Day 4: Engineering lead escalates to product owner
Day 5: Gate review includes risk impact assessment
```

### 8.3 Risk Mitigation Success Criteria

| Risk | Success Criteria |
|---|---|
| R4.1 (Dataset) | ≥ 200 pairs by Day 3, ≥ 3 domains covered |
| R4.2 (RAGAS) | Evaluation completes on full dataset in ≤ 30 min |
| R4.3 (Modal) | Evaluation GPU available when triggered |
| R4.4 (Auth) | JWT validation passes in 100% of API calls |
| R4.5 (SSE) | Chat UI streams tokens with ≤ 100ms latency |
| R4.6 (Langfuse) | Dashboard accessible, traces visible |
| R4.7 (Budget) | Zero false positives/negatives in test suite |
| R4.8 (Scope) | No out-of-scope features delivered |

---

## 9. Reporting Template

### 9.1 Week 4 Gate Review Report

```markdown
# Week 4 Gate Review Report
## Intelligent Domain Knowledge Platform (IDKP) v1.0

---

**Report Date:** June 28, 2026
**Evaluation Period:** June 24-28, 2026
**Report Prepared By:** [Engineering Team]
**Gate Decision:** [GO / NO-GO / CONDITIONAL GO]

---

## Executive Summary

[Brief summary of Week 4 outcomes: 2-3 paragraphs highlighting key achievements, blockers, and decision rationale]

---

## Deliverable Completion Status

| Deliverable | Status | Completion % | Quality Score | Evidence |
|---|---|---|---|---|
| D4.1: Ground-truth dataset | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.2: RAGAS harness | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.3: Baseline eval report | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.4: Model catalog API | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.5: FT trigger API | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.6: Budget hard block | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.7: FT job queue | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.8: Login page | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.9: Protected routes | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.10: Model catalog page | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.11: Chat interface | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.12: OpenTelemetry | [✓/✗] | XX% | X.XX/1.0 | [Link] |
| D4.13: Langfuse dashboard | [✓/✗] | XX% | X.XX/1.0 | [Link] |

**Overall Completion:** XX/13 deliverables (XX%)

---

## Key Metrics Summary

### RAGAS Evaluation
- Dataset size: 200 pairs
- Faithfulness: 0.82 (baseline)
- Context relevance: 0.78 (baseline)
- Answer relevance: 0.80 (baseline)
- Context recall: 0.75 (baseline)
- Evaluation runtime: 28 min

### API Performance
- Model catalog (P95): 85ms (target: 100ms) ✓
- FT trigger (P95): 180ms (target: 200ms) ✓
- Budget API (P95): 45ms (target: 100ms) ✓

### Frontend Metrics
- Model catalog load (FCP): 1.8s (target: 2s) ✓
- Chat streaming latency: 95ms (target: 100ms) ✓
- Auth redirect success: 100% (target: 95%) ✓

### Observability
- Span export success: 99.2% (target: 99%) ✓
- Query trace coverage: 100% (target: 100%) ✓
- Dashboard accessibility: 100% (target: 100%) ✓

---

## Exit Criteria Validation

| Exit Criterion | Status | Evidence |
|---|---|---|
| EC4.1: RAGAS baseline established | [✓/✗] | [Link to report] |
| EC4.2: Model catalog displays 9 models | [✓/✗] | [Screenshot] |
| EC4.3: Full auth flow working | [✓/✗] | [E2E test logs] |
| EC4.4: Chat UI streams with citations | [✓/✗] | [SSE logs] |
| EC4.5: FT API validates auth/dataset/budget | [✓/✗] | [Test coverage] |
| EC4.6: Langfuse shows traces | [✓/✗] | [Dashboard screenshot] |

**Exit Criteria Met:** X/6 (XX%)

---

## Issue Summary

| Issue ID | Severity | Description | Status |
|---|---|---|---|
| I4.1 | P2 | UI polish on model cards | Open |
| I4.2 | P3 | Add loading skeleton to chat | Open |

**Open Issues:** X (P0: 0, P1: 0, P2: X, P3: X)

---

## Risk Assessment

### Risks Realized
[Document any risks that materialized during Week 4]

### Residual Risks
[Risks carried forward to Phase 2]

| Risk ID | Description | Mitigation Status |
|---|---|---|
| R4.1 | Dataset quality | [Mitigated/Partially mitigated/Not mitigated] |

---

## Stakeholder Feedback

### Technical Reviews
- **ML Engineer:** [Feedback summary]
- **Backend Engineer:** [Feedback summary]
- **Frontend Engineer:** [Feedback summary]
- **DevOps:** [Feedback summary]

### Product Owner Review
[Product owner's assessment of feature completeness and quality]

---

## Recommendations for Phase 2

### Immediate Actions (Week 5)
1. [Action item]
2. [Action item]

### Technical Debt
1. [Technical debt item]
2. [Technical debt item]

### Process Improvements
1. [Process improvement suggestion]
2. [Process improvement suggestion]

---

## Gate Decision

**Decision:** [GO / NO-GO / CONDITIONAL GO]

**Rationale:**
[Detailed explanation of decision factors]

**Conditions (if CONDITIONAL GO):**
1. [Condition 1]
2. [Condition 2]

**Next Steps:**
1. Proceed to Week 5: Model Evaluation Gate
2. [Additional steps]

**Approved By:** _______________________  Date: ________
(Product Owner)

---

## Appendix

### A. Evidence Links
- [Baseline RAGAS Report](s3://...)
- [Model Catalog Screenshot](/path/to/screenshot.png)
- [E2E Test Logs](/path/to/logs/)
- [Langfuse Dashboard](http://localhost:3000)

### B. Test Coverage Report
```
Backend:
  Unit tests: XX% coverage
  Integration tests: XX% coverage
  E2E tests: 100% pass rate

Frontend:
  Unit tests: XX% coverage
  E2E tests: 100% pass rate
```

### C. Meeting Attendees
- [Name] - [Role]
- [Name] - [Role]
```

---

## 10. Continuous Improvement

### 10.1 Lessons Learned Log

After Week 4 completion, document:

1. **What Went Well:**
   - [Example]: RAGAS integration smoother than expected
   - [Example]: Auth.js and FastAPI JWT aligned quickly

2. **What Could Be Improved:**
   - [Example]: Dataset curation started too late
   - [Example]: SSE debugging took longer than anticipated

3. **Process Changes for Next Week:**
   - [Action]: Start dataset curation in Week 1
   - [Action]: Prototype SSE client early in development

### 10.2 Evaluation Scaffold Feedback

This scaffold is a living document. Provide feedback to improve future evaluations:

- **Scaffold Clarity:** [Rate 1-5] - [Comments]
- **Metric Relevance:** [Rate 1-5] - [Comments]
- **Process Efficiency:** [Rate 1-5] - [Comments]
- **Suggestions:** [Additions/modifications]

---

*End of Week 4 Evaluation Scaffold*