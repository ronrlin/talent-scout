"""Typed exception hierarchy for Talent Scout services.

Services raise these exceptions instead of printing to console.
Callers (CLI, API) catch and present them appropriately.
"""


class TalentScoutError(Exception):
    """Base exception for all Talent Scout service errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class JobNotFoundError(TalentScoutError):
    """Raised when a job ID cannot be found in the data store."""

    def __init__(self, job_id: str):
        super().__init__(f"Job not found: {job_id}", {"job_id": job_id})
        self.job_id = job_id


class CompanyNotFoundError(TalentScoutError):
    """Raised when a company cannot be found."""

    def __init__(self, company: str):
        super().__init__(f"Company not found: {company}", {"company": company})
        self.company = company


class ProfileNotFoundError(TalentScoutError):
    """Raised when no candidate profile exists."""

    def __init__(self):
        super().__init__("No candidate profile found. Run 'scout profile --refresh' to generate.")


class ResumeNotFoundError(TalentScoutError):
    """Raised when the base resume file cannot be loaded."""

    def __init__(self, path: str | None = None):
        msg = f"Base resume not found at {path}" if path else "Base resume not found"
        super().__init__(msg, {"path": path})


class AnalysisNotFoundError(TalentScoutError):
    """Raised when a job analysis is required but doesn't exist."""

    def __init__(self, job_id: str):
        super().__init__(
            f"No analysis found for job: {job_id}. Run 'scout analyze {job_id}' first.",
            {"job_id": job_id},
        )
        self.job_id = job_id


class GenerationFailedError(TalentScoutError):
    """Raised when AI generation (resume, cover letter, etc.) fails."""

    def __init__(self, operation: str, reason: str | None = None):
        msg = f"{operation} failed"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, {"operation": operation, "reason": reason})
        self.operation = operation
        self.reason = reason


class ValidationError(TalentScoutError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, {"field": field})
        self.field = field


class PipelineError(TalentScoutError):
    """Raised when a pipeline state transition fails."""

    def __init__(self, job_id: str, message: str):
        super().__init__(message, {"job_id": job_id})
        self.job_id = job_id
