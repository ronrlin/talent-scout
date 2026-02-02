"""Company Researcher Agent - deep research on companies and job discovery."""

import json
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
from .job_importer import JobImporter

console = Console()

RESEARCH_SYSTEM_PROMPT = """You are a company research analyst helping with a job search. Your task is to provide comprehensive research on a specific company.

Research and provide:
1. **Company Overview**: Mission, what they do, their products/services
2. **Recent News**: Any significant recent developments, funding, acquisitions, leadership changes (from the last 6-12 months)
3. **Financial Health**: For public companies, recent performance. For private, funding status and investor backing
4. **Engineering Culture**: What's known about their tech stack, engineering practices, culture
5. **Key Leadership**: CEO, CTO, VP Engineering, and other relevant leaders
6. **Office Locations**: Where they have engineering presence

Return your response as valid JSON matching this schema:
{
  "company_name": "Official Company Name",
  "website": "https://...",
  "description": "What the company does in 2-3 sentences",
  "mission": "Company mission statement or values",
  "industry": "Industry/sector",
  "founded": "Year founded",
  "headquarters": "City, State",
  "employee_count": "Approximate employee count",
  "public": true/false,
  "stock_ticker": "TICK or null",
  "recent_news": [
    {"headline": "...", "summary": "...", "date": "approximate date"}
  ],
  "financial_summary": "Brief financial health summary",
  "engineering_culture": "What's known about eng culture, tech stack",
  "leadership": [
    {"name": "...", "title": "...", "linkedin": "url or null"}
  ],
  "office_locations": ["City, State", ...],
  "relevance_notes": "Why this company might be good for an Engineering Manager / TPM role"
}

Be accurate and factual. If you're unsure about something, say so rather than making it up."""

JOB_SEARCH_SYSTEM_PROMPT_TEMPLATE = """You are a job search assistant. Given information about a company, identify current job openings that match these target roles:
{target_roles}

Also look for related roles like:
- Senior Engineering Manager
- Group Engineering Manager
- Head of Engineering
- Principal Product Manager (Technical)

Based on what you know about this company, list any current or likely job openings in these categories.

Return your response as valid JSON:
{{
  "jobs": [
    {{
      "title": "Job Title",
      "department": "Engineering/Product/etc",
      "location": "City, State or Remote",
      "location_type": "<location_slug>",
      "url": "careers page URL if known, otherwise null",
      "posted_date": "approximate date or null",
      "requirements_summary": "Key requirements if known",
      "match_score": 0-100,
      "match_notes": "Why this role matches the candidate profile"
    }}
  ],
  "careers_page": "URL to company careers page",
  "notes": "Any notes about job search at this company"
}}

For location_type, use one of these values based on the job's location:
{location_type_rules}

Be realistic - only include jobs you have reasonable confidence exist or are likely to exist based on company size and typical hiring patterns."""


class CompanyResearcherAgent(BaseAgent):
    """Agent that researches companies and discovers job openings."""

    def __init__(self, config: dict):
        """Initialize the company researcher agent.

        Args:
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.data_store = DataStore(config)
        self.job_importer = JobImporter(config)

    def research(self, company_name: str) -> dict:
        """Research a company and find job openings.

        Args:
            company_name: Name of the company to research.

        Returns:
            Dictionary with company info, jobs, and metadata.
        """
        slug = self._slugify(company_name)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Company research
            task = progress.add_task(f"Researching {company_name}...", total=None)
            company_info = self._research_company(company_name)

            # Step 2: Job search
            progress.update(task, description=f"Finding jobs at {company_name}...")
            jobs_info = self._find_jobs(company_name, company_info)

            # Step 3: Try to fetch careers page
            progress.update(task, description="Checking careers page...")
            careers_data = self._fetch_careers_page(jobs_info.get("careers_page"))

        # Combine results
        result = {
            "company": company_info,
            "jobs": jobs_info.get("jobs", []),
            "careers_page": jobs_info.get("careers_page"),
            "search_notes": jobs_info.get("notes"),
            "researched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save research
        self.data_store.save_research(slug, result)
        console.print(f"[dim]Saved research to data/research/{slug}.json[/dim]")

        # Add jobs to location files
        jobs = jobs_info.get("jobs", [])
        if jobs:
            added = self.data_store.save_jobs(jobs, company_name)
            if added > 0:
                console.print(f"[dim]Added {added} job(s) to data files[/dim]")

        # Print summary
        self._print_summary(company_info, jobs)

        return result

    def import_job_from_url(self, url: str) -> dict | None:
        """Import a job posting from a URL.

        Delegates to JobImporter.

        Args:
            url: URL of the job posting.

        Returns:
            The imported job dictionary, or None if import failed.
        """
        return self.job_importer.import_from_url(url)

    def import_job_from_markdown(self, content: str, filename: str) -> dict | None:
        """Import a job posting from markdown content.

        Delegates to JobImporter.

        Args:
            content: The markdown/text content of the job description.
            filename: The source filename (for reference).

        Returns:
            The imported job dictionary, or None if parsing failed.
        """
        return self.job_importer.import_from_markdown(content, filename)

    def _research_company(self, company_name: str) -> dict:
        """Get detailed company research from Claude."""
        try:
            return self.client.complete_json(
                system=RESEARCH_SYSTEM_PROMPT,
                user=f"Research this company: {company_name}\n\nProvide comprehensive information for a job seeker targeting Engineering Manager and Technical Product Manager roles.",
                max_tokens=4096,
            )
        except ValueError as e:
            console.print(f"[red]Error researching company: {e}[/red]")
            return {}

    def _find_jobs(self, company_name: str, company_info: dict) -> dict:
        """Find job openings at the company."""
        context = json.dumps(company_info, indent=2) if company_info else "No additional context"

        # Build enhanced prompt with learned preferences
        learned_context = self._build_learned_context("job_search")

        # Build location priorities from config
        locations = get_locations(self.config)
        location_priorities = []
        for i, loc in enumerate(locations, 1):
            location_priorities.append(f"{i}. {get_location_description(loc)}")
        if is_remote_enabled(self.config):
            location_priorities.append(f"{len(locations) + 1}. Remote / Distributed")
        location_text = "\n".join(location_priorities)

        # Get target roles from config
        target_roles = self.config.get("preferences", {}).get("target_roles", [])
        roles_text = (
            ", ".join(target_roles)
            if target_roles
            else "Engineering Manager, Director, and Technical Product Manager"
        )

        system_prompt = self._get_job_search_prompt() + learned_context

        try:
            jobs_data = self.client.complete_json(
                system=system_prompt,
                user=f"""Find job openings at {company_name}.

Company context:
{context}

Target locations (in priority order):
{location_text}

Find relevant {roles_text} roles.""",
                max_tokens=4096,
            )
        except ValueError as e:
            console.print(f"[red]Error finding jobs: {e}[/red]")
            jobs_data = {"jobs": []}

        # Add unique IDs and source to jobs, and validate/correct location_type
        for job in jobs_data.get("jobs", []):
            job["id"] = f"JOB-{self._slugify(company_name).upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
            job["company"] = company_name
            job["source"] = "discovered"

            # Validate and correct location_type using our classifier
            job_location = job.get("location", "")
            job["location_type"] = classify_job_location(job_location, self.config)

        return jobs_data

    def _get_job_search_prompt(self) -> str:
        """Build the job search system prompt with config-based locations."""
        return JOB_SEARCH_SYSTEM_PROMPT_TEMPLATE.format(
            target_roles=self._build_target_roles_text(),
            location_type_rules=self._build_location_type_rules(),
        )

    def _build_target_roles_text(self) -> str:
        """Build target roles text from config for prompts."""
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

    def _fetch_careers_page(self, url: str | None) -> dict | None:
        """Attempt to fetch and analyze a careers page."""
        if not url:
            return None

        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return {
                        "url": url,
                        "status": "accessible",
                        "content_length": len(response.text),
                    }
        except Exception as e:
            console.print(f"[dim]Could not fetch careers page: {e}[/dim]")

        return {"url": url, "status": "not_accessible"}

    def _slugify(self, name: str) -> str:
        """Convert company name to slug."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug

    def _print_summary(self, company_info: dict, jobs: list[dict]) -> None:
        """Print research summary."""
        if company_info:
            name = company_info.get("company_name", "Unknown")
            desc = company_info.get("description", "No description")
            industry = company_info.get("industry", "Unknown")
            employees = company_info.get("employee_count", "Unknown")
            public = "Public" if company_info.get("public") else "Private"

            console.print(
                Panel(
                    f"[bold]{name}[/bold] ({public})\n"
                    f"[dim]{industry} - ~{employees} employees[/dim]\n\n"
                    f"{desc}",
                    title="Company Overview",
                )
            )

        if jobs:
            console.print(f"\n[bold]Found {len(jobs)} relevant job(s):[/bold]")
            for job in jobs[:5]:
                score = job.get("match_score", "?")
                loc = job.get("location", "Unknown")
                console.print(
                    f"  - {job['title']} [dim]({loc}, score: {score})[/dim]"
                )
                console.print(f"    [dim]ID: {job['id']}[/dim]")

            if len(jobs) > 5:
                console.print(f"  [dim]... and {len(jobs) - 5} more[/dim]")
        else:
            console.print("\n[yellow]No matching jobs found[/yellow]")
