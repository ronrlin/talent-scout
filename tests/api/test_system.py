"""Tests for system endpoints (health, auth)."""

import pytest
from fastapi.testclient import TestClient

from api.app import create_app


class TestHealth:
    """Tests for GET /health."""

    def test_health_no_auth(self, client):
        """Health endpoint should work without auth."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAuth:
    """Tests for API key authentication."""

    def test_missing_key_returns_401(self, app):
        """Endpoints should reject requests without API key."""
        # Create a client that uses real auth (not overridden)
        from api.auth import verify_api_key
        from api import dependencies as deps

        # Remove the auth override
        real_app = create_app()
        real_app.dependency_overrides[deps.get_config] = app.dependency_overrides[deps.get_config]
        real_app.dependency_overrides[deps.get_data_store] = app.dependency_overrides[deps.get_data_store]
        real_app.dependency_overrides[deps.get_pipeline_store] = app.dependency_overrides[deps.get_pipeline_store]
        real_app.dependency_overrides[deps.get_task_manager] = app.dependency_overrides[deps.get_task_manager]
        real_app.dependency_overrides[deps.get_job_service] = app.dependency_overrides[deps.get_job_service]

        client = TestClient(real_app)
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 401


class TestTasks:
    """Tests for GET /api/v1/tasks."""

    def test_list_tasks_empty(self, client, auth_headers):
        resp = client.get("/api/v1/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_nonexistent_task(self, client, auth_headers):
        resp = client.get("/api/v1/tasks/nonexistent", headers=auth_headers)
        assert resp.status_code == 404
