"""Job Description Analyzer Skill - analyzes job postings and matches against candidate profile."""

import json
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillContext, SkillResult

# Constrained set of role archetypes. Used in analysis prompt and validated after.
ROLE_ARCHETYPES = {
    "org_leadership": "VP/Director/Head of Eng — org-wide strategy, budget, culture",
    "team_leadership": "Engineering Manager — team building, delivery, people management",
    "tech_lead": "Staff/Principal/Architect — technical direction, system design, IC with influence",
    "product": "Product Manager/TPM — roadmap, stakeholder alignment, product outcomes",
    "data": "Data/Analytics Engineering — pipelines, warehouses, BI, data platforms",
    "ml": "ML/AI Engineering — model development, MLOps, applied AI systems",
    "infra": "Platform/Infra/SRE — cloud, DevOps, reliability, infrastructure",
    "ic": "Individual Contributor — hands-on software engineering, feature delivery",
}


JOB_ANALYSIS_PROMPT = """You are a senior job analysis and resume-optimization expert specializing in technical and technical-leadership roles across software engineering, data engineering, platform infrastructure, machine learning, applied AI, and product-oriented organizations.

Your goal is to deeply analyze a job description and a candidate’s base resume, then determine how to optimally position the candidate for this specific role—without inventing experience or misrepresenting scope.

OBJECTIVES
Analyze the job posting and the candidate’s resume to produce:
1. Key requirements extraction — what the company truly values
2. Match assessment — how strong the candidate is for this role
3. Gap analysis — real vs perceived gaps
4. Resume customization guidance — how to tune, not rewrite history

You must adapt your analysis to the scope and archetype of the role, which may include:
- Organization-level engineering leadership (multi-team ownership, strategy, execution systems)
- Team-level engineering management
- Tech lead or staff-level IC roles
- Product-oriented engineering leadership
- ML / applied AI roles
- Data engineering / platform / infrastructure roles

DEEP DOMAIN REASONING (REQUIRED)
Do NOT rely on surface-level keyword matching.

For each relevant candidate experience, reason explicitly about underlying problem equivalence. Ask:
- Is this an ANALOGOUS PROBLEM? (e.g., fleet service optimization vs ride dispatch)
- Is there a SHARED ALGORITHMIC PATTERN? (e.g., classification, forecasting, ranking, optimization)
- Is there an INDUSTRY PARALLEL? (e.g., energy fleets vs autonomous vehicles vs logistics)
- Is there OPERATIONAL OVERLAP? (e.g., real-time telemetry, SLAs, distributed systems, on-call reliability)

When making connections:
- Name the underlying problem type (optimization, prediction, control systems, decision support, resource allocation)
- Describe shared constraints, inputs, outputs, and failure modes
- Explain why a hiring manager should consider this experience equivalent

CONSTRAINTS & RULES
- Do NOT invent experience, scope, metrics, or technologies
- You MAY re-frame existing experience to better match the role
- Prefer clarity and credibility over exaggeration
- Assume the resume will be evaluated by both ATS systems and senior humans
- If a gap cannot be reasonably bridged, state that explicitly
- Jobs that do not align with geographic preferences should be penalized in the overall score

OUTPUT FORMAT (STRICT JSON)
Return your analysis in the following structure:

{
  "job_summary": {
    "title": "Job title",
    "company": "Company name",
    "role_archetype": "EXACTLY one of: org_leadership | team_leadership | tech_lead | product | data | ml | infra | ic",
    "business_mission": "What this role ultimately exists to achieve",
    "key_responsibilities": ["Top 5 responsibilities"],
    "required_skills": ["Must-have skills"],
    "preferred_skills": ["Nice-to-have skills"],
    "experience_required": "Years and type of experience",
    "education_required": "Education requirements"
  },
  "match_assessment": {
    "overall_score": 0-100,
    "strengths": ["Concrete reasons this candidate is a strong fit"],
    "gaps": ["Real gaps or weaker areas relative to the role"],
    "transferable_skills": ["Skills that clearly translate into this role"],
    "domain_connections": [
      {
        "candidate_experience": "Specific role or project",
        "target_domain": "Aspect of the target role",
        "connection_type": "analogous_problem | shared_algorithm | industry_parallel | operational_overlap",
        "underlying_problem_type": "e.g., optimization, classification, forecasting",
        "reasoning": "Why these are structurally the same problem"
      }
    ]
  },
  "resume_recommendations": {
    "positioning_strategy": "How the resume should be framed overall for this role",
    "skills_to_emphasize": ["Existing skills to foreground"],
    "experience_to_highlight": ["Specific bullets or roles to feature"],
    "keywords_to_include": ["ATS-relevant keywords from the job description"],
    "sections_to_adjust": ["Summary, Experience bullets, Skills section"],
    "language_shifts": ["Specific wording changes to improve alignment"]
  },
  "cover_letter_points": ["Key narrative points tailored to this role"],
  "interview_prep": ["Topics, tradeoffs, or examples to prepare"],
  "confidence_flags": ["Areas where the candidate should proactively control the narrative"]
}

QUALITY BAR
Be specific, concrete, and actionable.
Think like a hiring manager, recruiter, and senior engineer.
Optimize for credibility, not hype.
The output should enable resume revisions with minimal guesswork."""


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

        # Validate and normalize role_archetype to constrained set
        job_summary = analysis.get("job_summary", {})
        raw_archetype = job_summary.get("role_archetype", "").lower().strip()
        if raw_archetype not in ROLE_ARCHETYPES:
            # Default to team_leadership if Claude returned something unexpected
            job_summary["role_archetype"] = "team_leadership"
        else:
            job_summary["role_archetype"] = raw_archetype

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
