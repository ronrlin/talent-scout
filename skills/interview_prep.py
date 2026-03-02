"""Interview Prep Skill - generates screening interview talking points and preparation notes."""

import json
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillContext, SkillResult, _load_reference

INTERVIEW_PREP_PROMPT = _load_reference("interview-prep-prompt.md")


@dataclass
class InterviewPrepResult:
    """Result of interview prep generation."""

    prep_markdown: str
    """Generated interview prep document in Markdown format."""

    section_count: int
    """Number of sections generated."""

    domain_connection_count: int
    """Number of domain connection talking points generated."""


class InterviewPrepSkill(BaseSkill):
    """Skill that generates screening interview preparation materials."""

    def execute(
        self,
        context: SkillContext,
        job: dict,
        base_resume: str,
        analysis: dict | None = None,
        role_lens: str = "engineering",
        company_research: dict | None = None,
    ) -> SkillResult:
        """Generate interview preparation talking points for a screening interview.

        Args:
            context: Execution context with config and learned preferences.
            job: Job dictionary with posting details.
            base_resume: Candidate's resume as plain text.
            analysis: Optional analysis from JobDescriptionAnalyzerSkill.
            role_lens: Role lens for tailoring (engineering/product/program).
            company_research: Optional company research data from scout research.

        Returns:
            SkillResult with InterviewPrepResult data.
        """
        # Build the user prompt with all available context
        user_prompt = self._build_user_prompt(
            job, base_resume, analysis, role_lens, company_research
        )

        try:
            prep_markdown = self.client.complete(
                system=INTERVIEW_PREP_PROMPT,
                user=user_prompt,
                max_tokens=6000,
            )
        except Exception as e:
            return SkillResult.fail(f"Failed to generate interview prep: {e}")

        if not prep_markdown:
            return SkillResult.fail("Empty interview prep result")

        # Count domain connections in the output
        domain_connection_count = self._count_domain_connections(analysis)

        # Count sections (## headers in the output)
        section_count = prep_markdown.count("\n## ")

        result = InterviewPrepResult(
            prep_markdown=prep_markdown,
            section_count=section_count,
            domain_connection_count=domain_connection_count,
        )

        return SkillResult.ok(result)

    def _build_user_prompt(
        self,
        job: dict,
        base_resume: str,
        analysis: dict | None,
        role_lens: str,
        company_research: dict | None,
    ) -> str:
        """Build the user prompt from all available context.

        Args:
            job: Job dictionary.
            base_resume: Candidate's resume text.
            analysis: Analysis data (may include domain_connections).
            role_lens: Role lens string.
            company_research: Optional company research data.

        Returns:
            Formatted user prompt string.
        """
        job_context = self._build_job_context(job)

        # Format analysis sections
        analysis_section = "No prior analysis available — generate domain connections from the resume and job posting."
        domain_connections_section = ""
        if analysis:
            match_assessment = analysis.get("match_assessment", {})

            # Extract domain connections separately for emphasis
            domain_connections = match_assessment.get("domain_connections", [])
            if domain_connections:
                dc_formatted = json.dumps(domain_connections, indent=2)
                domain_connections_section = f"""
## DOMAIN CONNECTIONS (use these as the PRIMARY backbone for talking points):
{dc_formatted}
"""
            else:
                domain_connections_section = """
## DOMAIN CONNECTIONS:
None provided in the analysis. Generate 2-3 domain connections by analyzing the resume against the job requirements. Look for analogous problems, shared algorithms, industry parallels, and operational overlaps.
"""

            analysis_section = json.dumps(analysis, indent=2)

        # Company research section (optional)
        research_section = ""
        if company_research:
            research_section = f"""
## COMPANY RESEARCH (use for "Why [Company]?" and "Areas to Probe"):
{json.dumps(company_research, indent=2)}
"""

        return f"""Generate screening interview preparation materials for this role.

## TARGET JOB:
{job_context}

## ROLE LENS: {role_lens.upper()}

## JOB ANALYSIS (match assessment, strengths, gaps, recommendations):
{analysis_section}
{domain_connections_section}
## CANDIDATE RESUME (ground truth — all facts must trace here):
{base_resume}
{research_section}
Generate the full interview prep document with all 6 sections. Every talking point must be grounded in the resume and analysis data above."""

    def _build_job_context(self, job: dict) -> str:
        """Build a comprehensive job context string for the prompt.

        Args:
            job: Job dictionary.

        Returns:
            Formatted job context string.
        """
        parts = []
        parts.append(f"Company: {job.get('company', 'Unknown')}")
        parts.append(f"Title: {job.get('title', 'Unknown')}")
        parts.append(f"Location: {job.get('location', 'Unknown')}")

        if job.get("requirements_summary"):
            parts.append(f"\nRequirements:\n{job.get('requirements_summary')}")

        if job.get("responsibilities_summary"):
            parts.append(f"\nResponsibilities:\n{job.get('responsibilities_summary')}")

        if job.get("match_notes"):
            parts.append(f"\nMatch Notes:\n{job.get('match_notes')}")

        return "\n".join(parts)

    def _count_domain_connections(self, analysis: dict | None) -> int:
        """Count domain connections available in the analysis.

        Args:
            analysis: Analysis data dictionary.

        Returns:
            Number of domain connections, or 0 if none.
        """
        if not analysis:
            return 0
        match_assessment = analysis.get("match_assessment", {})
        domain_connections = match_assessment.get("domain_connections", [])
        return len(domain_connections)
