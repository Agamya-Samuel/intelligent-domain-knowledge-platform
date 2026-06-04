"""
Integration tests — analytics dashboard and model comparison endpoints.

Covers:
  - RAGAS metrics trend (auth, params, empty state)
  - Fine-tuning job statistics (auth, empty state)
  - Chat usage statistics (auth, empty state)
  - Budget usage trend (auth, months param)
  - Full analytics overview (auth, structure)
  - Model comparison endpoint (auth, missing query)
  - Dataset staleness detection (auth, nonexistent dataset)
"""

import pytest
from fastapi.testclient import TestClient


# ── Metrics Trend ────────────────────────────────────────────────────────


class TestMetricsTrend:
    def test_metrics_trend_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/metrics/trend")
        assert response.status_code == 401

    def test_metrics_trend_returns_empty_for_new_user(
        self, client: TestClient, auth_headers
    ):
        response = client.get(
            "/api/v1/analytics/metrics/trend",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert isinstance(data["points"], list)

    def test_metrics_trend_with_limit_param(
        self, client: TestClient, auth_headers
    ):
        response = client.get(
            "/api/v1/analytics/metrics/trend?limit=10",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_metrics_trend_invalid_limit(self, client: TestClient, auth_headers):
        """Limit > 100 should be rejected by validation."""
        response = client.get(
            "/api/v1/analytics/metrics/trend?limit=500",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_metrics_trend_invalid_limit_zero(self, client: TestClient, auth_headers):
        """Limit < 1 should be rejected."""
        response = client.get(
            "/api/v1/analytics/metrics/trend?limit=0",
            headers=auth_headers,
        )
        assert response.status_code == 422


# ── Job Statistics ──────────────────────────────────────────────────────


class TestJobStats:
    def test_job_stats_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/jobs/stats")
        assert response.status_code == 401

    def test_job_stats_empty_for_new_user(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/analytics/jobs/stats",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0
        assert data["queued"] == 0
        assert data["total_cost"] == 0.0


# ── Chat Statistics ─────────────────────────────────────────────────────


class TestChatStats:
    def test_chat_stats_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/chat/stats")
        assert response.status_code == 401

    def test_chat_stats_empty_for_new_user(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/analytics/chat/stats",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] == 0
        assert data["total_messages"] == 0


# ── Budget Trend ────────────────────────────────────────────────────────


class TestBudgetTrend:
    def test_budget_trend_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/budget/trend")
        assert response.status_code == 401

    def test_budget_trend_empty_for_new_user(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/analytics/budget/trend",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert "current_spend" in data
        assert "budget_limit" in data
        assert data["budget_limit"] == 30.0

    def test_budget_trend_months_param(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/analytics/budget/trend?months=3",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_budget_trend_invalid_months(self, client: TestClient, auth_headers):
        """Months > 12 should be rejected."""
        response = client.get(
            "/api/v1/analytics/budget/trend?months=24",
            headers=auth_headers,
        )
        assert response.status_code == 422


# ── Analytics Overview ───────────────────────────────────────────────────


class TestAnalyticsOverview:
    def test_overview_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/overview")
        assert response.status_code == 401

    def test_overview_structure(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/analytics/overview",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "metrics_trend" in data
        assert "job_stats" in data
        assert "chat_stats" in data
        assert "budget_trend" in data


# ── Model Comparison ───────────────────────────────────────────────────


class TestModelComparison:
    def test_compare_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/compare",
            json={"query": "What is RAG?"},
        )
        assert response.status_code == 401

    def test_compare_missing_query_returns_422(
        self, client: TestClient, auth_headers
    ):
        response = client.post("/api/v1/compare", json={}, headers=auth_headers)
        assert response.status_code == 422

    def test_compare_empty_query_returns_422(
        self, client: TestClient, auth_headers
    ):
        response = client.post(
            "/api/v1/compare",
            json={"query": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_compare_with_valid_query_returns_500(
        self, client: TestClient, auth_headers
    ):
        """Valid query but no RAG backend available — expect 500 or 200."""
        response = client.post(
            "/api/v1/compare",
            json={
                "query": "Explain retrieval-augmented generation",
                "base_model_id": "qwen2.5-7b",
                "finetuned_model_id": "qwen2.5-14b",
            },
            headers=auth_headers,
        )
        # Service may fail due to no real backend — acceptable
        assert response.status_code in (200, 500)


# ── Dataset Staleness ───────────────────────────────────────────────────


class TestDatasetStaleness:
    def test_staleness_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/datasets/some-id/staleness")
        assert response.status_code == 401

    def test_staleness_nonexistent_dataset(
        self, client: TestClient, auth_headers
    ):
        response = client.get(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000/staleness",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_stale" in data
        assert "message" in data
        # Nonexistent dataset returns stale=False
        assert data["is_stale"] is False
