"""Centralized data access layer for jobs, companies, and research."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config_loader import (
    get_all_location_slugs,
    get_location_slug,
    is_remote_enabled,
    classify_job_location,
)


class DataStore:
    """Centralized data access for jobs, companies, research, and deleted jobs."""

    def __init__(self, config: dict):
        """Initialize the data store.

        Args:
            config: Configuration dictionary with location and preference settings.
        """
        self.config = config
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)

        # Lazy-loaded index for fast job lookups
        self._job_index: dict[str, str] | None = None  # job_id -> location_slug

    # =========================================================================
    # Jobs
    # =========================================================================

    def get_job(self, job_id: str) -> dict | None:
        """Get a job by ID.

        Args:
            job_id: The job ID to look up.

        Returns:
            Job dictionary with _location_slug added, or None if not found.
        """
        self._ensure_index()

        location_slug = self._job_index.get(job_id)
        if not location_slug:
            return None

        jobs_file = self.data_dir / f"jobs-{location_slug}.json"
        if not jobs_file.exists():
            return None

        with open(jobs_file) as f:
            data = json.load(f)

        for job in data.get("jobs", []):
            if job.get("id") == job_id:
                job["_location_slug"] = location_slug
                return job

        return None

    def save_job(self, job: dict, location_slug: str | None = None) -> bool:
        """Save a job to the appropriate location file.

        Args:
            job: Job dictionary. Must have 'id' field.
            location_slug: Optional location slug. If not provided, will be
                          classified based on job['location'].

        Returns:
            True if job was added (new), False if it was a duplicate.
        """
        if not job.get("id"):
            raise ValueError("Job must have an 'id' field")

        # Determine location slug
        if not location_slug:
            job_location = job.get("location", "")
            location_slug = classify_job_location(job_location, self.config)

        # Validate location slug
        all_slugs = get_all_location_slugs(self.config)
        if location_slug not in all_slugs:
            if is_remote_enabled(self.config) and "remote" in all_slugs:
                location_slug = "remote"
            elif all_slugs:
                location_slug = all_slugs[0]
            else:
                return False

        # Ensure location_type is set on the job
        job["location_type"] = location_slug

        jobs_file = self.data_dir / f"jobs-{location_slug}.json"

        # Load existing jobs
        existing_data = {"jobs": []}
        if jobs_file.exists():
            with open(jobs_file) as f:
                existing_data = json.load(f)

        existing_jobs = existing_data.get("jobs", [])

        # Check for duplicates
        if self._is_duplicate(job, existing_jobs):
            return False

        # Add the job
        existing_jobs.append(job)
        existing_data["jobs"] = existing_jobs
        existing_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(jobs_file, "w") as f:
            json.dump(existing_data, f, indent=2)

        # Update index
        if self._job_index is not None:
            self._job_index[job["id"]] = location_slug

        return True

    def save_jobs(self, jobs: list[dict], company_name: str | None = None) -> int:
        """Save multiple jobs, routing each to the appropriate location file.

        Args:
            jobs: List of job dictionaries.
            company_name: Optional company name to set on all jobs.

        Returns:
            Number of jobs actually added (excluding duplicates).
        """
        if not jobs:
            return 0

        added_count = 0
        for job in jobs:
            if company_name and not job.get("company"):
                job["company"] = company_name
            if self.save_job(job):
                added_count += 1

        return added_count

    def delete_job(self, job_id: str) -> dict | None:
        """Remove a job by ID and return it.

        Args:
            job_id: The job ID to remove.

        Returns:
            The removed job dictionary, or None if not found.
        """
        self._ensure_index()

        location_slug = self._job_index.get(job_id)
        if not location_slug:
            return None

        jobs_file = self.data_dir / f"jobs-{location_slug}.json"
        if not jobs_file.exists():
            return None

        with open(jobs_file) as f:
            data = json.load(f)

        jobs = data.get("jobs", [])
        for i, job in enumerate(jobs):
            if job.get("id") == job_id:
                removed_job = jobs.pop(i)
                data["jobs"] = jobs
                data["updated_at"] = datetime.now(timezone.utc).isoformat()

                with open(jobs_file, "w") as f:
                    json.dump(data, f, indent=2)

                # Update index
                if self._job_index is not None:
                    del self._job_index[job_id]

                return removed_job

        return None

    def get_jobs(
        self,
        location_slug: str | None = None,
        company: str | None = None,
        source: str | None = None,
    ) -> list[dict]:
        """Get jobs with optional filtering.

        Args:
            location_slug: Filter by location slug.
            company: Filter by company name (case-insensitive substring match).
            source: Filter by source ("imported" or "discovered").

        Returns:
            List of matching jobs.
        """
        all_jobs = []

        # Determine which location files to read
        if location_slug:
            slugs = [location_slug]
        else:
            slugs = get_all_location_slugs(self.config)

        for slug in slugs:
            jobs_file = self.data_dir / f"jobs-{slug}.json"
            if not jobs_file.exists():
                continue

            with open(jobs_file) as f:
                data = json.load(f)

            for job in data.get("jobs", []):
                job["_location_slug"] = slug
                all_jobs.append(job)

        # Apply filters
        if company:
            company_lower = company.lower()
            all_jobs = [j for j in all_jobs if company_lower in j.get("company", "").lower()]

        if source:
            all_jobs = [j for j in all_jobs if j.get("source") == source]

        return all_jobs

    def job_exists(
        self,
        job_id: str | None = None,
        company: str | None = None,
        title: str | None = None,
    ) -> bool:
        """Check if a job exists.

        Args:
            job_id: Check by exact job ID.
            company: Check by company + title combination.
            title: Check by company + title combination.

        Returns:
            True if a matching job exists.
        """
        if job_id:
            self._ensure_index()
            return job_id in self._job_index

        if company and title:
            # Check all location files
            for slug in get_all_location_slugs(self.config):
                jobs_file = self.data_dir / f"jobs-{slug}.json"
                if not jobs_file.exists():
                    continue

                with open(jobs_file) as f:
                    data = json.load(f)

                for job in data.get("jobs", []):
                    if (
                        job.get("company", "").lower() == company.lower()
                        and job.get("title", "").lower() == title.lower()
                    ):
                        return True

        return False

    # =========================================================================
    # Companies
    # =========================================================================

    def get_companies(self, location_slug: str) -> list[dict]:
        """Get companies for a location.

        Args:
            location_slug: The location slug (e.g., "palo-alto-ca").

        Returns:
            List of company dictionaries.
        """
        companies_file = self.data_dir / f"companies-{location_slug}.json"
        if not companies_file.exists():
            return []

        with open(companies_file) as f:
            data = json.load(f)

        return data.get("companies", [])

    def save_companies(self, companies: list[dict], location_slug: str, location: str) -> None:
        """Save companies for a location.

        Args:
            companies: List of company dictionaries.
            location_slug: The location slug.
            location: The full location string (e.g., "Palo Alto, CA").
        """
        from config_loader import get_location_description

        output_path = self.data_dir / f"companies-{location_slug}.json"

        data = {
            "location": location,
            "location_slug": location_slug,
            "location_description": get_location_description(location),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(companies),
            "companies": companies,
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # Research
    # =========================================================================

    def get_research(self, company_slug: str) -> dict | None:
        """Get research data for a company.

        Args:
            company_slug: Slugified company name.

        Returns:
            Research data dictionary or None if not found.
        """
        research_dir = self.data_dir / "research"
        research_file = research_dir / f"{company_slug}.json"

        if not research_file.exists():
            return None

        with open(research_file) as f:
            return json.load(f)

    def save_research(self, company_slug: str, research: dict) -> None:
        """Save research data for a company.

        Args:
            company_slug: Slugified company name.
            research: Research data dictionary.
        """
        research_dir = self.data_dir / "research"
        research_dir.mkdir(parents=True, exist_ok=True)

        output_path = research_dir / f"{company_slug}.json"
        with open(output_path, "w") as f:
            json.dump(research, f, indent=2)

    # =========================================================================
    # Deleted Jobs (for learning)
    # =========================================================================

    def record_deleted_job(self, job: dict, reason: str | None = None) -> None:
        """Record a deleted job for negative learning.

        Args:
            job: The deleted job dictionary.
            reason: Optional reason for deletion.
        """
        deleted_file = self.data_dir / "deleted-jobs.json"

        # Load existing
        deleted_jobs = []
        if deleted_file.exists():
            with open(deleted_file) as f:
                data = json.load(f)
                deleted_jobs = data.get("jobs", [])

        # Add deletion metadata
        job["deleted_at"] = datetime.now(timezone.utc).isoformat()
        job["deletion_reason"] = reason

        # Append and save
        deleted_jobs.append(job)

        with open(deleted_file, "w") as f:
            json.dump(
                {
                    "jobs": deleted_jobs,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
            )

    def get_deleted_jobs(self) -> list[dict]:
        """Get all deleted jobs.

        Returns:
            List of deleted job dictionaries.
        """
        deleted_file = self.data_dir / "deleted-jobs.json"

        if not deleted_file.exists():
            return []

        with open(deleted_file) as f:
            data = json.load(f)
            return data.get("jobs", [])

    # =========================================================================
    # Learned Preferences
    # =========================================================================

    def get_learned_preferences(self) -> dict | None:
        """Get learned preferences.

        Returns:
            Preferences dictionary or None if not found.
        """
        prefs_file = self.data_dir / "learned-preferences.json"

        if not prefs_file.exists():
            return None

        with open(prefs_file) as f:
            return json.load(f)

    def save_learned_preferences(self, preferences: dict) -> None:
        """Save learned preferences.

        Args:
            preferences: Preferences dictionary to save.
        """
        prefs_file = self.data_dir / "learned-preferences.json"
        with open(prefs_file, "w") as f:
            json.dump(preferences, f, indent=2)

    # =========================================================================
    # Candidate Profile
    # =========================================================================

    def get_profile(self) -> dict | None:
        """Get candidate profile.

        Returns:
            Profile dictionary or None if not found.
        """
        profile_file = self.data_dir / "candidate-profile.json"

        if not profile_file.exists():
            return None

        with open(profile_file) as f:
            return json.load(f)

    def save_profile(self, profile: dict) -> None:
        """Save candidate profile.

        Args:
            profile: Profile dictionary to save.
        """
        profile_file = self.data_dir / "candidate-profile.json"
        with open(profile_file, "w") as f:
            json.dump(profile, f, indent=2)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _ensure_index(self) -> None:
        """Build job index if not already built."""
        if self._job_index is not None:
            return

        self._job_index = {}

        for slug in get_all_location_slugs(self.config):
            jobs_file = self.data_dir / f"jobs-{slug}.json"
            if not jobs_file.exists():
                continue

            with open(jobs_file) as f:
                data = json.load(f)

            for job in data.get("jobs", []):
                job_id = job.get("id")
                if job_id:
                    self._job_index[job_id] = slug

    def _is_duplicate(self, job: dict, existing_jobs: list[dict]) -> bool:
        """Check if a job is a duplicate.

        For imported jobs (source="imported"), only check exact ID match.
        For discovered jobs, also check company+title combination.

        Args:
            job: Job to check.
            existing_jobs: List of existing jobs to check against.

        Returns:
            True if job is a duplicate.
        """
        job_id = job.get("id")
        existing_ids = {j.get("id") for j in existing_jobs}

        # Check exact ID match
        if job_id and job_id in existing_ids:
            return True

        # For discovered jobs, also check company+title
        if job.get("source") != "imported":
            existing_discovered = {
                (j["company"], j["title"])
                for j in existing_jobs
                if j.get("source") != "imported"
            }
            key = (job.get("company"), job.get("title"))
            if key in existing_discovered:
                return True

        return False

    def invalidate_index(self) -> None:
        """Invalidate the job index, forcing rebuild on next lookup."""
        self._job_index = None
