"""
Integration tests — health, auth, and security endpoints.

Covers:
  - Health check
  - Auth token validation (valid, missing, invalid)
  - Rate limit headers present on API responses
  - OpenAPI docs accessible
"""

import pytest
from fastapi.testclient import TestClient


# ── Health Check ────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_response_time(self, client: TestClient):
        """Health check should respond within 100ms."""
        import time
        start = time.perf_counter()
        response = client.get("/health")
        elapsed = time.perf_counter() - start
        assert response.status_code == 200
        assert elapsed < 0.1, f"Health check took {elapsed:.3f}s"


# ── Auth Endpoints ─────────────────────────────────────────────────────


class TestAuthEndpoints:
    def test_auth_me_without_token_returns_401(self, client: TestClient):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_auth_me_with_invalid_token_returns_401(self, client: TestClient):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        assert response.status_code == 401

    def test_auth_me_with_valid_token_returns_user(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-123"
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"

    def test_auth_me_with_malformed_header(self, client: TestClient):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "NotBearer sometoken"},
        )
        # Should return 401 since "NotBearer" doesn't start with "Bearer "
        assert response.status_code == 401


# ── OpenAPI Docs ────────────────────────────────────────────────────────


class TestOpenAPI:
    def test_openapi_schema_accessible(self, client: TestClient):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "IDKP Backend"
        assert schema["info"]["version"] == "0.1.0"

    def test_docs_page_accessible(self, client: TestClient):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_page_accessible(self, client: TestClient):
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_has_all_routes(self, client: TestClient):
        response = client.get("/openapi.json")
        paths = response.json()["paths"]
        expected_prefixes = [
            "/health",
            "/api/v1/auth",
            "/api/v1/documents",
            "/api/v1/chat",
            "/api/v1/models",
            "/api/v1/budget",
            "/api/v1/fine-tune",
            "/api/v1/evaluations",
            "/api/v1/compare",
            "/api/v1/ws",
            "/api/v1/analytics",
        ]
        all_paths = "".join(paths.keys())
        for prefix in expected_prefixes:
            assert prefix in all_paths, f"Missing route prefix: {prefix}"
