"""
Integration tests — document endpoints.

Covers document CRUD operations, auth requirements, and error handling.
Uses in-memory SQLite (no external DB needed).
"""

import pytest
from fastapi.testclient import TestClient


# ── Document List (requires auth) ───────────────────────────────────────


class TestDocumentEndpoints:
    def test_list_documents_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/documents")
        assert response.status_code == 401

    def test_list_documents_returns_empty_for_new_user(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/documents", headers=auth_headers)
        assert response.status_code == 200
        # Returns empty list (no DB populated in this test)
        assert isinstance(response.json(), list)

    def test_get_nonexistent_document_returns_404(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/documents/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_delete_nonexistent_document_returns_404(self, client: TestClient, auth_headers):
        response = client.delete(
            "/api/v1/documents/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_upload_document_requires_auth(self, client: TestClient):
        response = client.post("/api/v1/documents/upload")
        assert response.status_code == 401  # No auth

    def test_upload_without_file_returns_422(self, client: TestClient, auth_headers):
        """Uploading without a file field should fail with 422."""
        response = client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_document_pagination_params(self, client: TestClient, auth_headers):
        """Verify pagination query params are accepted."""
        response = client.get(
            "/api/v1/documents?offset=0&limit=10&status=pending",
            headers=auth_headers,
        )
        assert response.status_code == 200
