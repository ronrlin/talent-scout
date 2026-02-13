"""Discovery service - company scouting, research, job import, and learning.

Extracted from agents/opportunity_scout.py.
"""

import json
import logging
import re
from datetime import datetime, timezone

from config_loader import (
    get_location_slug,
    get_location_description,
)
from skills import (
    CompanyResearcherSkill,
    JobPostingRetrieverSkill,
    JobDescriptionAnalyzerSkill,
    SkillContext,
)

from .base_service import BaseService
from .exceptions import GenerationFailedError, JobNotFoundError
from .models import CompanySummary, ResearchResult, LearningResult

logger = logging.getLogger(__name__)

# ============================================================================
# Prompts (copied from opportunity_scout.py)
# ============================================================================

SCOUT_SYSTEM_PROMPT = """You are a company research assistant helping with a job search. Your task is to identify and evaluate technology companies that would be good targets for a job search.

The ideal target companies:
- Are technology companies where software is a revenue driver (not just a cost center)
- Have strong engineering cultures
- Are financially stable (prefer public companies or well-funded private)
- Have roles matching: Engineering Manager, Software Manager, Technical Product Manager, Director of Analytics Engineering

For each company, provide:
1. Company name
2. Website URL
3. Headquarters location
4. Industry/sector
5. Approximate employee count
6. Whether publicly traded
7. A priority score from 0-100 based on fit
8. Brief notes on why this company is a good target

Return your response as valid JSON matching this schema:
{
  "companies": [
    {
      "name": "Company Name",
      "website": "https://example.com",
      "hq_location": "City, State",
      "industry": "Industry description",
      "employee_count": "1000-5000",
      "public": true,
      "priority_score": 85,
      "notes": "Why this company is a good fit"
    }
  ]
}

Be thorough and accurate. Only include companies you're confident exist and match the criteria."""

COMBINED_LEARNING_PROMPT = """You are a job search optimization assistant. You have TWO types of feedback to analyze:

1. POSITIVE SIGNALS - Jobs the user manually IMPORTED (they want MORE like these)
2. NEGATIVE SIGNALS - Jobs the user DELETED/REJECTED (they want FEWER like these)

Analyze both to build a comprehensive understanding of what makes a good job match.

Return your analysis as JSON:
{
  "positive_analysis": {
    "title_patterns": ["job title patterns from imported jobs"],
    "key_skills": ["skills that appear in desired roles"],
    "experience_level": "target seniority level",
    "industry_patterns": ["appealing industries"],
    "company_characteristics": ["desirable company traits"],
    "compelling_factors": ["what makes these roles attractive"]
  },
  "negative_analysis": {
    "title_patterns_to_avoid": ["job title patterns to deprioritize"],
    "skills_mismatch": ["skills/requirements that indicate poor fit"],
    "company_red_flags": ["company characteristics to avoid"],
    "role_red_flags": ["role aspects that are unappealing"]
  },
  "improved_targeting": {
    "primary_titles": ["exact job titles to prioritize"],
    "secondary_titles": ["related titles worth considering"],
    "titles_to_avoid": ["job titles to deprioritize or exclude"],
    "must_have_keywords": ["keywords that should appear in ideal postings"],
    "nice_to_have_keywords": ["positive signal keywords"],
    "red_flag_keywords": ["keywords that indicate poor fit - penalize these"],
    "ideal_company_profile": "description of ideal company",
    "companies_to_avoid": "types of companies to deprioritize"
  },
  "scoring_adjustments": {
    "boost_factors": ["factors that should increase match score"],
    "penalty_factors": ["factors that should decrease match score"]
  },
  "prompt_improvements": {
    "job_search_additions": "text to add to job search prompts",
    "job_search_exclusions": "text about what to exclude from job searches",
    "company_scout_additions": "text to add to company scouting prompts",
    "match_scoring_criteria": "comprehensive scoring criteria including penalties"
  },
  "insights": "2-3 sentence summary combining positive preferences and things to avoid"
}

Be specific and actionable. Balance learning from both positive and negative signals."""

LEARNING_ANALYSIS_PROMPT = """You are a job search optimization assistant. Analyze the following manually imported job postings to understand what the job seeker is actually looking for.

These jobs were manually imported by the user, meaning they represent REAL interest - the user found these jobs compelling enough to add them to their tracking system.

Your task is to:
1. Identify patterns in job titles, responsibilities, and requirements
2. Understand what industries and company types appeal to this person
3. Extract key skills and qualifications that appear repeatedly
4. Identify what makes these roles attractive (seniority level, team size, scope, etc.)
5. Note any patterns in company characteristics (size, stage, culture indicators)

Return your analysis as JSON:
{
  "analysis": {
    "title_patterns": ["list of job title patterns/keywords that appear"],
    "key_skills": ["technical and leadership skills mentioned repeatedly"],
    "experience_level": "typical years of experience / seniority level",
    "team_scope": "typical team size or organizational scope",
    "industry_patterns": ["industries that appear appealing"],
    "company_characteristics": ["company traits that seem attractive"],
    "role_focus": "what the roles tend to focus on (people mgmt, technical strategy, product, etc.)",
    "compelling_factors": ["what seems to make these roles attractive"]
  },
  "improved_targeting": {
    "primary_titles": ["exact job titles to search for, ordered by relevance"],
    "secondary_titles": ["related titles worth considering"],
    "must_have_keywords": ["keywords that should appear in ideal job postings"],
    "nice_to_have_keywords": ["keywords that are positive signals"],
    "red_flag_keywords": ["keywords that indicate poor fit"],
    "ideal_company_profile": "description of ideal company characteristics"
  },
  "prompt_improvements": {
    "job_search_additions": "specific text to add to job search prompts",
    "company_scout_additions": "specific text to add to company scouting prompts",
    "match_scoring_criteria": "how to better score job matches based on these patterns"
  },
  "insights": "2-3 sentence summary of key insights about what this person is looking for"
}

Be specific and actionable. These recommendations will be used to improve automated job discovery."""

NEGATIVE_LEARNING_PROMPT = """You are a job search optimization assistant. Analyze the following DELETED/REJECTED job postings to understand what the job seeker does NOT want.

These jobs were explicitly removed by the user, meaning they represent roles to AVOID - the user saw these jobs and decided they were not a good fit.

Your task is to:
1. Identify patterns in why these jobs might have been rejected
2. Extract job title patterns that should be deprioritized
3. Identify company characteristics that seem unappealing
4. Find keywords or requirements that signal poor fit
5. Note any seniority, scope, or role focus patterns to avoid

Return your analysis as JSON:
{
  "rejection_patterns": {
    "title_patterns_to_avoid": ["job title keywords that indicate poor fit"],
    "role_characteristics_to_avoid": ["aspects of roles that seem unappealing"],
    "company_red_flags": ["company characteristics to deprioritize"],
    "keyword_red_flags": ["specific keywords that signal poor fit"],
    "seniority_mismatches": "any patterns around seniority level mismatches",
    "scope_mismatches": "any patterns around role scope that doesn't fit"
  },
  "score_penalties": {
    "title_keywords": ["keywords in titles that should reduce match score"],
    "requirement_keywords": ["requirement keywords that should reduce match score"],
    "company_types": ["company types to deprioritize"]
  },
  "prompt_adjustments": {
    "roles_to_exclude": "text describing roles to explicitly exclude from searches",
    "deprioritization_criteria": "criteria for lowering priority of similar roles"
  },
  "insights": "2-3 sentence summary of what this person is trying to avoid"
}

Be specific about patterns. These will be used to filter OUT unwanted job matches."""


class DiscoveryService(BaseService):
    """Service for company discovery, research, job import, and learning.

    Wraps OpportunityScoutAgent's business logic with typed exceptions
    and Pydantic response models.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize skills
        self.company_researcher = CompanyResearcherSkill(
            self.client, self.data_store, self.config
        )
        self.job_retriever = JobPostingRetrieverSkill(
            self.client, self.data_store, self.config
        )
        self.job_analyzer = JobDescriptionAnalyzerSkill(
            self.client, self.data_store, self.config
        )

    # =========================================================================
    # Company Scouting
    # =========================================================================

    def scout_companies(self, location: str, count: int | None = None) -> list[CompanySummary]:
        """Scout companies for a given location.

        Args:
            location: Target location (e.g., "Palo Alto, CA" or "remote").
            count: Number of companies to find.

        Returns:
            List of CompanySummary models sorted by priority score.
        """
        if count is None:
            count = self.config.get("preferences", {}).get("companies_per_location", 15)

        target_companies = self.config.get("target_companies", [])
        excluded_companies = self.config.get("excluded_companies", [])
        excluded_names = {c["name"].lower() for c in excluded_companies}

        seed_names = [c["name"] for c in target_companies]

        # Build prompt with learned preferences
        prompt = self._build_scout_prompt(location, seed_names, count)
        system_prompt = SCOUT_SYSTEM_PROMPT + self._build_learned_context("company_scout")

        try:
            result = self.client.complete_json(
                system=system_prompt,
                user=prompt,
                max_tokens=4096,
            )
            companies = result.get("companies", [])
        except ValueError as e:
            raise GenerationFailedError("Company scouting", str(e))

        # Filter excluded, sort, limit
        companies = [c for c in companies if c["name"].lower() not in excluded_names]
        companies.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        companies = companies[:count]

        # Save results
        slug = get_location_slug(location)
        self.data_store.save_companies(companies, slug, location)
        logger.info("Saved %d companies to data/companies-%s.json", len(companies), slug)

        return [CompanySummary(**c) for c in companies]

    # =========================================================================
    # Company Research
    # =========================================================================

    def research_company(self, company_name: str) -> ResearchResult:
        """Research a company and find job openings.

        Args:
            company_name: Name of the company to research.

        Returns:
            ResearchResult with company info and jobs.
        """
        slug = self._slugify(company_name)

        context = SkillContext(
            config=self.config,
            learned_context=self._build_learned_context("job_search"),
        )

        result = self.company_researcher.execute(context, company_name)

        if not result.success:
            raise GenerationFailedError("Company research", result.error)

        research_data = result.data
        company_info = research_data.company_info
        jobs = research_data.jobs

        # Combine results
        full_result = {
            "company": company_info,
            "jobs": jobs,
            "careers_page": research_data.careers_page,
            "search_notes": research_data.search_notes,
            "researched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save research
        self.data_store.save_research(slug, full_result)
        logger.info("Saved research to data/research/%s.json", slug)

        # Add jobs to location files
        jobs_added = 0
        if jobs:
            jobs_added = self.data_store.save_jobs(jobs, company_name)
            if jobs_added > 0:
                logger.info("Added %d job(s) to data files", jobs_added)

            # Pipeline: create entries for discovered jobs
            for job in jobs:
                self.pipeline.create(job["id"], "auto:research")

        return ResearchResult(
            company=company_info if isinstance(company_info, dict) else {},
            jobs=jobs,
            jobs_added=jobs_added,
            careers_page=research_data.careers_page,
            search_notes=research_data.search_notes,
        )

    # =========================================================================
    # Job Import
    # =========================================================================

    def import_job_from_url(self, url: str) -> dict:
        """Import a job posting from a URL.

        Args:
            url: URL of the job posting.

        Returns:
            The imported job dictionary.

        Raises:
            GenerationFailedError: If import fails.
        """
        context = SkillContext(
            config=self.config,
            learned_context=self._build_learned_context("job_scoring"),
        )

        result = self.job_retriever.execute(context, url=url)

        if not result.success:
            raise GenerationFailedError("Job import from URL", result.error)

        job = result.data.job

        self.data_store.save_job(job)
        self.pipeline.create(job["id"], "auto:import_url")
        logger.info("Imported job %s from URL", job["id"])

        return job

    def import_job_from_markdown(self, content: str, filename: str) -> dict:
        """Import a job posting from markdown content.

        Args:
            content: The markdown/text content of the job description.
            filename: The source filename (for reference).

        Returns:
            The imported job dictionary.

        Raises:
            GenerationFailedError: If parsing fails.
        """
        context = SkillContext(
            config=self.config,
            learned_context=self._build_learned_context("job_scoring"),
        )

        result = self.job_retriever.execute(
            context, content=content, filename=filename
        )

        if not result.success:
            raise GenerationFailedError("Job import from markdown", result.error)

        job = result.data.job

        self.data_store.save_job(job)
        self.pipeline.create(job["id"], "auto:import_markdown")
        logger.info("Imported job %s from %s", job["id"], filename)

        return job

    # =========================================================================
    # Learning
    # =========================================================================

    def learn_from_feedback(self) -> LearningResult:
        """Analyze imported and deleted jobs to generate learning insights.

        Returns:
            LearningResult with insights and targeting improvements.

        Raises:
            GenerationFailedError: If analysis fails.
        """
        imported_jobs = self.data_store.get_jobs(source="imported")
        deleted_jobs = self.data_store.get_deleted_jobs()

        if not imported_jobs and not deleted_jobs:
            return LearningResult(
                insights="No feedback found. Import jobs you like or delete jobs you don't want.",
                positive_count=0,
                negative_count=0,
            )

        # Analyze with Claude
        if imported_jobs and deleted_jobs:
            analysis = self._analyze_combined(imported_jobs, deleted_jobs)
        elif imported_jobs:
            analysis = self._analyze_imported(imported_jobs)
        else:
            analysis = self._analyze_deleted_only(deleted_jobs)

        if not analysis:
            raise GenerationFailedError("Learning analysis", "Failed to analyze feedback")

        # Save preferences
        self._save_preferences(analysis, imported_jobs, deleted_jobs)

        return LearningResult(
            insights=analysis.get("insights", ""),
            positive_count=len(imported_jobs),
            negative_count=len(deleted_jobs),
            targeting=analysis.get("improved_targeting", {}),
            scoring_adjustments=analysis.get("scoring_adjustments", {}),
        )

    def record_deleted_job(self, job: dict, reason: str | None = None) -> None:
        """Record a deleted job for negative learning."""
        self.data_store.record_deleted_job(job, reason)

    def get_companies(self, location_slug: str) -> list[CompanySummary]:
        """Get previously scouted companies for a location.

        Args:
            location_slug: Location slug (e.g., "palo-alto-ca").

        Returns:
            List of CompanySummary models.
        """
        raw = self.data_store.get_companies(location_slug)
        return [CompanySummary(**c) for c in raw]

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _build_scout_prompt(
        self, location: str, seed_companies: list[str], count: int
    ) -> str:
        """Build the prompt for company scouting."""
        location_desc = get_location_description(location)

        seed_section = ""
        if seed_companies:
            seed_list = "\n".join(f"- {name}" for name in seed_companies)
            seed_section = f"""
Here are some seed companies I'm interested in. Include any that have presence in {location_desc}:
{seed_list}

Expand on this list with additional companies that match my criteria.
"""

        target_roles = self.config.get("preferences", {}).get(
            "target_roles",
            self.config.get("preferences", {}).get("roles", [
                "Engineering Manager",
                "Software Manager",
                "Technical Product Manager",
                "Director of Analytics Engineering",
            ]),
        )
        roles_text = "\n".join(f"- {role}" for role in target_roles)

        min_size = self.config.get("preferences", {}).get("min_company_size", 100)
        prefer_public = self.config.get("preferences", {}).get("prefer_public_companies", True)
        public_pref = (
            "Prefer public companies or well-funded late-stage startups"
            if prefer_public
            else "Consider both public and private companies"
        )

        return f"""Find {count} technology companies that have offices or presence in {location_desc}.

{seed_section}

Target roles I'm looking for:
{roles_text}

Preferences:
- {public_pref}
- Software should be a revenue driver for the company
- Strong engineering culture is important
- Minimum ~{min_size} employees

Return exactly {count} companies as JSON. Prioritize quality and fit over quantity."""

    def _analyze_combined(
        self, imported_jobs: list[dict], deleted_jobs: list[dict]
    ) -> dict | None:
        """Analyze both imported and deleted jobs together."""
        imported_text = json.dumps(imported_jobs, indent=2)
        deleted_text = json.dumps(deleted_jobs, indent=2)

        try:
            return self.client.complete_json(
                system=COMBINED_LEARNING_PROMPT,
                user=f"""Analyze this job search feedback:

## POSITIVE SIGNALS - {len(imported_jobs)} Imported Jobs (user WANTS more like these):
{imported_text}

## NEGATIVE SIGNALS - {len(deleted_jobs)} Deleted Jobs (user wants FEWER like these):
{deleted_text}

Generate comprehensive targeting improvements based on both positive and negative feedback.""",
                max_tokens=4096,
            )
        except ValueError as e:
            logger.error("Error analyzing combined feedback: %s", e)
            return None

    def _analyze_imported(self, jobs: list[dict]) -> dict | None:
        """Analyze only imported jobs."""
        jobs_text = json.dumps(jobs, indent=2)

        try:
            return self.client.complete_json(
                system=LEARNING_ANALYSIS_PROMPT,
                user=f"Analyze these {len(jobs)} manually imported job postings:\n\n{jobs_text}",
                max_tokens=4096,
            )
        except ValueError as e:
            logger.error("Error analyzing imported jobs: %s", e)
            return None

    def _analyze_deleted_only(self, deleted_jobs: list[dict]) -> dict | None:
        """Analyze only deleted jobs when no imports exist."""
        deleted_text = json.dumps(deleted_jobs, indent=2)

        try:
            result = self.client.complete_json(
                system=NEGATIVE_LEARNING_PROMPT,
                user=f"Analyze these {len(deleted_jobs)} deleted/rejected job postings:\n\n{deleted_text}",
                max_tokens=4096,
            )
        except ValueError as e:
            logger.error("Error analyzing deleted jobs: %s", e)
            return None

        if result:
            return {
                "analysis": {},
                "negative_analysis": result.get("rejection_patterns", {}),
                "improved_targeting": {
                    "titles_to_avoid": result.get("rejection_patterns", {}).get(
                        "title_patterns_to_avoid", []
                    ),
                    "red_flag_keywords": result.get("score_penalties", {}).get(
                        "title_keywords", []
                    )
                    + result.get("score_penalties", {}).get("requirement_keywords", []),
                },
                "scoring_adjustments": {"penalty_factors": result.get("score_penalties", {})},
                "prompt_improvements": result.get("prompt_adjustments", {}),
                "insights": result.get("insights", ""),
            }
        return None

    def _save_preferences(
        self, analysis: dict, imported_jobs: list[dict], deleted_jobs: list[dict] | None = None
    ) -> None:
        """Save learned preferences to file."""
        deleted_jobs = deleted_jobs or []

        preferences = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "based_on_imported": len(imported_jobs),
            "based_on_deleted": len(deleted_jobs),
            "imported_job_ids": [j["id"] for j in imported_jobs],
            "deleted_job_ids": [j["id"] for j in deleted_jobs],
            "positive_analysis": analysis.get("positive_analysis", analysis.get("analysis", {})),
            "negative_analysis": analysis.get("negative_analysis", {}),
            "improved_targeting": analysis.get("improved_targeting", {}),
            "scoring_adjustments": analysis.get("scoring_adjustments", {}),
            "prompt_improvements": analysis.get("prompt_improvements", {}),
            "insights": analysis.get("insights", ""),
        }

        self.data_store.save_learned_preferences(preferences)
        logger.info("Saved learned preferences")

    def _slugify(self, name: str) -> str:
        """Convert company name to slug."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug
