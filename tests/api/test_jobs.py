"""Tests for Jobs API endpoints."""

import pytest


class TestGetJobs:
    """Tests for GET /api/v1/jobs."""

    def test_get_jobs_empty(self, client, auth_headers):
        resp = client.get("/api/v1/jobs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_jobs(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/jobs", headers=auth_headers)
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 2
        # Sorted by match_score desc
        assert jobs[0]["match_score"] >= jobs[1]["match_score"]

    def test_get_jobs_filter_company(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/jobs?company=TestCo", headers=auth_headers)
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 1
        assert jobs[0]["company"] == "TestCo"

    def test_get_jobs_filter_stage(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/jobs?stage=discovered", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_jobs_invalid_stage(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/jobs?stage=invalid", headers=auth_headers)
        assert resp.status_code == 422


class TestGetJob:
    """Tests for GET /api/v1/jobs/{job_id}."""

    def test_get_existing_job(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/jobs/JOB-TESTCO-ABC123", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "JOB-TESTCO-ABC123"
        assert data["company"] == "TestCo"
        assert data["title"] == "Engineering Manager"
        assert data["stage"] == "discovered"

    def test_get_nonexistent_job(self, client, auth_headers, populated_api_store):
        resp = client.get("/api/v1/jobs/JOB-NONEXISTENT", headers=auth_headers)
        assert resp.status_code == 404


class TestDeleteJob:
    """Tests for DELETE /api/v1/jobs/{job_id}."""

    def test_delete_job(self, client, auth_headers, populated_api_store):
        resp = client.request(
            "DELETE",
            "/api/v1/jobs/JOB-TESTCO-ABC123",
            headers=auth_headers,
            json={"reason": "Not interested"},
        )
        assert resp.status_code == 200
        assert resp.json()["company"] == "TestCo"

        # Verify job is gone
        resp2 = client.get("/api/v1/jobs/JOB-TESTCO-ABC123", headers=auth_headers)
        assert resp2.status_code == 404

    def test_delete_nonexistent(self, client, auth_headers, populated_api_store):
        resp = client.request(
            "DELETE",
            "/api/v1/jobs/JOB-NONEXISTENT",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestApply:
    """Tests for POST /api/v1/jobs/{job_id}/apply."""

    def test_apply_basic(self, client, auth_headers, populated_api_store):
        resp = client.post(
            "/api/v1/jobs/JOB-TESTCO-ABC123/apply",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "applied"

    def test_apply_with_details(self, client, auth_headers, populated_api_store):
        resp = client.post(
            "/api/v1/jobs/JOB-TESTCO-ABC123/apply",
            headers=auth_headers,
            json={"via": "company site", "notes": "Applied online"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "applied"
        assert data["applied_via"] == "company site"

    def test_apply_nonexistent(self, client, auth_headers, populated_api_store):
        resp = client.post(
            "/api/v1/jobs/JOB-NONEXISTENT/apply",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestSetStatus:
    """Tests for PUT /api/v1/jobs/{job_id}/status."""

    def test_set_valid_status(self, client, auth_headers, populated_api_store):
        resp = client.put(
            "/api/v1/jobs/JOB-TESTCO-ABC123/status",
            headers=auth_headers,
            json={"stage": "researched"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "researched"

    def test_set_invalid_status(self, client, auth_headers, populated_api_store):
        resp = client.put(
            "/api/v1/jobs/JOB-TESTCO-ABC123/status",
            headers=auth_headers,
            json={"stage": "invalid_stage"},
        )
        assert resp.status_code == 422


class TestClose:
    """Tests for POST /api/v1/jobs/{job_id}/close."""

    def test_close_job(self, client, auth_headers, populated_api_store):
        resp = client.post(
            "/api/v1/jobs/JOB-TESTCO-ABC123/close",
            headers=auth_headers,
            json={"outcome": "rejected"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["closed_outcome"] == "rejected"

    def test_close_invalid_outcome(self, client, auth_headers, populated_api_store):
        resp = client.post(
            "/api/v1/jobs/JOB-TESTCO-ABC123/close",
            headers=auth_headers,
            json={"outcome": "invalid"},
        )
        assert resp.status_code == 422


class TestHistory:
    """Tests for GET /api/v1/jobs/{job_id}/history."""

    def test_get_history(self, client, auth_headers, populated_api_store):
        resp = client.get(
            "/api/v1/jobs/JOB-TESTCO-ABC123/history",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 1
        assert history[0]["stage"] == "discovered"

    def test_get_history_nonexistent(self, client, auth_headers, populated_api_store):
        resp = client.get(
            "/api/v1/jobs/JOB-NONEXISTENT/history",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestNotes:
    """Tests for POST /api/v1/jobs/{job_id}/notes."""

    def test_add_note(self, client, auth_headers, populated_api_store):
        resp = client.post(
            "/api/v1/jobs/JOB-TESTCO-ABC123/notes",
            headers=auth_headers,
            json={"text": "Interesting company"},
        )
        assert resp.status_code == 201
        assert resp.json()["ok"] is True
