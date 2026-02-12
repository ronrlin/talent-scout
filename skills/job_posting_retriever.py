"""Job Posting Retriever Skill - fetches and parses job postings from URLs or markdown."""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Configure error logger to write to error.log in project root
_error_logger = logging.getLogger("talent_scout.job_retriever")
_error_logger.setLevel(logging.DEBUG)
if not _error_logger.handlers:
    _log_path = Path(__file__).resolve().parent.parent / "error.log"
    _file_handler = logging.FileHandler(_log_path)
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    _error_logger.addHandler(_file_handler)

from config_loader import (
    get_locations,
    get_location_slug,
    get_location_description,
    is_remote_enabled,
    classify_job_location,
)
from .base_skill import BaseSkill, SkillContext, SkillResult


JOB_URL_PARSE_PROMPT_TEMPLATE = """You are a job posting parser. Given the raw content from a job posting URL, extract the key information.

Return your response as valid JSON:
{{
  "company": "Company Name",
  "title": "Job Title",
  "department": "Engineering/Product/etc",
  "location": "City, State or Remote",
  "location_type": "<location_slug>",
  "posted_date": "Date if found, otherwise null",
  "requirements_summary": "Key requirements (years experience, skills, etc)",
  "responsibilities_summary": "Key responsibilities",
  "compensation": "Salary/compensation if mentioned, otherwise null",
  "match_score": 0-100,
  "match_notes": "Assessment of how well this matches the target role profile"
}}

For location_type, use these rules:
{location_type_rules}

For match_score, consider how well the role aligns with these target profiles:
{target_roles}

Be thorough in extracting requirements and responsibilities."""


@dataclass
class JobPostingResult:
    """Result of job posting retrieval."""

    job: dict
    """Parsed job dictionary with ID and metadata."""

    source_url: str | None
    """Source URL if imported from URL."""

    source_file: str | None
    """Source filename if imported from markdown."""


class JobPostingRetrieverSkill(BaseSkill):
    """Skill that fetches and parses job postings from URLs or markdown content."""

    def execute(
        self,
        context: SkillContext,
        url: str | None = None,
        content: str | None = None,
        filename: str | None = None,
    ) -> SkillResult:
        """Fetch and parse a job posting.

        Args:
            context: Execution context with config and learned preferences.
            url: URL to fetch job posting from.
            content: Markdown/text content to parse (alternative to URL).
            filename: Source filename when using content.

        Returns:
            SkillResult with JobPostingResult data.
        """
        if url:
            return self._import_from_url(url, context)
        elif content:
            return self._import_from_markdown(content, filename or "manual", context)
        else:
            return SkillResult.fail("Either url or content must be provided")

    def _import_from_url(self, url: str, context: SkillContext) -> SkillResult:
        """Import a job posting from a URL."""
        # Fetch the URL
        content = self._fetch_url_content(url)
        if not content:
            msg = f"Could not fetch job posting from URL: {url} (see error.log for details)"
            _error_logger.error("Job import failed at fetch stage for URL: %s", url)
            return SkillResult.fail(msg)

        # Parse with Claude
        job = self._parse_job_posting(url, content, context)
        if not job:
            msg = f"Could not parse job posting from URL: {url} (see error.log for details)"
            _error_logger.error(
                "Job import failed at parse stage for URL: %s — content length: %d, first 200 chars: %s",
                url,
                len(content),
                content[:200],
            )
            return SkillResult.fail(msg)

        # Add ID, URL, and source tracking
        company_name = job.get("company") or "unknown"
        company_slug = self._slugify(company_name)
        job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        job["url"] = url
        job["source"] = "imported"
        job["imported_at"] = datetime.now(timezone.utc).isoformat()
        job["company"] = company_name

        result = JobPostingResult(
            job=job,
            source_url=url,
            source_file=None,
        )

        return SkillResult.ok(result)

    def _import_from_markdown(
        self, content: str, filename: str, context: SkillContext
    ) -> SkillResult:
        """Import a job posting from markdown content."""
        # Parse with Claude
        job = self._parse_job_posting(f"manual import from {filename}", content, context)
        if not job:
            return SkillResult.fail(f"Could not parse job from {filename}")

        # Add ID and source tracking
        company_name = job.get("company") or "unknown"
        company_slug = self._slugify(company_name)
        job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        job["url"] = None
        job["source"] = "imported"
        job["imported_at"] = datetime.now(timezone.utc).isoformat()
        job["source_file"] = filename
        job["company"] = company_name

        result = JobPostingResult(
            job=job,
            source_url=None,
            source_file=filename,
        )

        return SkillResult.ok(result)

    def _fetch_url_content(self, url: str) -> str | None:
        """Fetch content from a URL."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.text
                _error_logger.error(
                    "HTTP %d fetching %s — response: %s",
                    response.status_code,
                    url,
                    response.text[:500],
                )
        except httpx.TimeoutException as e:
            _error_logger.error("Timeout fetching %s: %s", url, e)
        except httpx.ConnectError as e:
            _error_logger.error("Connection error fetching %s: %s", url, e)
        except Exception as e:
            _error_logger.error("Unexpected error fetching %s: %s: %s", url, type(e).__name__, e)
        return None

    def _parse_job_posting(
        self, source: str, content: str, context: SkillContext
    ) -> dict | None:
        """Parse job posting content with Claude."""
        # Truncate content if too long
        if len(content) > 50000:
            content = content[:50000] + "\n... [truncated]"

        # Build system prompt with learned preferences for scoring
        system_prompt = self._get_url_parse_prompt()
        if context.learned_context:
            system_prompt += context.learned_context

        try:
            job = self.client.complete_json(
                system=system_prompt,
                user=f"Parse this job posting from {source}:\n\n{content}",
                max_tokens=2048,
            )

            # Validate and correct location_type using classifier
            if job:
                job_location = job.get("location", "")
                job["location_type"] = classify_job_location(job_location, self.config)

            return job
        except ValueError as e:
            _error_logger.error(
                "Failed to parse Claude response for %s: %s", source, e
            )
            return None

    def _get_url_parse_prompt(self) -> str:
        """Build the URL parse system prompt with config-based locations."""
        return JOB_URL_PARSE_PROMPT_TEMPLATE.format(
            target_roles=self._build_target_roles_text(),
            location_type_rules=self._build_location_type_rules(),
        )

    def _build_target_roles_text(self) -> str:
        """Build target roles text from config."""
        target_roles = self.config.get("preferences", {}).get(
            "target_roles",
            [
                "Engineering Manager",
                "Software Manager",
                "Technical Product Manager",
                "Director of Analytics Engineering",
            ],
        )
        return "\n".join(f"- {role}" for role in target_roles)

    def _build_location_type_rules(self) -> str:
        """Build location type rules from config for prompts."""
        rules = []
        locations = get_locations(self.config)

        for location in locations:
            slug = get_location_slug(location)
            desc = get_location_description(location)
            rules.append(f'- "{slug}" = {desc}')

        if is_remote_enabled(self.config):
            rules.append(
                '- "remote" = Remote, distributed, work from anywhere, or hybrid with remote option'
            )
            rules.append(
                '\nIf the location doesn\'t clearly match any configured location, default to "remote".'
            )
        elif locations:
            default_slug = get_location_slug(locations[0])
            rules.append(
                f'\nIf the location doesn\'t clearly match any configured location, default to "{default_slug}".'
            )

        return "\n".join(rules)

    def _slugify(self, name: str) -> str:
        """Convert a name to a slug."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug
