"""Job Importer - imports jobs from URLs and markdown files."""

import re
import uuid
from datetime import datetime, timezone

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from config_loader import (
    get_locations,
    get_location_slug,
    get_location_description,
    is_remote_enabled,
    classify_job_location,
)
from data_store import DataStore
from .base_agent import BaseAgent

console = Console()

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


class JobImporter(BaseAgent):
    """Agent that imports jobs from URLs and markdown files."""

    def __init__(self, config: dict):
        """Initialize the job importer.

        Args:
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.data_store = DataStore(config)

    def import_from_url(self, url: str) -> dict | None:
        """Import a job posting from a URL.

        Args:
            url: URL of the job posting.

        Returns:
            The imported job dictionary, or None if import failed.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Fetch the URL
            task = progress.add_task("Fetching job posting...", total=None)
            content = self._fetch_url_content(url)

            if not content:
                console.print("[red]Could not fetch job posting from URL[/red]")
                return None

            # Step 2: Parse with Claude
            progress.update(task, description="Parsing job details...")
            job = self._parse_job_posting(url, content)

            if not job:
                console.print("[red]Could not parse job posting[/red]")
                return None

        # Add ID, URL, and source tracking
        company_name = job.get("company") or "unknown"
        company_slug = self._slugify(company_name)
        job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        job["url"] = url
        job["source"] = "imported"
        job["imported_at"] = datetime.now(timezone.utc).isoformat()
        job["company"] = company_name

        # Save to data store
        self.data_store.save_job(job)

        # Print summary
        self._print_job_summary(job)

        return job

    def import_from_markdown(self, content: str, filename: str) -> dict | None:
        """Import a job posting from markdown content.

        Args:
            content: The markdown/text content of the job description.
            filename: The source filename (for reference).

        Returns:
            The imported job dictionary, or None if parsing failed.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Parsing {filename}...", total=None)

            # Parse with Claude
            job = self._parse_job_posting(f"manual import from {filename}", content)

            if not job:
                console.print(f"[red]Could not parse job from {filename}[/red]")
                return None

        # Add ID and source tracking
        company_name = job.get("company") or "unknown"
        company_slug = self._slugify(company_name)
        job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        job["url"] = None
        job["source"] = "imported"
        job["imported_at"] = datetime.now(timezone.utc).isoformat()
        job["source_file"] = filename
        job["company"] = company_name

        # Save to data store
        self.data_store.save_job(job)

        # Print summary
        self._print_job_summary(job)

        return job

    def _fetch_url_content(self, url: str) -> str | None:
        """Fetch content from a URL.

        Args:
            url: URL to fetch.

        Returns:
            Page content as string, or None if fetch failed.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.text
                else:
                    console.print(f"[red]HTTP {response.status_code} fetching URL[/red]")
        except Exception as e:
            console.print(f"[red]Error fetching URL: {e}[/red]")
        return None

    def _parse_job_posting(self, url: str, content: str) -> dict | None:
        """Parse job posting content with Claude.

        Args:
            url: Source URL (for context in prompt).
            content: Page content to parse.

        Returns:
            Parsed job dictionary, or None if parsing failed.
        """
        # Truncate content if too long
        if len(content) > 50000:
            content = content[:50000] + "\n... [truncated]"

        # Build system prompt with learned preferences for scoring
        system_prompt = self._get_url_parse_prompt() + self._build_learned_context("job_scoring")

        try:
            job = self.client.complete_json(
                system=system_prompt,
                user=f"Parse this job posting from {url}:\n\n{content}",
                max_tokens=2048,
            )

            # Validate and correct location_type using our classifier
            if job:
                job_location = job.get("location", "")
                job["location_type"] = classify_job_location(job_location, self.config)

            return job
        except ValueError as e:
            console.print(f"[red]Error parsing job: {e}[/red]")
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
        """Convert a name to a slug.

        Args:
            name: Name to slugify.

        Returns:
            Lowercase, hyphenated slug.
        """
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug

    def _print_job_summary(self, job: dict) -> None:
        """Print summary of imported job."""
        company = job.get("company", "Unknown")
        title = job.get("title", "Unknown")
        location = job.get("location", "Unknown")
        location_type = job.get("location_type", "remote")
        score = job.get("match_score", "?")
        requirements = job.get("requirements_summary", "Not specified")

        console.print(
            Panel(
                f"[bold]{title}[/bold] at [cyan]{company}[/cyan]\n"
                f"[dim]Location: {location} ({location_type})[/dim]\n"
                f"[dim]Match Score: {score}/100[/dim]\n\n"
                f"[bold]Requirements:[/bold]\n{requirements}\n\n"
                f"[dim]ID: {job['id']}[/dim]",
                title="Job Imported",
            )
        )
