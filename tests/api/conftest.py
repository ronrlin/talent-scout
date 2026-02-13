"""Shared fixtures for API tests."""

import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.app import create_app
from api import dependencies as deps


@pytest.fixture
def api_key():
    """Fixed API key for testing."""
    return "test-api-key-12345"


@pytest.fixture
def app(test_config, data_store, pipeline_store, mock_claude_client, api_key):
    """Create a FastAPI test app with injected dependencies."""
    # Override dependency functions
    def _get_config():
        return test_config

    def _get_data_store():
        return data_store

    def _get_pipeline_store():
        return pipeline_store

    def _get_task_manager():
        from services.task_manager import TaskManager
        return TaskManager()

    def _service_kwargs():
        return {
            "config": test_config,
            "data_store": data_store,
            "pipeline": pipeline_store,
            "client": mock_claude_client,
        }

    def _get_job_service():
        from services import JobService
        return JobService(**_service_kwargs())

    def _get_profile_service():
        from services import ProfileService
        return ProfileService(**_service_kwargs())

    def _get_discovery_service():
        from services import DiscoveryService
        return DiscoveryService(**_service_kwargs())

    def _get_composer_service():
        from services import ComposerService
        return ComposerService(**_service_kwargs())

    def _get_corpus_service():
        from services import CorpusService
        return CorpusService(**_service_kwargs())

    application = create_app()

    # Override all dependency providers
    application.dependency_overrides[deps.get_config] = _get_config
    application.dependency_overrides[deps.get_data_store] = _get_data_store
    application.dependency_overrides[deps.get_pipeline_store] = _get_pipeline_store
    application.dependency_overrides[deps.get_task_manager] = _get_task_manager
    application.dependency_overrides[deps.get_job_service] = _get_job_service
    application.dependency_overrides[deps.get_profile_service] = _get_profile_service
    application.dependency_overrides[deps.get_discovery_service] = _get_discovery_service
    application.dependency_overrides[deps.get_composer_service] = _get_composer_service
    application.dependency_overrides[deps.get_corpus_service] = _get_corpus_service

    # Override auth to accept test key
    from api.auth import verify_api_key

    async def _verify_test_key(key=None):
        # Accept the test key or no key check
        return api_key

    application.dependency_overrides[verify_api_key] = _verify_test_key

    return application


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers(api_key):
    """Headers with API key."""
    return {"X-API-Key": api_key}


@pytest.fixture
def populated_api_store(data_store, pipeline_store, sample_job, sample_job_2, tmp_data_dir):
    """Populate stores with sample data (same as service tests)."""
    jobs_data = {"jobs": [sample_job], "updated_at": "2026-01-15T00:00:00Z"}
    jobs_file = tmp_data_dir / "jobs-palo-alto-ca.json"
    with open(jobs_file, "w") as f:
        json.dump(jobs_data, f)

    remote_data = {"jobs": [sample_job_2], "updated_at": "2026-01-20T00:00:00Z"}
    remote_file = tmp_data_dir / "jobs-remote.json"
    with open(remote_file, "w") as f:
        json.dump(remote_data, f)

    data_store._job_index = None

    pipeline_store.create(sample_job["id"], "auto:test")
    pipeline_store.create(sample_job_2["id"], "auto:test")

    return data_store, pipeline_store
