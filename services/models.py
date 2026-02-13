"""Pydantic models for Talent Scout services.

Request and response models shared by CLI and API layers.
Services return these models; callers handle presentation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class PipelineStage(str, Enum):
    """Application pipeline stages."""

    DISCOVERED = "discovered"
    RESEARCHED = "researched"
    RESUME_READY = "resume_ready"
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    CLOSED = "closed"


class ClosedOutcome(str, Enum):
    """Outcomes for closed applications."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DECLINED = "declined"
    GHOSTED = "ghosted"
    WITHDRAWN = "withdrawn"


class OutputFormat(str, Enum):
    """Document output formats."""

    PDF = "pdf"
    DOCX = "docx"
    BOTH = "both"


class TaskStatus(str, Enum):
    """Async task statuses."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactType(str, Enum):
    """Types of generated artifacts."""

    ANALYSIS = "analysis"
    RESUME = "resume"
    COVER_LETTER = "cover_letter"
    INTERVIEW_PREP = "interview_prep"


# =============================================================================
# Request Models
# =============================================================================


class ScoutCompaniesRequest(BaseModel):
    """Request to scout companies for a location."""

    location: str = Field(description="Target location (e.g., 'Palo Alto, CA', 'remote', 'all')")
    count: int | None = Field(default=None, description="Number of companies to find")


class ResearchRequest(BaseModel):
    """Request to research a company."""

    company_name: str = Field(description="Name of the company to research")


class ImportUrlRequest(BaseModel):
    """Request to import a job from URL."""

    url: str = Field(description="URL of the job posting")


class ImportMarkdownRequest(BaseModel):
    """Request to import a job from markdown content."""

    content: str = Field(description="Markdown/text content of the job description")
    filename: str = Field(default="imported.md", description="Source filename for reference")


class GenerateRequest(BaseModel):
    """Request to generate a document (resume, cover letter, etc.)."""

    output_format: OutputFormat = Field(default=OutputFormat.PDF, description="Output format")


class ApplyRequest(BaseModel):
    """Request to record a job application."""

    via: str | None = Field(default=None, description="How you applied (e.g., 'company site')")
    notes: str | None = Field(default=None, description="Notes about the application")
    date: str | None = Field(default=None, description="Application date (ISO format)")


class StatusUpdateRequest(BaseModel):
    """Request to update pipeline stage."""

    stage: PipelineStage = Field(description="New pipeline stage")


class CloseRequest(BaseModel):
    """Request to close an application."""

    outcome: ClosedOutcome = Field(description="Outcome of the application")


class NoteRequest(BaseModel):
    """Request to add a note to a pipeline entry."""

    text: str = Field(description="Note text")


class DeleteJobRequest(BaseModel):
    """Request to delete a job."""

    reason: str | None = Field(default=None, description="Reason for deletion")


# =============================================================================
# Response Models
# =============================================================================


class JobSummary(BaseModel):
    """Compact job representation for lists."""

    id: str
    company: str
    title: str
    location: str
    match_score: int | None = None
    source: str | None = None
    stage: str | None = None


class JobDetail(BaseModel):
    """Full job representation."""

    id: str
    company: str
    title: str
    location: str
    location_type: str | None = None
    url: str | None = None
    description: str | None = None
    source: str | None = None
    match_score: int | None = None
    key_skills: list[str] = Field(default_factory=list)
    date_posted: str | None = None
    requirements_summary: str | None = None
    stage: str | None = None
    pipeline_entry: PipelineEntryResponse | None = None


class CompanySummary(BaseModel):
    """Company representation."""

    name: str
    website: str | None = None
    hq_location: str | None = None
    industry: str | None = None
    employee_count: str | None = None
    public: bool | None = None
    priority_score: int | None = None
    notes: str | None = None


class ProfileResponse(BaseModel):
    """Candidate profile response."""

    version: str | None = None
    generated_at: str | None = None
    identity: dict = Field(default_factory=dict)
    summary: str = ""
    experience: list[dict] = Field(default_factory=list)
    skills: dict = Field(default_factory=dict)
    education: list[dict] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)
    learned_preferences: dict = Field(default_factory=dict)


class HistoryEntry(BaseModel):
    """Pipeline history entry."""

    stage: str
    timestamp: str
    trigger: str


class PipelineEntryResponse(BaseModel):
    """Pipeline entry for a job."""

    job_id: str
    status: str
    created_at: str
    updated_at: str
    applied_at: str | None = None
    applied_via: str | None = None
    closed_at: str | None = None
    closed_outcome: str | None = None
    artifacts: dict = Field(default_factory=dict)
    notes: list[dict] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)


class ActionableItem(BaseModel):
    """An actionable pipeline item."""

    job_id: str
    status: str
    company: str = "?"
    title: str = "?"
    match_score: int = 0
    days_since_update: int | None = None
    updated_at: str | None = None


class ActionableResponse(BaseModel):
    """Grouped action items for the 'next' command."""

    overdue: list[ActionableItem] = Field(default_factory=list)
    ready_to_act: list[ActionableItem] = Field(default_factory=list)
    in_progress: list[ActionableItem] = Field(default_factory=list)
    next_up: list[ActionableItem] = Field(default_factory=list)


class PipelineOverview(BaseModel):
    """Kanban-style pipeline overview."""

    stages: dict[str, list[JobSummary]] = Field(default_factory=dict)
    total: int = 0
    summary: dict[str, int] = Field(default_factory=dict)


class PipelineStats(BaseModel):
    """Pipeline statistics."""

    total: int = 0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)


class GenerationResult(BaseModel):
    """Result from document generation."""

    job_id: str
    doc_type: str
    markdown_path: str | None = None
    artifacts: dict[str, str | None] = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Result from job analysis."""

    job_id: str
    analysis: dict = Field(default_factory=dict)
    analysis_path: str | None = None


class ResearchResult(BaseModel):
    """Result from company research."""

    company: dict = Field(default_factory=dict)
    jobs: list[dict] = Field(default_factory=list)
    jobs_added: int = 0
    careers_page: str | None = None
    search_notes: str | None = None


class LearningResult(BaseModel):
    """Result from learning analysis."""

    insights: str = ""
    positive_count: int = 0
    negative_count: int = 0
    targeting: dict = Field(default_factory=dict)
    scoring_adjustments: dict = Field(default_factory=dict)


class CorpusStats(BaseModel):
    """Corpus statistics."""

    version: str | None = None
    generated_at: str | None = None
    source_resumes: int = 0
    experience_entries: int = 0
    total_bullets: int = 0
    skills_indexed: int = 0
    themes_indexed: int = 0
    top_skills: list[dict] = Field(default_factory=list)
    top_themes: list[dict] = Field(default_factory=list)


# =============================================================================
# Async Task Models
# =============================================================================


class TaskCreatedResponse(BaseModel):
    """Response when an async task is created."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING


class TaskStatusResponse(BaseModel):
    """Response when polling task status."""

    task_id: str
    status: TaskStatus
    result: Any | None = None
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
