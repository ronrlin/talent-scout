"""Job Description Analyzer Skill - analyzes job postings and matches against candidate profile."""

import json
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillContext, SkillResult


JOB_ANALYSIS_PROMPT = """You are a job analysis expert helping a candidate understand a job posting and how well they match.

Analyze the job posting and the candidate's resume to provide:
1. Key requirements extraction
2. Match assessment
3. Gaps analysis
4. Customization recommendations

Return your analysis as JSON:
{
  "job_summary": {
    "title": "Job title",
    "company": "Company name",
    "key_responsibilities": ["top 5 responsibilities"],
    "required_skills": ["must-have skills"],
    "preferred_skills": ["nice-to-have skills"],
    "experience_required": "years and type of experience",
    "education_required": "education requirements"
  },
  "match_assessment": {
    "overall_score": 0-100,
    "strengths": ["candidate strengths that match this role"],
    "gaps": ["areas where candidate may be weak"],
    "transferable_skills": ["skills that translate well to this role"]
  },
  "resume_recommendations": {
    "skills_to_emphasize": ["skills from resume to highlight"],
    "experience_to_highlight": ["specific experiences to feature"],
    "keywords_to_include": ["ATS keywords from job posting to incorporate"],
    "sections_to_adjust": ["suggested section modifications"]
  },
  "cover_letter_points": ["key points to address in cover letter"],
  "interview_prep": ["topics to prepare for based on job requirements"]
}

Be specific and actionable. Focus on helping the candidate present themselves optimally for this role."""


@dataclass
class JobAnalysisResult:
    """Result of job analysis."""

    job_summary: dict
    """Summarized job information."""

    match_assessment: dict
    """Assessment of candidate-job fit."""

    resume_recommendations: dict
    """Recommendations for resume customization."""

    cover_letter_points: list[str]
    """Key points for cover letter."""

    interview_prep: list[str]
    """Topics to prepare for interviews."""

    role_lens: str
    """Determined role lens (engineering/product/program)."""


class JobDescriptionAnalyzerSkill(BaseSkill):
    """Skill that analyzes job descriptions and matches against candidate profiles."""

    def execute(
        self,
        context: SkillContext,
        job: dict,
        resume_text: str,
    ) -> SkillResult:
        """Analyze a job posting against a candidate's resume.

        Args:
            context: Execution context with config and learned preferences.
            job: Job dictionary with posting details.
            resume_text: Candidate's resume as plain text.

        Returns:
            SkillResult with JobAnalysisResult data.
        """
        # Determine role lens
        role_lens = self._determine_role_lens(job)

        # Analyze with Claude
        job_text = json.dumps(job, indent=2)

        try:
            analysis = self.client.complete_json(
                system=JOB_ANALYSIS_PROMPT,
                user=f"""Analyze this job posting and candidate resume:

## JOB POSTING:
{job_text}

## CANDIDATE RESUME:
{resume_text}

Provide a detailed match analysis and recommendations.""",
                max_tokens=4096,
            )
        except ValueError as e:
            return SkillResult.fail(f"Failed to analyze job: {e}")

        if not analysis:
            return SkillResult.fail("Empty analysis result")

        result = JobAnalysisResult(
            job_summary=analysis.get("job_summary", {}),
            match_assessment=analysis.get("match_assessment", {}),
            resume_recommendations=analysis.get("resume_recommendations", {}),
            cover_letter_points=analysis.get("cover_letter_points", []),
            interview_prep=analysis.get("interview_prep", []),
            role_lens=role_lens,
        )

        return SkillResult.ok(result, raw_analysis=analysis)

    def determine_role_lens(self, job: dict) -> str:
        """Determine the role lens for a job (public method).

        Args:
            job: Job dictionary.

        Returns:
            Role lens: "engineering", "product", or "program".
        """
        return self._determine_role_lens(job)

    def _determine_role_lens(self, job: dict) -> str:
        """Determine the role lens (engineering | product | program) based on job title and description."""
        title = job.get("title", "").lower()
        department = job.get("department", "").lower()

        # Check for product indicators
        product_keywords = ["product manager", "product lead", "product director", "tpm", "technical product"]
        if any(kw in title for kw in product_keywords):
            return "product"

        # Check for program indicators
        program_keywords = ["program manager", "program lead", "program director", "tpm", "technical program"]
        if any(kw in title for kw in program_keywords):
            return "program"

        # Check for engineering indicators
        engineering_keywords = [
            "engineering manager", "engineer", "software", "data engineer", "analytics engineer",
            "director of engineering", "vp engineering", "head of engineering", "staff engineer"
        ]
        if any(kw in title for kw in engineering_keywords):
            return "engineering"

        # Secondary check on department
        if "product" in department:
            return "product"
        if "program" in department:
            return "program"
        if "engineering" in department or "data" in department:
            return "engineering"

        # Default to engineering for technical roles
        return "engineering"

    def get_role_lens_guidance(self, role_lens: str, doc_type: str) -> str:
        """Get role-lens specific guidance for document generation.

        Args:
            role_lens: The role lens (engineering/product/program).
            doc_type: Document type ("resume" or "cover_letter").

        Returns:
            Guidance text for the specified role lens and document type.
        """
        guidance = {
            "engineering": {
                "resume": """This is an ENGINEERING role. Emphasize:
- Technical systems architecture and ownership
- Code, infrastructure, and platform decisions
- Scaling engineering teams and establishing technical practices
- Production reliability, observability, and operational excellence
- AI/ML systems from experimentation to production deployment
- Technical mentorship and growing engineers""",
                "cover_letter": """This is an ENGINEERING role. Frame experience around:
- Systems you built or architected and their technical constraints
- Engineering team leadership and scaling
- Production operations and reliability outcomes
- Technical decision-making and trade-offs"""
            },
            "product": {
                "resume": """This is a PRODUCT role. Emphasize:
- Product strategy, vision, and roadmap ownership
- Customer outcomes and business metrics
- Cross-functional leadership with engineering, design, sales
- Data-driven decision making and experimentation
- Market analysis and competitive positioning
- Prioritization frameworks and trade-off decisions""",
                "cover_letter": """This is a PRODUCT role. Frame experience around:
- Products you shaped and the customer/business outcomes
- Strategic decisions about what to build and why
- Working with engineering teams to deliver product value
- Metrics, experimentation, and iteration"""
            },
            "program": {
                "resume": """This is a PROGRAM role. Emphasize:
- Cross-functional coordination and delivery execution
- Stakeholder management across engineering, product, leadership
- Process design, risk management, and dependency tracking
- Program-level metrics, reporting, and visibility
- Driving alignment and unblocking teams
- Launch coordination and operational readiness""",
                "cover_letter": """This is a PROGRAM role. Frame experience around:
- Complex programs you drove to completion
- Cross-functional coordination and stakeholder alignment
- Process improvements and delivery outcomes
- Risk identification and mitigation"""
            }
        }
        return guidance.get(role_lens, guidance["engineering"]).get(doc_type, "")
