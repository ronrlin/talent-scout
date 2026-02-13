"""Tests for JobService."""

import json
import pytest
from unittest.mock import MagicMock

from services.job_service import JobService
from services.exceptions import JobNotFoundError, ValidationError, PipelineError
from services.models import JobSummary, JobDetail, PipelineEntryResponse, ActionableResponse


@pytest.fixture
def job_service(test_config, data_store, pipeline_store, mock_claude_client):
    """Create a JobService with test dependencies."""
    svc = JobService(
        config=test_config,
        data_store=data_store,
        pipeline=pipeline_store,
        client=mock_claude_client,
    )
    return svc


@pytest.fixture
def populated_store(data_store, pipeline_store, sample_job, sample_job_2, tmp_data_dir):
    """Populate stores with sample data."""
    # Write jobs file
    jobs_data = {"jobs": [sample_job], "updated_at": "2026-01-15T00:00:00Z"}
    jobs_file = tmp_data_dir / "jobs-palo-alto-ca.json"
    with open(jobs_file, "w") as f:
        json.dump(jobs_data, f)

    remote_data = {"jobs": [sample_job_2], "updated_at": "2026-01-20T00:00:00Z"}
    remote_file = tmp_data_dir / "jobs-remote.json"
    with open(remote_file, "w") as f:
        json.dump(remote_data, f)

    # Reset index
    data_store._job_index = None

    # Create pipeline entries
    pipeline_store.create(sample_job["id"], "auto:test")
    pipeline_store.create(sample_job_2["id"], "auto:test")

    return data_store, pipeline_store


class TestGetJobs:
    """Tests for get_jobs()."""

    def test_get_all_jobs(self, job_service, populated_store):
        jobs = job_service.get_jobs()
        assert len(jobs) == 2
        assert all(isinstance(j, JobSummary) for j in jobs)

    def test_get_jobs_sorted_by_score(self, job_service, populated_store):
        jobs = job_service.get_jobs()
        assert jobs[0].match_score >= jobs[1].match_score

    def test_get_jobs_with_company_filter(self, job_service, populated_store):
        jobs = job_service.get_jobs(company="TestCo")
        assert len(jobs) == 1
        assert jobs[0].company == "TestCo"

    def test_get_jobs_with_stage_filter(self, job_service, populated_store):
        jobs = job_service.get_jobs(stage="discovered")
        assert len(jobs) == 2

    def test_get_jobs_invalid_stage(self, job_service, populated_store):
        with pytest.raises(ValidationError):
            job_service.get_jobs(stage="invalid_stage")

    def test_get_jobs_empty(self, job_service):
        jobs = job_service.get_jobs()
        assert jobs == []


class TestGetJob:
    """Tests for get_job()."""

    def test_get_existing_job(self, job_service, populated_store):
        detail = job_service.get_job("JOB-TESTCO-ABC123")
        assert isinstance(detail, JobDetail)
        assert detail.company == "TestCo"
        assert detail.title == "Engineering Manager"
        assert detail.stage == "discovered"
        assert detail.pipeline_entry is not None

    def test_get_nonexistent_job(self, job_service, populated_store):
        with pytest.raises(JobNotFoundError):
            job_service.get_job("JOB-NONEXISTENT")


class TestDeleteJob:
    """Tests for delete_job()."""

    def test_delete_existing_job(self, job_service, populated_store, tmp_data_dir):
        result = job_service.delete_job("JOB-TESTCO-ABC123", reason="Not interested")
        assert isinstance(result, JobDetail)
        assert result.company == "TestCo"

        # Verify job is gone
        with pytest.raises(JobNotFoundError):
            job_service.get_job("JOB-TESTCO-ABC123")

        # Verify deleted job is recorded
        deleted = job_service.data_store.get_deleted_jobs()
        assert len(deleted) == 1
        assert deleted[0]["deletion_reason"] == "Not interested"

    def test_delete_nonexistent_job(self, job_service, populated_store):
        with pytest.raises(JobNotFoundError):
            job_service.delete_job("JOB-NONEXISTENT")


class TestApply:
    """Tests for apply()."""

    def test_apply_basic(self, job_service, populated_store):
        entry = job_service.apply("JOB-TESTCO-ABC123")
        assert isinstance(entry, PipelineEntryResponse)
        assert entry.status == "applied"

    def test_apply_with_details(self, job_service, populated_store):
        entry = job_service.apply(
            "JOB-TESTCO-ABC123",
            via="company site",
            notes="Applied through careers page",
        )
        assert entry.status == "applied"
        assert entry.applied_via == "company site"
        assert len(entry.notes) == 1
        assert entry.notes[0]["text"] == "Applied through careers page"

    def test_apply_nonexistent_job(self, job_service, populated_store):
        with pytest.raises(JobNotFoundError):
            job_service.apply("JOB-NONEXISTENT")


class TestSetStatus:
    """Tests for set_status()."""

    def test_set_valid_status(self, job_service, populated_store):
        entry = job_service.set_status("JOB-TESTCO-ABC123", "researched")
        assert entry.status == "researched"

    def test_set_invalid_status(self, job_service, populated_store):
        with pytest.raises(ValidationError):
            job_service.set_status("JOB-TESTCO-ABC123", "invalid_stage")

    def test_set_status_nonexistent_job(self, job_service, populated_store):
        with pytest.raises(JobNotFoundError):
            job_service.set_status("JOB-NONEXISTENT", "researched")


class TestClose:
    """Tests for close()."""

    def test_close_with_outcome(self, job_service, populated_store):
        entry = job_service.close("JOB-TESTCO-ABC123", "rejected")
        assert entry.status == "closed"
        assert entry.closed_outcome == "rejected"
        assert entry.closed_at is not None

    def test_close_invalid_outcome(self, job_service, populated_store):
        with pytest.raises(ValidationError):
            job_service.close("JOB-TESTCO-ABC123", "invalid_outcome")


class TestHistory:
    """Tests for get_history()."""

    def test_get_history(self, job_service, populated_store):
        history = job_service.get_history("JOB-TESTCO-ABC123")
        assert len(history) == 1
        assert history[0].stage == "discovered"
        assert history[0].trigger == "auto:test"

    def test_get_history_after_transitions(self, job_service, populated_store):
        job_service.set_status("JOB-TESTCO-ABC123", "researched")
        job_service.apply("JOB-TESTCO-ABC123", via="LinkedIn")

        history = job_service.get_history("JOB-TESTCO-ABC123")
        assert len(history) == 3
        stages = [h.stage for h in history]
        assert stages == ["discovered", "researched", "applied"]


class TestAddNote:
    """Tests for add_note()."""

    def test_add_note(self, job_service, populated_store):
        result = job_service.add_note("JOB-TESTCO-ABC123", "Interesting company")
        assert result is True

    def test_add_note_nonexistent_job(self, job_service, populated_store):
        with pytest.raises(JobNotFoundError):
            job_service.add_note("JOB-NONEXISTENT", "Note")


class TestActionable:
    """Tests for get_actionable()."""

    def test_get_actionable_with_next_up(self, job_service, populated_store):
        result = job_service.get_actionable()
        assert isinstance(result, ActionableResponse)
        assert len(result.next_up) == 2  # Both in discovered state


class TestPipelineOverview:
    """Tests for get_pipeline_overview()."""

    def test_overview_shows_all_stages(self, job_service, populated_store):
        overview = job_service.get_pipeline_overview()
        assert overview.total == 2
        assert len(overview.stages["discovered"]) == 2

    def test_overview_filter_stage(self, job_service, populated_store):
        overview = job_service.get_pipeline_overview(filter_stage="discovered")
        assert "discovered" in overview.stages
        assert len(overview.stages) == 1

    def test_overview_invalid_stage(self, job_service, populated_store):
        with pytest.raises(ValidationError):
            job_service.get_pipeline_overview(filter_stage="invalid")


class TestPipelineStats:
    """Tests for get_pipeline_stats()."""

    def test_stats(self, job_service, populated_store):
        stats = job_service.get_pipeline_stats()
        assert stats.total == 2
        assert stats.by_stage["discovered"] == 2
