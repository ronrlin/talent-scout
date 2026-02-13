"""Tests for Pipeline API endpoints."""

import pytest


class TestPipelineOverview:
    """Tests for GET /api/v1/pipeline."""

    def test_pipeline_empty(self, client, auth_headers):
        resp = client.get("/api/v1/pipeline", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_pipeline_with_data(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/pipeline", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["stages"]["discovered"]) == 2

    def test_pipeline_filter_stage(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/pipeline?stage=discovered", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "discovered" in data["stages"]
        assert len(data["stages"]) == 1

    def test_pipeline_invalid_stage(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/pipeline?stage=invalid", headers=auth_headers)
        assert resp.status_code == 422


class TestNextActions:
    """Tests for GET /api/v1/pipeline/next."""

    def test_next_with_data(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/pipeline/next", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "next_up" in data
        assert "overdue" in data
        assert len(data["next_up"]) == 2


class TestPipelineStats:
    """Tests for GET /api/v1/pipeline/stats."""

    def test_stats(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/pipeline/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["by_stage"]["discovered"] == 2
