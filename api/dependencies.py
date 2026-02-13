"""FastAPI dependency injection providers.

Singleton instances shared across all requests.
"""

from functools import lru_cache

from config_loader import load_config
from data_store import DataStore
from pipeline_store import PipelineStore
from services import (
    JobService,
    ProfileService,
    DiscoveryService,
    ComposerService,
    CorpusService,
)
from services.task_manager import TaskManager


@lru_cache()
def get_config() -> dict:
    """Cached config singleton."""
    return load_config()


# Module-level singletons
_data_store: DataStore | None = None
_pipeline_store: PipelineStore | None = None
_task_manager: TaskManager | None = None


def get_data_store() -> DataStore:
    """DataStore singleton."""
    global _data_store
    if _data_store is None:
        _data_store = DataStore(get_config())
    return _data_store


def get_pipeline_store() -> PipelineStore:
    """PipelineStore singleton."""
    global _pipeline_store
    if _pipeline_store is None:
        _pipeline_store = PipelineStore(get_config())
    return _pipeline_store


def get_task_manager() -> TaskManager:
    """TaskManager singleton."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def _service_kwargs() -> dict:
    """Common kwargs for all services."""
    return {
        "config": get_config(),
        "data_store": get_data_store(),
        "pipeline": get_pipeline_store(),
    }


def get_job_service() -> JobService:
    return JobService(**_service_kwargs())


def get_profile_service() -> ProfileService:
    return ProfileService(**_service_kwargs())


def get_discovery_service() -> DiscoveryService:
    return DiscoveryService(**_service_kwargs())


def get_composer_service() -> ComposerService:
    return ComposerService(**_service_kwargs())


def get_corpus_service() -> CorpusService:
    return CorpusService(**_service_kwargs())


def reset_singletons() -> None:
    """Reset all singletons (for testing)."""
    global _data_store, _pipeline_store, _task_manager
    _data_store = None
    _pipeline_store = None
    _task_manager = None
    get_config.cache_clear()
