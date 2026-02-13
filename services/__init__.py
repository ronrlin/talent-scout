"""Talent Scout services - framework-agnostic business logic layer.

Services wrap agents/skills and return structured data (Pydantic models).
No Rich imports, no console output. Callers handle presentation.
"""

from .base_service import BaseService
from .exceptions import (
    TalentScoutError,
    JobNotFoundError,
    CompanyNotFoundError,
    GenerationFailedError,
    ValidationError,
    ProfileNotFoundError,
    ResumeNotFoundError,
    AnalysisNotFoundError,
    PipelineError,
)
from .job_service import JobService
from .profile_service import ProfileService
from .discovery_service import DiscoveryService
from .composer_service import ComposerService
from .corpus_service import CorpusService

__all__ = [
    # Base
    "BaseService",
    # Services
    "JobService",
    "ProfileService",
    "DiscoveryService",
    "ComposerService",
    "CorpusService",
    # Exceptions
    "TalentScoutError",
    "JobNotFoundError",
    "CompanyNotFoundError",
    "GenerationFailedError",
    "ValidationError",
    "ProfileNotFoundError",
    "ResumeNotFoundError",
    "AnalysisNotFoundError",
    "PipelineError",
]
