"""Job service - CRUD operations for jobs and pipeline management.

Pure data operations wrapping DataStore + PipelineStore. No Claude API calls.
"""

import logging
from pathlib import Path

from config_loader import (
    get_all_location_slugs,
    get_location_slug,
    get_locations,
    is_remote_enabled,
)
from data_store import DataStore
from pipeline_store import PipelineStore, PIPELINE_STAGES, CLOSED_OUTCOMES

from .base_service import BaseService
from .exceptions import (
    JobNotFoundError,
    ValidationError,
    PipelineError,
)
from .models import (
    JobSummary,
    JobDetail,
    PipelineEntryResponse,
    HistoryEntry,
    ActionableItem,
    ActionableResponse,
    PipelineOverview,
    PipelineStats,
)

logger = logging.getLogger(__name__)


class JobService(BaseService):
    """Service for job CRUD and pipeline management.

    Wraps DataStore and PipelineStore with typed exceptions and
    Pydantic response models. No AI operations.
    """

    def get_jobs(
        self,
        location: str | None = None,
        company: str | None = None,
        source: str | None = None,
        stage: str | None = None,
    ) -> list[JobSummary]:
        """Get jobs with optional filtering.

        Args:
            location: Filter by location (e.g., "Palo Alto, CA", "remote", "all").
            company: Filter by company name (case-insensitive substring).
            source: Filter by source ("imported" or "discovered").
            stage: Filter by pipeline stage.

        Returns:
            List of JobSummary models sorted by match_score descending.
        """
        location_slug = self._resolve_location_slug(location)

        if stage and stage not in PIPELINE_STAGES:
            raise ValidationError(f"Invalid stage: {stage}", field="stage")

        all_jobs = self.data_store.get_jobs(
            location_slug=location_slug,
            company=company,
            source=source,
        )

        # Build pipeline lookup for stage column
        pipeline_lookup = {
            entry["job_id"]: entry["status"]
            for entry in self.pipeline.get_all()
        }

        # Filter by stage if requested
        if stage:
            stage_job_ids = {entry["job_id"] for entry in self.pipeline.get_by_status(stage)}
            all_jobs = [j for j in all_jobs if j.get("id") in stage_job_ids]

        # Sort by match score
        all_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        return [
            JobSummary(
                id=job.get("id", "?"),
                company=job.get("company", "?"),
                title=job.get("title", "?"),
                location=job.get("location", "?"),
                match_score=job.get("match_score"),
                source=job.get("source"),
                stage=pipeline_lookup.get(job.get("id")),
            )
            for job in all_jobs
        ]

    def get_job(self, job_id: str) -> JobDetail:
        """Get full job details.

        Args:
            job_id: The job ID.

        Returns:
            JobDetail model.

        Raises:
            JobNotFoundError: If job not found.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        # Get pipeline entry
        entry = self.pipeline.get(job_id)
        pipeline_entry = self._to_pipeline_response(entry) if entry else None

        return JobDetail(
            id=job.get("id", ""),
            company=job.get("company", ""),
            title=job.get("title", ""),
            location=job.get("location", ""),
            location_type=job.get("location_type"),
            url=job.get("url"),
            description=job.get("description"),
            source=job.get("source"),
            match_score=job.get("match_score"),
            key_skills=job.get("key_skills", []),
            date_posted=job.get("date_posted"),
            requirements_summary=job.get("requirements_summary"),
            stage=entry["status"] if entry else None,
            pipeline_entry=pipeline_entry,
        )

    def delete_job(self, job_id: str, reason: str | None = None) -> JobDetail:
        """Delete a job and record it for negative learning.

        Args:
            job_id: The job ID to delete.
            reason: Optional reason for deletion.

        Returns:
            The deleted job as JobDetail.

        Raises:
            JobNotFoundError: If job not found.
        """
        job = self.data_store.delete_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        # Record for negative learning
        self.data_store.record_deleted_job(job, reason)

        return JobDetail(
            id=job.get("id", ""),
            company=job.get("company", ""),
            title=job.get("title", ""),
            location=job.get("location", ""),
            match_score=job.get("match_score"),
        )

    def apply(
        self,
        job_id: str,
        via: str | None = None,
        notes: str | None = None,
        date: str | None = None,
    ) -> PipelineEntryResponse:
        """Record a job application.

        Args:
            job_id: The job ID.
            via: How you applied.
            notes: Notes about the application.
            date: Application date (ISO format).

        Returns:
            Updated pipeline entry.

        Raises:
            JobNotFoundError: If job not found.
            PipelineError: If pipeline update fails.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        # Ensure pipeline entry exists
        self.pipeline.create(job_id, "auto:apply_init")

        # Build metadata
        meta = {}
        if via:
            meta["applied_via"] = via
        if date:
            meta["applied_at"] = date

        result = self.pipeline.set_status(job_id, "applied", "manual:apply", **meta)
        if not result:
            raise PipelineError(job_id, "Failed to update pipeline")

        if notes:
            self.pipeline.add_note(job_id, notes)

        entry = self.pipeline.get(job_id)
        return self._to_pipeline_response(entry)

    def set_status(self, job_id: str, stage: str) -> PipelineEntryResponse:
        """Manually set pipeline stage.

        Args:
            job_id: The job ID.
            stage: Target stage.

        Returns:
            Updated pipeline entry.

        Raises:
            JobNotFoundError: If job not found.
            ValidationError: If stage is invalid.
            PipelineError: If update fails.
        """
        if stage not in PIPELINE_STAGES:
            raise ValidationError(
                f"Invalid stage: {stage}. Valid: {', '.join(PIPELINE_STAGES)}",
                field="stage",
            )

        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        self.pipeline.create(job_id, "auto:status_init")

        result = self.pipeline.set_status(job_id, stage, "manual:status")
        if not result:
            raise PipelineError(job_id, f"Failed to set status to {stage}")

        entry = self.pipeline.get(job_id)
        return self._to_pipeline_response(entry)

    def close(self, job_id: str, outcome: str) -> PipelineEntryResponse:
        """Close an application with an outcome.

        Args:
            job_id: The job ID.
            outcome: Closed outcome.

        Returns:
            Updated pipeline entry.

        Raises:
            JobNotFoundError: If job not found.
            ValidationError: If outcome is invalid.
            PipelineError: If close fails.
        """
        if outcome not in CLOSED_OUTCOMES:
            raise ValidationError(
                f"Invalid outcome: {outcome}. Valid: {', '.join(CLOSED_OUTCOMES)}",
                field="outcome",
            )

        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        self.pipeline.create(job_id, "auto:close_init")

        result = self.pipeline.close(job_id, outcome, "manual:status")
        if not result:
            raise PipelineError(job_id, f"Failed to close with outcome {outcome}")

        entry = self.pipeline.get(job_id)
        return self._to_pipeline_response(entry)

    def get_history(self, job_id: str) -> list[HistoryEntry]:
        """Get pipeline history for a job.

        Args:
            job_id: The job ID.

        Returns:
            List of history entries.

        Raises:
            JobNotFoundError: If job not found.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        raw_history = self.pipeline.get_history(job_id)
        return [
            HistoryEntry(
                stage=h.get("stage", "?"),
                timestamp=h.get("timestamp", "?"),
                trigger=h.get("trigger", "?"),
            )
            for h in raw_history
        ]

    def add_note(self, job_id: str, text: str) -> bool:
        """Add a note to a pipeline entry.

        Args:
            job_id: The job ID.
            text: Note text.

        Returns:
            True if note was added.

        Raises:
            JobNotFoundError: If job not found.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        return self.pipeline.add_note(job_id, text)

    def get_actionable(self) -> ActionableResponse:
        """Get grouped action items for the 'next' dashboard.

        Returns:
            ActionableResponse with overdue, ready_to_act, in_progress, next_up.
        """
        follow_up_days = (
            self.config.get("preferences", {})
            .get("pipeline", {})
            .get("follow_up_days", 7)
        )

        all_jobs = self.data_store.get_jobs()
        raw = self.pipeline.get_actionable(follow_up_days=follow_up_days, jobs=all_jobs)

        def to_items(items: list[dict]) -> list[ActionableItem]:
            return [
                ActionableItem(
                    job_id=item["job_id"],
                    status=item["status"],
                    company=item.get("company", "?"),
                    title=item.get("title", "?"),
                    match_score=item.get("match_score", 0),
                    days_since_update=item.get("days_since_update"),
                    updated_at=item.get("updated_at"),
                )
                for item in items
            ]

        return ActionableResponse(
            overdue=to_items(raw["overdue"]),
            ready_to_act=to_items(raw["ready_to_act"]),
            in_progress=to_items(raw["in_progress"]),
            next_up=to_items(raw["next_up"]),
        )

    def get_pipeline_overview(self, filter_stage: str | None = None) -> PipelineOverview:
        """Get kanban-style pipeline overview.

        Args:
            filter_stage: Optional stage to filter to.

        Returns:
            PipelineOverview with jobs grouped by stage.
        """
        if filter_stage and filter_stage not in PIPELINE_STAGES:
            raise ValidationError(f"Invalid stage: {filter_stage}", field="stage")

        all_entries = self.pipeline.get_all()

        # Build job lookup
        job_lookup = {}
        for j in self.data_store.get_jobs():
            job_lookup[j["id"]] = j

        # Group by stage
        by_stage: dict[str, list[JobSummary]] = {stage: [] for stage in PIPELINE_STAGES}

        for entry in all_entries:
            s = entry["status"]
            if s not in by_stage:
                continue

            job_id = entry["job_id"]
            job = job_lookup.get(job_id, {})

            by_stage[s].append(
                JobSummary(
                    id=job_id,
                    company=job.get("company", "?"),
                    title=job.get("title", "?"),
                    location=job.get("location", "?"),
                    match_score=job.get("match_score"),
                    stage=s,
                )
            )

        # Filter if requested
        if filter_stage:
            by_stage = {filter_stage: by_stage.get(filter_stage, [])}

        # Build summary counts
        summary = {
            stage: len(jobs) for stage, jobs in by_stage.items() if jobs
        }

        return PipelineOverview(
            stages=by_stage,
            total=len(all_entries),
            summary=summary,
        )

    def get_pipeline_stats(self) -> PipelineStats:
        """Get pipeline conversion stats.

        Returns:
            PipelineStats model.
        """
        raw = self.pipeline.get_stats()
        return PipelineStats(
            total=raw["total"],
            by_stage=raw["by_stage"],
            by_outcome=raw["by_outcome"],
        )

    def get_pipeline_entry(self, job_id: str) -> PipelineEntryResponse | None:
        """Get pipeline entry for a job.

        Args:
            job_id: The job ID.

        Returns:
            Pipeline entry or None.
        """
        entry = self.pipeline.get(job_id)
        if not entry:
            return None
        return self._to_pipeline_response(entry)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _resolve_location_slug(self, location: str | None) -> str | None:
        """Resolve a location string to a location slug.

        Returns None for "all" or None (meaning get everything).
        """
        if not location or location.lower() == "all":
            return None

        if location.lower() == "remote":
            return "remote"

        slug = get_location_slug(location)
        all_slugs = get_all_location_slugs(self.config)

        if slug in all_slugs:
            return slug

        # Try partial match on configured locations
        configured_locations = get_locations(self.config)
        matched = [loc for loc in configured_locations if location.lower() in loc.lower()]
        if matched:
            return get_location_slug(matched[0])

        return None

    def _to_pipeline_response(self, entry: dict) -> PipelineEntryResponse:
        """Convert a raw pipeline entry dict to a PipelineEntryResponse."""
        return PipelineEntryResponse(
            job_id=entry["job_id"],
            status=entry["status"],
            created_at=entry["created_at"],
            updated_at=entry["updated_at"],
            applied_at=entry.get("applied_at"),
            applied_via=entry.get("applied_via"),
            closed_at=entry.get("closed_at"),
            closed_outcome=entry.get("closed_outcome"),
            artifacts=entry.get("artifacts", {}),
            notes=entry.get("notes", []),
            history=[
                HistoryEntry(
                    stage=h.get("stage", "?"),
                    timestamp=h.get("timestamp", "?"),
                    trigger=h.get("trigger", "?"),
                )
                for h in entry.get("history", [])
            ],
        )
