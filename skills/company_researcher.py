"""Company Researcher Skill - researches company details and discovers jobs."""

import json
import re
import uuid
from dataclasses import dataclass

import httpx

from config_loader import (
    get_locations,
    get_location_slug,
    get_location_description,
    is_remote_enabled,
    classify_job_location,
)
from .base_skill import BaseSkill, SkillContext, SkillResult, _load_reference

RESEARCH_SYSTEM_PROMPT = _load_reference("company-research-prompt.md")
JOB_SEARCH_SYSTEM_PROMPT_TEMPLATE = _load_reference("job-search-prompt.md")


@dataclass
class CompanyResearchResult:
    """Result of company research."""

    company_info: dict
    """Company information dictionary."""

    jobs: list[dict]
    """List of discovered job dictionaries."""

    careers_page: str | None
    """URL to company careers page."""

    search_notes: str | None
    """Notes about the job search."""


class CompanyResearcherSkill(BaseSkill):
    """Skill that researches companies and discovers job openings."""

    def execute(
        self,
        context: SkillContext,
        company_name: str,
    ) -> SkillResult:
        """Research a company and find job openings.

        Args:
            context: Execution context with config and learned preferences.
            company_name: Name of the company to research.

        Returns:
            SkillResult with CompanyResearchResult data.
        """
        # Step 1: Research the company
        company_info = self._research_company(company_name)
        if not company_info:
            return SkillResult.fail("Failed to research company")

        # Step 2: Find jobs at the company
        jobs_data = self._find_jobs(company_name, company_info, context)

        # Step 3: Try to verify careers page accessibility
        careers_data = self._check_careers_page(jobs_data.get("careers_page"))

        # Process jobs - add IDs, validate locations
        jobs = self._process_jobs(jobs_data.get("jobs", []), company_name)

        result = CompanyResearchResult(
            company_info=company_info,
            jobs=jobs,
            careers_page=jobs_data.get("careers_page"),
            search_notes=jobs_data.get("notes"),
        )

        return SkillResult.ok(
            result,
            careers_accessible=careers_data.get("status") == "accessible" if careers_data else False,
        )

    def research_company_only(self, company_name: str) -> SkillResult:
        """Research only company details without job search.

        Args:
            company_name: Name of the company to research.

        Returns:
            SkillResult with company info dictionary.
        """
        company_info = self._research_company(company_name)
        if not company_info:
            return SkillResult.fail("Failed to research company")
        return SkillResult.ok(company_info)

    def _research_company(self, company_name: str) -> dict | None:
        """Get detailed company research from Claude."""
        try:
            return self.client.complete_json(
                system=RESEARCH_SYSTEM_PROMPT,
                user=f"Research this company: {company_name}\n\nProvide comprehensive information for a job seeker targeting Engineering Manager and Technical Product Manager roles.",
                max_tokens=4096,
            )
        except ValueError:
            return None

    def _find_jobs(
        self, company_name: str, company_info: dict, context: SkillContext
    ) -> dict:
        """Find job openings at the company."""
        company_context = json.dumps(company_info, indent=2) if company_info else "No additional context"

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

        # Build system prompt with learned preferences
        system_prompt = self._get_job_search_prompt()
        if context.learned_context:
            system_prompt += context.learned_context

        try:
            return self.client.complete_json(
                system=system_prompt,
                user=f"""Find job openings at {company_name}.

Company context:
{company_context}

Target locations (in priority order):
{location_text}

Find relevant {roles_text} roles.""",
                max_tokens=4096,
            )
        except ValueError:
            return {"jobs": []}

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

    def _process_jobs(self, jobs: list[dict], company_name: str) -> list[dict]:
        """Add IDs and validate location_type for jobs."""
        company_slug = self._slugify(company_name)

        for job in jobs:
            # Add unique ID
            job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
            job["company"] = company_name
            job["source"] = "discovered"

            # Validate and correct location_type using classifier
            job_location = job.get("location", "")
            job["location_type"] = classify_job_location(job_location, self.config)

        return jobs

    def _check_careers_page(self, url: str | None) -> dict | None:
        """Check if careers page is accessible."""
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
        except Exception:
            pass

        return {"url": url, "status": "not_accessible"}

    def _slugify(self, name: str) -> str:
        """Convert company name to slug."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug
