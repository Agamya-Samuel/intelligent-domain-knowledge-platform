"""
Integration tests — evaluation, benchmark, and comparison endpoints.

Covers:
  - Evaluation history (auth, empty, pagination, filtering)
  - Evaluation detail (existing, nonexistent)
  - Evaluation creation (trigger run with valid body)
  - Benchmark (valid model IDs, invalid model IDs, empty list)
  - Evaluation comparison (nonexistent IDs, same ID)
"""

import pytest
from fastapi.testclient import TestClient


# ── Evaluation History ──────────────────────────────────────────────────


class TestEvaluationHistory:
    def test_history_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/evaluations")
        assert response.status_code == 401

    def test_history_returns_empty_for_new_user(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/evaluations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "evaluations" in data
        assert "total" in data
        assert isinstance(data["evaluations"], list)

    def test_history_with_pagination(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/evaluations?offset=0&limit=10",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_history_with_invalid_limit(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/evaluations?limit=500",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_history_filter_by_run_type(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/evaluations?run_type=baseline",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_history_filter_by_status(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/evaluations?status=completed",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_history_filter_by_type_and_status(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/evaluations?run_type=benchmark&status=completed",
            headers=auth_headers,
        )
        assert response.status_code == 200


# ── Evaluation Detail ──────────────────────────────────────────────────


class TestEvaluationDetail:
    def test_detail_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/evaluations/some-id")
        assert response.status_code == 401

    def test_detail_nonexistent_returns_404(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/evaluations/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_detail_nonexistent_includes_detail(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/evaluations/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


# ── Evaluation Creation ────────────────────────────────────────────────


class TestEvaluationCreate:
    def test_create_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/evaluations",
            json={"run_type": "baseline"},
        )
        assert response.status_code == 401

    def test_create_missing_run_type_returns_422(
        self, client: TestClient, auth_headers
    ):
        response = client.post(
            "/api/v1/evaluations",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_invalid_run_type_returns_422(
        self, client: TestClient, auth_headers
    ):
        response = client.post(
            "/api/v1/evaluations",
            json={"run_type": "invalid_type"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_with_valid_baseline(self, client: TestClient, auth_headers):
        """Baseline eval should return 201 (may complete or fail depending on backend)."""
        response = client.post(
            "/api/v1/evaluations",
            json={"run_type": "baseline", "model_variant": "base"},
            headers=auth_headers,
        )
        # With empty eval dataset, service returns completed with no metrics
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["run_type"] == "baseline"
        assert "status" in data
        assert "created_at" in data

    def test_create_with_model_id(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/evaluations",
            json={
                "run_type": "baseline",
                "model_id": "qwen2.5-7b",
                "model_variant": "base",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["model_id"] == "qwen2.5-7b"

    def test_create_with_job_id(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/evaluations",
            json={
                "run_type": "post_training",
                "job_id": "00000000-0000-0000-0000-000000000000",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201


# ── Benchmark ────────────────────────────────────────────────────────────


class TestBenchmark:
    def test_benchmark_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/evaluations/benchmark",
            json={"model_ids": ["qwen2.5-7b"]},
        )
        assert response.status_code == 401

    def test_benchmark_missing_model_ids_returns_422(
        self, client: TestClient, auth_headers
    ):
        response = client.post(
            "/api/v1/evaluations/benchmark",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_benchmark_empty_model_ids_returns_422(
        self, client: TestClient, auth_headers
    ):
        response = client.post(
            "/api/v1/evaluations/benchmark",
            json={"model_ids": []},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_benchmark_too_many_models_returns_422(
        self, client: TestClient, auth_headers
    ):
        """Benchmark allows max 5 models."""
        response = client.post(
            "/api/v1/evaluations/benchmark",
            json={
                "model_ids": [
                    "qwen2.5-7b", "gemma4-e4b", "qwen2.5-14b",
                    "ministral3-14b", "deepseek-r1-14b", "qwen2.5-32b",
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_benchmark_invalid_model_ids_returns_422(
        self, client: TestClient, auth_headers
    ):
        """Unknown model IDs should return 422."""
        response = client.post(
            "/api/v1/evaluations/benchmark",
            json={"model_ids": ["nonexistent-model"]},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_benchmark_single_valid_model(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/evaluations/benchmark",
            json={"model_ids": ["qwen2.5-7b"]},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "benchmark_id" in data
        assert "results" in data
        assert data["total_models"] == 1

    def test_benchmark_multiple_valid_models(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/evaluations/benchmark",
            json={
                "model_ids": ["qwen2.5-7b", "qwen2.5-14b"],
                "model_variant": "base",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total_models"] == 2
        assert len(data["results"]) == 2


# ── Evaluation Comparison ───────────────────────────────────────────────


class TestEvaluationComparison:
    def test_compare_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/evaluations/compare",
            json={
                "base_eval_id": "id1",
                "candidate_eval_id": "id2",
            },
        )
        assert response.status_code == 401

    def test_compare_missing_fields_returns_422(
        self, client: TestClient, auth_headers
    ):
        response = client.post(
            "/api/v1/evaluations/compare",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_compare_nonexistent_evals_returns_404(
        self, client: TestClient, auth_headers
    ):
        response = client.post(
            "/api/v1/evaluations/compare",
            json={
                "base_eval_id": "00000000-0000-0000-0000-000000000000",
                "candidate_eval_id": "00000000-0000-0000-0000-000000000001",
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_compare_same_eval_id_returns_404(
        self, client: TestClient, auth_headers
    ):
        """Comparing an eval to itself should still work or return 404."""
        response = client.post(
            "/api/v1/evaluations/compare",
            json={
                "base_eval_id": "00000000-0000-0000-0000-000000000000",
                "candidate_eval_id": "00000000-0000-0000-0000-000000000000",
            },
            headers=auth_headers,
        )
        # Both point to same nonexistent ID — not found
        assert response.status_code == 404

    def test_compare_response_structure(self):
        """Verify the comparison response schema fields are correct."""
        from app.schemas.evaluation import ComparisonResponse

        # Validate the schema structure
        field_names = set(ComparisonResponse.model_fields.keys())
        expected = {
            "base_eval_id", "candidate_eval_id",
            "base_metrics", "candidate_metrics",
            "deltas", "winner",
        }
        assert expected.issubset(field_names)


# ── Model Catalog Validation ───────────────────────────────────────────


class TestModelCatalog:
    def test_catalog_has_expected_models(self):
        from app.config import MODEL_CATALOG

        ids = {m["id"] for m in MODEL_CATALOG}
        assert "qwen2.5-7b" in ids
        assert "qwen2.5-14b" in ids
        assert "qwen2.5-72b" in ids

    def test_catalog_models_have_required_fields(self):
        from app.config import MODEL_CATALOG

        for model in MODEL_CATALOG:
            assert "id" in model
            assert "name" in model
            assert "tier" in model
            assert "est_cost" in model
            assert "gpu" in model

    def test_catalog_tiers_are_sequential(self):
        from app.config import MODEL_CATALOG

        tiers = {m["tier"] for m in MODEL_CATALOG}
        assert tiers == {0, 1, 2, 3}
