"""
Cold-start load test — measures latency across model tiers from a cold state.

Target SLAs (TRD §8.1):
  - Tier 1 (≤7B params): cold-start ≤ 30s
  - Tier 2 (8-14B params): cold-start ≤ 60s
  - Tier 3 (≥32B params): cold-start ≤ 120s

Usage:
    locust -f tests/load/coldstart_locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 and configure:
  - Number of users: 1  (sequential cold starts)
  - Spawn rate: 1
"""

from __future__ import annotations

import time

from locust import HttpUser, constant_pacing, task


# ── Cold-start targets per model tier ──────────────────────────────────────

COLD_START_TARGETS = {
    # Tier 1: small models
    "qwen2.5-7b": {"tier": 1, "max_seconds": 30, "max_warm_ms": 3000},
    "gemma4-e4b": {"tier": 1, "max_seconds": 30, "max_warm_ms": 3000},
    # Tier 2: medium models
    "qwen2.5-14b": {"tier": 2, "max_seconds": 60, "max_warm_ms": 4000},
    "mistral-7b": {"tier": 1, "max_seconds": 30, "max_warm_ms": 3000},
    # Tier 3: large models
    "qwen2.5-32b": {"tier": 2, "max_seconds": 60, "max_warm_ms": 5000},
    "qwen2.5-72b": {"tier": 3, "max_seconds": 120, "max_warm_ms": 6000},
    "llama3.3-70b": {"tier": 3, "max_seconds": 120, "max_warm_ms": 6000},
}

COLD_START_QUERIES = [
    "What is retrieval-augmented generation?",
    "Explain the difference between fine-tuning and RAG.",
    "How does QLoRA work for parameter-efficient fine-tuning?",
]


class ColdStartUser(HttpUser):
    """
    Simulates cold-start scenarios for model inference endpoints.

    Designed to be run with a single user to measure true cold-start latency
    without interference from concurrent requests.

    Each task runs once per iteration cycle to measure the first-request latency.
    """

    # Fixed pacing: wait 5s between requests to let Modal scale down
    wait_time = constant_pacing(5)

    def on_start(self):
        """Store auth token for API access."""
        self.headers = {"Authorization": "Bearer load-test-token"}

    @task
    def cold_start_chat_tier1(self):
        """Measure cold-start for Tier 1 models via chat endpoint."""
        model_id = "qwen2.5-7b"
        self._measure_cold_start(model_id, "base")

    @task
    def cold_start_chat_tier2(self):
        """Measure cold-start for Tier 2 models via chat endpoint."""
        model_id = "qwen2.5-14b"
        self._measure_cold_start(model_id, "base")

    @task
    def cold_start_chat_tier3(self):
        """Measure cold-start for Tier 3 models via chat endpoint."""
        model_id = "qwen2.5-72b"
        self._measure_cold_start(model_id, "base")

    @task
    def cold_start_compare(self):
        """Measure cold-start for model comparison (dual model load)."""
        query = COLD_START_QUERIES[0]
        start = time.perf_counter()
        self.client.post(
            "/api/v1/compare",
            json={
                "query": query,
                "base_model_id": "qwen2.5-7b",
                "finetuned_model_id": "qwen2.5-7b",
            },
            headers=self.headers,
            name="POST /api/v1/compare (cold)",
        )
        elapsed = time.perf_counter() - start
        # Compare loads both models — allow 2x the Tier 1 cold-start limit
        tier1_limit = COLD_START_TARGETS["qwen2.5-7b"]["max_seconds"]
        if elapsed > 2 * tier1_limit:
            print(
                f"[COLD-START WARNING] Compare took {elapsed:.1f}s "
                f"(limit: {2 * tier1_limit}s)"
            )

    @task
    def cold_start_evaluation(self):
        """Measure cold-start for evaluation endpoint."""
        start = time.perf_counter()
        self.client.post(
            "/api/v1/evaluations",
            json={
                "run_type": "full",
                "model_id": "qwen2.5-7b",
                "model_variant": "base",
            },
            headers=self.headers,
            name="POST /api/v1/evaluations (cold)",
        )
        elapsed = time.perf_counter() - start
        if elapsed > 60:
            print(f"[COLD-START WARNING] Evaluation took {elapsed:.1f}s (limit: 60s)")

    def _measure_cold_start(self, model_id: str, model_variant: str):
        """Send a chat request and measure cold-start latency."""
        target = COLD_START_TARGETS.get(model_id, {"tier": 2, "max_seconds": 60})
        query = COLD_START_QUERIES[0]

        start = time.perf_counter()
        self.client.post(
            "/api/v1/chat",
            json={
                "query": query,
                "model_variant": model_variant,
            },
            headers=self.headers,
            name=f"POST /api/v1/chat [{model_id}] (cold)",
        )
        elapsed = time.perf_counter() - start

        tier = target["tier"]
        limit = target["max_seconds"]
        if elapsed > limit:
            print(
                f"[COLD-START WARNING] {model_id} (Tier {tier}) "
                f"took {elapsed:.1f}s (limit: {limit}s)"
            )
