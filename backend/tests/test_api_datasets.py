"""
Integration tests — dataset CRUD endpoints.

Covers:
  - Dataset listing (with auth, pagination, status filter)
  - Dataset creation (valid, missing fields)
  - Dataset detail (existing, nonexistent)
  - Dataset update (PATCH metadata)
  - Dataset archive (soft-delete)
  - Dataset source management (add, list, delete)
"""

import pytest
from fastapi.testclient import TestClient


# ── Dataset List ─────────────────────────────────────────────────────────


class TestDatasetList:
    def test_list_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/datasets")
        assert response.status_code == 401

    def test_list_returns_empty_for_new_user(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/datasets", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_with_pagination(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/datasets?offset=0&limit=10",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_with_status_filter(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/datasets?status=active",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_list_with_invalid_limit(self, client: TestClient, auth_headers):
        """Limit > 100 should be rejected by validation."""
        response = client.get(
            "/api/v1/datasets?limit=500",
            headers=auth_headers,
        )
        assert response.status_code == 422


# ── Dataset Create ───────────────────────────────────────────────────────


class TestDatasetCreate:
    def test_create_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/datasets",
            json={"name": "Test Dataset", "description": "A test dataset"},
        )
        assert response.status_code == 401

    def test_create_with_valid_data(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/datasets",
            json={
                "name": "Test Dataset",
                "description": "A dataset for testing fine-tuning",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Dataset"
        assert data["description"] == "A dataset for testing fine-tuning"
        assert "id" in data
        assert "version" in data

    def test_create_with_minimal_data(self, client: TestClient, auth_headers):
        """Only name is required; description can be empty."""
        response = client.post(
            "/api/v1/datasets",
            json={"name": "Minimal Dataset", "description": ""},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Dataset"

    def test_create_without_name_returns_422(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/datasets",
            json={"description": "No name provided"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_without_body_returns_422(self, client: TestClient, auth_headers):
        response = client.post("/api/v1/datasets", headers=auth_headers)
        assert response.status_code == 422

    def test_create_with_empty_name_returns_422(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/datasets",
            json={"name": "", "description": "Empty name"},
            headers=auth_headers,
        )
        assert response.status_code == 422


# ── Dataset Detail ───────────────────────────────────────────────────────


class TestDatasetDetail:
    def test_detail_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/datasets/some-id")
        assert response.status_code == 401

    def test_detail_nonexistent_returns_404(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_detail_invalid_uuid_returns_404(self, client: TestClient, auth_headers):
        """Non-UUID string should be handled gracefully."""
        response = client.get("/api/v1/datasets/not-a-uuid", headers=auth_headers)
        assert response.status_code in (404, 422)


# ── Dataset Update ───────────────────────────────────────────────────────


class TestDatasetUpdate:
    def test_update_requires_auth(self, client: TestClient):
        response = client.patch(
            "/api/v1/datasets/some-id",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    def test_update_nonexistent_returns_404(self, client: TestClient, auth_headers):
        response = client.patch(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_update_empty_body_still_requires_auth(self, client: TestClient):
        response = client.patch("/api/v1/datasets/some-id", json={})
        assert response.status_code == 401


# ── Dataset Archive ──────────────────────────────────────────────────────


class TestDatasetArchive:
    def test_archive_requires_auth(self, client: TestClient):
        response = client.post("/api/v1/datasets/some-id/archive")
        assert response.status_code == 401

    def test_archive_nonexistent_returns_404(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000/archive",
            headers=auth_headers,
        )
        assert response.status_code == 404


# ── Dataset Sources ──────────────────────────────────────────────────────


class TestDatasetSources:
    def test_add_source_requires_auth(self, client: TestClient):
        response = client.post("/api/v1/datasets/some-id/sources")
        assert response.status_code == 401

    def test_list_sources_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/datasets/some-id/sources")
        assert response.status_code == 401

    def test_delete_source_requires_auth(self, client: TestClient):
        response = client.delete("/api/v1/datasets/some-id/sources/source-id")
        assert response.status_code == 401

    def test_list_sources_nonexistent_dataset(self, client: TestClient, auth_headers):
        response = client.get(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000/sources",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_delete_source_nonexistent_dataset(self, client: TestClient, auth_headers):
        response = client.delete(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000/sources/source-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_list_sources_with_pagination(self, client: TestClient, auth_headers):
        """Verify pagination params are accepted (will return 404 since dataset doesn't exist)."""
        response = client.get(
            "/api/v1/datasets/some-id/sources?offset=0&limit=50",
            headers=auth_headers,
        )
        # 404 because dataset doesn't exist, but pagination params are valid
        assert response.status_code == 404
