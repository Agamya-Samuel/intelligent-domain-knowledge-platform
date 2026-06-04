"""
Locust load test — simulates 100 concurrent chat users.

Target SLAs (TRD §8.2):
  - P50 < 500ms (warm)
  - P95 < 3s (warm)
  - Cold-start ≤ 30s for Tier 1 models

Usage:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 and configure:
  - Number of users: 100
  - Spawn rate: 10/s
"""

from __future__ import annotations

import json
import random
from locust import HttpUser, between, task


# ── Test data ──────────────────────────────────────────────────────────

SAMPLE_QUERIES = [
    "What is retrieval-augmented generation?",
    "Explain the difference between fine-tuning and RAG.",
    "How does QLoRA work for parameter-efficient fine-tuning?",
    "What are the benefits of semantic chunking?",
    "How does reciprocal rank fusion improve search results?",
    "What is cross-encoder reranking?",
    "Explain HyDE query expansion.",
    "What are the RAGAS evaluation metrics?",
    "How does the budget hard block work?",
    "What model tiers are available for fine-tuning?",
    "How does the citation extraction pipeline work?",
    "Explain the Self-RAG relevance gate.",
    "What is context compression in RAG?",
    "How are training datasets prepared for fine-tuning?",
    "What is a LoRA adapter and how is it served?",
]

SAMPLE_DATASETS = [
    "machine-learning-textbook",
    "api-documentation",
    "internal-wiki",
    "research-papers",
    "product-specs",
]


class IDKPUser(HttpUser):
    """
    Simulates an authenticated IDKP user performing typical workflows.

    Weight distribution:
      - 60% chat queries (most common action)
      - 15% document listing
      - 10% analytics
      - 10% model catalog
      - 5% budget check
    """

    wait_time = between(1, 5)  # 1-5 seconds between requests

    def on_start(self):
        """Login and store auth token."""
        # We mock a valid JWT token since we can't do Auth.js flow in load tests.
        # In staging, replace with actual login flow.
        self.headers = {"Authorization": "Bearer load-test-token"}
        # Mark skip for endpoints that require real DB
        self.skip_db_endpoints = True

    # ── Chat (highest frequency) ────────────────────────────────────────

    @task(6)
    def chat_query(self):
        """Simulate a chat query with streaming SSE."""
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/api/v1/chat",
            json={
                "query": query,
                "model_variant": random.choice(["base", "finetuned"]),
            },
            headers=self.headers,
            name="POST /api/v1/chat",
        )

    # ── Document listing ───────────────────────────────────────────────

    @task(3)
    def list_documents(self):
        """Browse the user's document library."""
        self.client.get(
            "/api/v1/documents?limit=20",
            headers=self.headers,
            name="GET /api/v1/documents",
        )

    # ── Analytics dashboard ──────────────────────────────────────────────

    @task(2)
    def get_analytics(self):
        """Fetch analytics summary."""
        self.client.get(
            "/api/v1/analytics/summary",
            headers=self.headers,
            name="GET /api/v1/analytics/summary",
        )

    @task(1)
    def get_metrics_trend(self):
        """Fetch RAGAS metrics trend."""
        self.client.get(
            "/api/v1/analytics/metrics-trend",
            headers=self.headers,
            name="GET /api/v1/analytics/metrics-trend",
        )

    # ── Model catalog ──────────────────────────────────────────────────

    @task(2)
    def list_models(self):
        """Browse available models."""
        self.client.get(
            "/api/v1/models",
            headers=self.headers,
            name="GET /api/v1/models",
        )

    # ── Budget check ───────────────────────────────────────────────────

    @task(1)
    def check_budget(self):
        """Check current budget usage."""
        self.client.get(
            "/api/v1/budget",
            headers=self.headers,
            name="GET /api/v1/budget",
        )

    # ── Health check (baseline) ───────────────────────────────────────

    @task(1)
    def health_check(self):
        """Lightweight health check (baseline latency)."""
        self.client.get("/health", name="GET /health")
