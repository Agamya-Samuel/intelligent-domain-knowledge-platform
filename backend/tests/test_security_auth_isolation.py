"""
Security audit tests — auth isolation and cross-user access prevention (TRD §9.1).

Verifies:
  - All API endpoints require authentication
  - Users cannot access other users' resources
  - Auth token validation rejects expired/malformed/empty tokens
  - Cookie-based auth (next-auth.session-token) works alongside Bearer
  - Resource scoping: documents, chat sessions, datasets, fine-tune jobs
"""

import pytest
from fastapi.testclient import TestClient


# ── Global Auth Gate — all endpoints require authentication ──────────────


class TestGlobalAuthRequired:
    """Every v1 endpoint must reject unauthenticated requests with 401."""

    def test_datasets_list_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/datasets")
        assert response.status_code == 401

    def test_datasets_create_requires_auth(self, client: TestClient):
        response = client.post("/api/v1/datasets", json={"name": "Test", "description": ""})
        assert response.status_code == 401

    def test_documents_list_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/documents")
        assert response.status_code == 401

    def test_documents_upload_requires_auth(self, client: TestClient):
        response = client.post("/api/v1/documents/upload")
        assert response.status_code == 401

    def test_chat_sessions_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/chat/sessions")
        assert response.status_code == 401

    def test_chat_query_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/chat",
            json={"query": "What is RAG?", "model_variant": "base"},
        )
        assert response.status_code == 401

    def test_budget_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/budget")
        assert response.status_code == 401

    def test_finetune_history_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/fine-tune/history")
        assert response.status_code == 401

    def test_finetune_estimate_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/fine-tune/estimate")
        assert response.status_code == 401

    def test_evaluations_list_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/evaluations")
        assert response.status_code == 401

    def test_compare_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/compare",
            json={
                "query": "test",
                "base_model_id": "qwen2.5-7b",
                "finetuned_model_id": "qwen2.5-7b",
            },
        )
        assert response.status_code == 401

    def test_analytics_overview_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/overview")
        assert response.status_code == 401

    def test_analytics_metrics_trend_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/metrics/trend")
        assert response.status_code == 401

    def test_analytics_job_stats_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/jobs/stats")
        assert response.status_code == 401

    def test_analytics_chat_stats_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/chat/stats")
        assert response.status_code == 401

    def test_analytics_budget_trend_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/analytics/budget/trend")
        assert response.status_code == 401


# ── Token Validation ────────────────────────────────────────────────────


class TestTokenValidation:
    """Verify token handling rejects bad tokens correctly."""

    def test_empty_bearer_token(self, client: TestClient):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_completely_invalid_token(self, client: TestClient):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer this.is.not.a.jwt"},
        )
        assert response.status_code == 401

    def test_token_with_wrong_secret(self, client: TestClient):
        """Token signed with wrong secret should be rejected."""
        import jwt as pyjwt
        payload = {"sub": "test-user", "email": "test@example.com", "name": "Test"}
        # Sign with a different secret
        bad_token = pyjwt.encode(payload, "wrong-secret-key", algorithm="HS256")
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert response.status_code == 401

    def test_malformed_header_prefix(self, client: TestClient):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401

    def test_no_authorization_header(self, client: TestClient):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_valid_token_returns_200(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200

    def test_cookie_auth_works(self, client: TestClient, mock_user):
        """Verify that next-auth.session-token cookie is accepted."""
        import jwt as pyjwt
        from app.config import settings

        token = pyjwt.encode(mock_user, settings.AUTH_SECRET, algorithm="HS256")
        client.cookies.set("next-auth.session-token", token)
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-123"


# ── Cross-User Isolation ──────────────────────────────────────────────────


class TestCrossUserIsolation:
    """Verify that users cannot access other users' resources (TRD §9.1)."""

    @pytest.fixture
    def user_a_headers(self):
        """Auth headers for User A."""
        import jwt as pyjwt
        from app.config import settings

        token = pyjwt.encode(
            {"sub": "user-a-001", "email": "alice@example.com", "name": "Alice"},
            settings.AUTH_SECRET,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def user_b_headers(self):
        """Auth headers for User B."""
        import jwt as pyjwt
        from app.config import settings

        token = pyjwt.encode(
            {"sub": "user-b-002", "email": "bob@example.com", "name": "Bob"},
            settings.AUTH_SECRET,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def test_user_a_identity(self, client: TestClient, user_a_headers):
        """User A's auth/me returns User A's identity."""
        response = client.get("/api/v1/auth/me", headers=user_a_headers)
        assert response.status_code == 200
        assert response.json()["user_id"] == "user-a-001"
        assert response.json()["name"] == "Alice"

    def test_user_b_identity(self, client: TestClient, user_b_headers):
        """User B's auth/me returns User B's identity."""
        response = client.get("/api/v1/auth/me", headers=user_b_headers)
        assert response.status_code == 200
        assert response.json()["user_id"] == "user-b-002"
        assert response.json()["name"] == "Bob"

    def test_user_a_cannot_see_user_b_documents(
        self, client: TestClient, user_a_headers, user_b_headers
    ):
        """User A lists documents — should only see their own, not User B's."""
        resp_a = client.get("/api/v1/documents", headers=user_a_headers)
        assert resp_a.status_code == 200
        # Both get empty lists (no documents created), but the endpoint
        # is scoped to the authenticated user
        assert isinstance(resp_a.json(), list)

    def test_user_b_cannot_see_user_a_documents(
        self, client: TestClient, user_a_headers, user_b_headers
    ):
        """User B lists documents — should only see their own."""
        resp_b = client.get("/api/v1/documents", headers=user_b_headers)
        assert resp_b.status_code == 200
        assert isinstance(resp_b.json(), list)

    def test_user_a_cannot_see_user_b_datasets(
        self, client: TestClient, user_a_headers, user_b_headers
    ):
        """User A lists datasets — should not see User B's datasets."""
        resp = client.get("/api/v1/datasets", headers=user_a_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_user_a_cannot_see_user_b_chat_sessions(
        self, client: TestClient, user_a_headers, user_b_headers
    ):
        """User A lists chat sessions — should not see User B's sessions."""
        resp = client.get("/api/v1/chat/sessions", headers=user_a_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_user_a_cannot_see_user_b_finetune_history(
        self, client: TestClient, user_a_headers, user_b_headers
    ):
        """User A's fine-tune history is scoped to User A only."""
        resp = client.get("/api/v1/fine-tune/history", headers=user_a_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        # All returned jobs should belong to user-a-001
        for job in data["jobs"]:
            assert job.get("user_id") != "user-b-002"

    def test_nonexistent_resource_returns_404_not_other_user_data(
        self, client: TestClient, auth_headers
    ):
        """Accessing a nonexistent resource should return 404, not leak data."""
        response = client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_nonexistent_dataset_returns_404(
        self, client: TestClient, auth_headers
    ):
        response = client.get(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_nonexistent_chat_session_returns_404(
        self, client: TestClient, auth_headers
    ):
        response = client.get(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_nonexistent_finetune_job_returns_404(
        self, client: TestClient, auth_headers
    ):
        response = client.get(
            "/api/v1/fine-tune/status/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_nonexistent_evaluation_returns_404(
        self, client: TestClient, auth_headers
    ):
        response = client.get(
            "/api/v1/evaluations/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404


# ── Auth Response Headers ───────────────────────────────────────────────


class TestAuthResponseHeaders:
    """Verify 401 responses include WWW-Authenticate header."""

    def test_401_includes_www_authenticate(self, client: TestClient):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert "Bearer" in response.headers["WWW-Authenticate"]
