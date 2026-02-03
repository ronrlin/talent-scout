"""Opportunity Scout Agent - company discovery, job search, and learning feedback loop."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from config_loader import (
    get_location_slug,
    get_location_description,
    get_locations,
    is_remote_enabled,
)
from data_store import DataStore
from skills import (
    CompanyResearcherSkill,
    JobPostingRetrieverSkill,
    JobDescriptionAnalyzerSkill,
    SkillContext,
)
from .base_agent import BaseAgent

console = Console()

# ============================================================================
# Company Scouting Prompts
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

# ============================================================================
# Learning Prompts
# ============================================================================

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


class OpportunityScoutAgent(BaseAgent):
    """Agent that handles company discovery, job search, and learning feedback.

    Consolidates functionality from:
    - CompanyScoutAgent (scout_companies)
    - CompanyResearcherAgent (research_company)
    - JobImporter (import_job_from_url, import_job_from_markdown)
    - LearningAgent (learn_from_feedback)
    """

    def __init__(self, config: dict):
        """Initialize the opportunity scout agent.

        Args:
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.data_store = DataStore(config)

        # Initialize skills
        self.company_researcher = CompanyResearcherSkill(
            self.client, self.data_store, config
        )
        self.job_retriever = JobPostingRetrieverSkill(
            self.client, self.data_store, config
        )
        self.job_analyzer = JobDescriptionAnalyzerSkill(
            self.client, self.data_store, config
        )

    # =========================================================================
    # Company Scouting
    # =========================================================================

    def scout_companies(self, location: str, count: int = 15) -> list[dict]:
        """Scout companies for a given location.

        Args:
            location: Target location (e.g., "Palo Alto, CA" or "remote").
            count: Number of companies to find.

        Returns:
            List of company dictionaries sorted by priority score.
        """
        # Get seed companies
        target_companies = self.config.get("target_companies", [])
        excluded_companies = self.config.get("excluded_companies", [])
        excluded_names = {c["name"].lower() for c in excluded_companies}

        # Filter seed companies relevant to this location
        seed_names = [c["name"] for c in target_companies]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Researching companies for {location}...", total=None
            )

            # Build prompt with learned preferences
            prompt = self._build_scout_prompt(location, seed_names, count)
            system_prompt = SCOUT_SYSTEM_PROMPT + self._build_learned_context("company_scout")

            # Call Claude
            try:
                result = self.client.complete_json(
                    system=system_prompt,
                    user=prompt,
                    max_tokens=4096,
                )
                companies = result.get("companies", [])
            except ValueError as e:
                console.print(f"[red]Error parsing response: {e}[/red]")
                companies = []

            progress.update(task, description="Processing results...")

            # Filter excluded companies
            companies = [
                c for c in companies if c["name"].lower() not in excluded_names
            ]

            # Sort by priority score
            companies.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

            # Limit to requested count
            companies = companies[:count]

        # Save results
        slug = get_location_slug(location)
        self.data_store.save_companies(companies, slug, location)
        console.print(f"[dim]Saved to data/companies-{slug}.json[/dim]")

        # Print summary
        self._print_companies_summary(companies)

        return companies

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

        # Get target roles from config
        target_roles = self.config.get("preferences", {}).get(
            "target_roles",
            [
                "Engineering Manager",
                "Software Manager",
                "Technical Product Manager",
                "Director of Analytics Engineering",
            ],
        )
        roles_text = "\n".join(f"- {role}" for role in target_roles)

        # Get company preferences
        min_size = self.config.get("preferences", {}).get("min_company_size", 100)
        prefer_public = self.config.get("preferences", {}).get(
            "prefer_public_companies", True
        )
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

    def _print_companies_summary(self, companies: list[dict]) -> None:
        """Print a summary of found companies."""
        console.print("\n[bold]Top companies found:[/bold]")
        for i, company in enumerate(companies[:5], 1):
            score = company.get("priority_score", "?")
            public = "public" if company.get("public") else "private"
            console.print(
                f"  {i}. {company['name']} "
                f"[dim]({public}, score: {score})[/dim]"
            )

        if len(companies) > 5:
            console.print(f"  [dim]... and {len(companies) - 5} more[/dim]")

    # =========================================================================
    # Company Research
    # =========================================================================

    def research_company(self, company_name: str) -> dict:
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
            task = progress.add_task(f"Researching {company_name}...", total=None)

            # Build skill context
            context = SkillContext(
                config=self.config,
                learned_context=self._build_learned_context("job_search"),
            )

            # Execute company research skill
            result = self.company_researcher.execute(context, company_name)

            if not result.success:
                console.print(f"[red]Research failed: {result.error}[/red]")
                return {}

            research_data = result.data
            company_info = research_data.company_info
            jobs = research_data.jobs

            progress.update(task, description="Saving results...")

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
        console.print(f"[dim]Saved research to data/research/{slug}.json[/dim]")

        # Add jobs to location files
        if jobs:
            added = self.data_store.save_jobs(jobs, company_name)
            if added > 0:
                console.print(f"[dim]Added {added} job(s) to data files[/dim]")

        # Print summary
        self._print_research_summary(company_info, jobs)

        return full_result

    def _print_research_summary(self, company_info: dict, jobs: list[dict]) -> None:
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

    # =========================================================================
    # Job Import
    # =========================================================================

    def import_job_from_url(self, url: str) -> dict | None:
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
            task = progress.add_task("Importing job from URL...", total=None)

            # Build skill context
            context = SkillContext(
                config=self.config,
                learned_context=self._build_learned_context("job_scoring"),
            )

            # Execute job retriever skill
            result = self.job_retriever.execute(context, url=url)

            if not result.success:
                console.print(f"[red]{result.error}[/red]")
                return None

            job = result.data.job

            progress.update(task, description="Saving job...")

            # Save to data store
            self.data_store.save_job(job)

        # Print summary
        self._print_job_summary(job)

        return job

    def import_job_from_markdown(self, content: str, filename: str) -> dict | None:
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

            # Build skill context
            context = SkillContext(
                config=self.config,
                learned_context=self._build_learned_context("job_scoring"),
            )

            # Execute job retriever skill
            result = self.job_retriever.execute(
                context, content=content, filename=filename
            )

            if not result.success:
                console.print(f"[red]{result.error}[/red]")
                return None

            job = result.data.job

            progress.update(task, description="Saving job...")

            # Save to data store
            self.data_store.save_job(job)

        # Print summary
        self._print_job_summary(job)

        return job

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

    # =========================================================================
    # Job Analysis
    # =========================================================================

    def analyze_job(self, job_id: str, resume_text: str) -> dict | None:
        """Analyze a job posting and match against candidate profile.

        Args:
            job_id: ID of the job to analyze.
            resume_text: Candidate's resume text.

        Returns:
            Analysis dictionary or None if failed.
        """
        # Find the job
        job = self.data_store.get_job(job_id)
        if not job:
            console.print(f"[red]Job not found: {job_id}[/red]")
            return None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing job requirements...", total=None)

            # Build skill context
            context = SkillContext(config=self.config)

            # Execute job analyzer skill
            result = self.job_analyzer.execute(context, job, resume_text)

            if not result.success:
                console.print(f"[red]Analysis failed: {result.error}[/red]")
                return None

        return result.metadata.get("raw_analysis")

    # =========================================================================
    # Learning
    # =========================================================================

    def record_deleted_job(self, job: dict, reason: str | None = None) -> None:
        """Record a deleted job for negative learning.

        Args:
            job: The deleted job dictionary.
            reason: Optional reason for deletion.
        """
        self.data_store.record_deleted_job(job, reason)

    def learn_from_feedback(self) -> dict | None:
        """Analyze imported and deleted jobs to generate learning insights.

        Returns:
            Analysis dictionary or None if no feedback available.
        """
        # Collect all feedback
        imported_jobs = self.data_store.get_jobs(source="imported")
        deleted_jobs = self.data_store.get_deleted_jobs()

        if not imported_jobs and not deleted_jobs:
            console.print("[yellow]No feedback found. To improve targeting:[/yellow]")
            console.print("  - Import jobs you like: scout research <job_url>")
            console.print("  - Delete jobs you don't want: scout delete <job_id>")
            return None

        # Report what we're analyzing
        if imported_jobs:
            console.print(f"[bold]Positive signals:[/bold] {len(imported_jobs)} imported job(s)")
        if deleted_jobs:
            console.print(f"[bold]Negative signals:[/bold] {len(deleted_jobs)} deleted job(s)")
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing feedback patterns...", total=None)

            # Analyze with Claude - use combined prompt if we have both types
            if imported_jobs and deleted_jobs:
                analysis = self._analyze_combined(imported_jobs, deleted_jobs)
            elif imported_jobs:
                analysis = self._analyze_imported(imported_jobs)
            else:
                analysis = self._analyze_deleted_only(deleted_jobs)

            if not analysis:
                console.print("[red]Failed to analyze feedback[/red]")
                return None

            progress.update(task, description="Saving learned preferences...")

            # Save preferences
            self._save_preferences(analysis, imported_jobs, deleted_jobs)

        # Print summary
        self._print_learning_summary(analysis, has_deleted=bool(deleted_jobs))

        return analysis

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
            console.print(f"[red]Error analyzing combined feedback: {e}[/red]")
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
            console.print(f"[red]Error analyzing imported jobs: {e}[/red]")
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
            console.print(f"[red]Error analyzing deleted jobs: {e}[/red]")
            return None

        # Transform to standard format
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
        console.print(f"[dim]Saved learned preferences to data/learned-preferences.json[/dim]")

    def _print_learning_summary(self, analysis: dict, has_deleted: bool = False) -> None:
        """Print analysis summary."""
        insights = analysis.get("insights", "No insights generated")
        targeting = analysis.get("improved_targeting", {})
        improvements = analysis.get("prompt_improvements", {})
        negative = analysis.get("negative_analysis", {})

        # Insights panel
        console.print(Panel(insights, title="Key Insights"))

        # Positive targeting recommendations
        primary = targeting.get("primary_titles", [])
        if primary:
            console.print("\n[bold green]Job Titles to Target:[/bold green]")
            for title in primary[:5]:
                console.print(f"  - {title}")

        must_have = targeting.get("must_have_keywords", [])
        if must_have:
            console.print("\n[bold green]Must-Have Keywords:[/bold green]")
            console.print(f"  {', '.join(must_have[:8])}")

        nice_to_have = targeting.get("nice_to_have_keywords", [])
        if nice_to_have:
            console.print("\n[bold]Nice-to-Have Keywords:[/bold]")
            console.print(f"  {', '.join(nice_to_have[:8])}")

        # Negative signals / things to avoid
        titles_to_avoid = targeting.get("titles_to_avoid", [])
        if titles_to_avoid:
            console.print("\n[bold red]Job Titles to Avoid:[/bold red]")
            for title in titles_to_avoid[:5]:
                console.print(f"  - {title}")

        red_flags = targeting.get("red_flag_keywords", [])
        if red_flags:
            console.print("\n[bold red]Red Flag Keywords (penalize):[/bold red]")
            console.print(f"  {', '.join(red_flags[:8])}")

        # Show negative analysis if we have deleted jobs
        if has_deleted and negative:
            role_red_flags = negative.get("role_red_flags", [])
            if role_red_flags:
                console.print("\n[bold red]Role Characteristics to Avoid:[/bold red]")
                for flag in role_red_flags[:4]:
                    console.print(f"  - {flag}")

        # Scoring adjustments
        scoring = analysis.get("scoring_adjustments", {})
        if scoring:
            boost = scoring.get("boost_factors", [])
            penalty = scoring.get("penalty_factors", [])
            if boost or penalty:
                console.print("\n[bold]Scoring Adjustments:[/bold]")
                if boost:
                    console.print(
                        f"  [green]Boost:[/green] {', '.join(boost[:4]) if isinstance(boost, list) else 'configured'}"
                    )
                if penalty:
                    console.print(
                        f"  [red]Penalize:[/red] {', '.join(penalty[:4]) if isinstance(penalty, list) else 'configured'}"
                    )

        # Prompt improvements
        if improvements:
            console.print("\n[bold]Prompt Improvements Generated:[/bold]")
            if improvements.get("job_search_additions"):
                console.print("  - Job search prompt enhancements")
            if improvements.get("job_search_exclusions"):
                console.print("  - Job search exclusion rules")
            if improvements.get("company_scout_additions"):
                console.print("  - Company scout prompt enhancements")
            if improvements.get("match_scoring_criteria"):
                console.print("  - Match scoring criteria updates")

        console.print("\n[green]Learning complete! Future searches will use these insights.[/green]")

    # =========================================================================
    # Helpers
    # =========================================================================

    def _slugify(self, name: str) -> str:
        """Convert company name to slug."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug
