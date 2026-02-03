"""Resume Generator Skill - generates customized resumes with two-pass refinement."""

import json
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillContext, SkillResult


RESUME_GENERATION_PROMPT = """You are an expert resume writer. Create a customized resume tailored to a specific job posting.

Guidelines:
- Maintain truthfulness - only use information from the base resume
- Reorder and emphasize relevant experience
- Incorporate keywords from the job posting naturally
- Keep to 1-2 pages maximum
- Use action verbs and quantified achievements
- Tailor the professional summary to the target role

Output the resume in clean Markdown format with clear sections:
- Contact info header
- Professional Summary (3-4 sentences tailored to this role)
- Professional Experience (reverse chronological)
- Education
- Additional relevant sections as needed

Global constraints:
- Avoid generic phrases (e.g., "proven track record," "results-driven," "dynamic leader").
- Do NOT overemphasize years of experience or education.
- Do NOT list tools or frameworks unless they were used in production systems I owned or led.
- Prefer outcomes, constraints, and decisions over responsibilities.

PROFESSIONAL EXPERIENCE
- Treat my current and most recent role as the primary anchor.
- For each role, include 3–6 bullets max.
- Each bullet should describe:
  - a concrete system, process, or organizational change I owned or led
  - the constraint or problem it addressed
  - the measurable or observable outcome
- At least one bullet per role should reflect people leadership or organizational design.
- Use action-oriented language, but avoid resume clichés.

EDUCATION
- Include degrees succinctly at the end without emphasis.

Formatting:
- Use clear section headers.
- Keep bullets concise but specific.
- Output only the resume in Markdown.

Do NOT invent experiences or skills not in the base resume. Only reorganize and reframe existing content."""

RESUME_DEFENSIBILITY_PROMPT = """You are a rigorous resume editor ensuring authenticity and defensibility.

Your task: Review the resume below and identify any content that:
1. Sounds too generic or could appear on anyone's resume
2. Unrealistically mirrors the job description (keyword stuffing or parroting requirements)
3. Makes claims that couldn't be defended in an interview
4. Uses inflated language that overstates actual responsibilities
5. Lists skills or technologies without evidence of real usage in the experience section
6. Lists a core skills section without adding much value to the overall impact of the resume

For each problematic element:
- REWRITE it to be specific, grounded, and defensible
- REMOVE it if it adds no real value or can't be substantiated
- TONE DOWN language that sounds like marketing copy

Red flags to fix:
- "Expert in X" without specific examples → Either add the example or use "experienced with"
- "Led transformation of..." without concrete details → Add what specifically changed
- Skills listed that don't appear in any job bullet → Remove or add supporting evidence
- Metrics that seem invented or rounded too neatly → Make more realistic or remove
- Buzzwords from the job posting that weren't in the original resume → Remove unless genuinely applicable
- Superlatives like "exceptional," "outstanding," "best-in-class" → Replace with factual descriptions
- Remove the Core Skills or Core Capabilities section if it does not provide an essential value to the role at hand

The goal: A hiring manager should be able to ask about ANY line on this resume and receive a concrete, honest answer. Nothing should require backpedaling or clarification in an interview.

Rules:
- Preserve the structure and formatting
- Keep all genuinely specific achievements, metrics, and examples
- Check that the resume presents work history in chronological order
- The candidate should be able to speak confidently to every single bullet point
- Output ONLY the revised resume in Markdown (no explanations)"""

RESUME_IMPROVE_PROMPT = """You are an expert technical recruiter and hiring manager with deep experience reviewing senior engineering, data, product, and technical leadership resumes.

Your task is to iteratively evaluate and improve a resume so that it is well-aligned with a specific job description while remaining credible, accurate, and professional.

Follow this process exactly:

STEP 1 — Analyze Job Description
- Identify the core responsibilities, required skills, preferred qualifications, seniority expectations, and success signals.
- Summarize the role's implicit evaluation criteria (what a hiring manager actually cares about).

STEP 2 — Evaluate Resume Against Job Description
- Assess alignment across the following dimensions:
  - Role fit and seniority
  - Technical depth and relevance
  - Scope, ownership, and impact
  - Leadership and cross-functional influence
  - Domain familiarity
- Explicitly identify:
  - Strong matches
  - Partial matches
  - Gaps or weak signals
  - Content that is off-target or distracting

STEP 3 — Identify Improvement Opportunities
- Propose concrete, high-impact opportunities to improve alignment.
- Focus on:
  - Reframing existing experience (do NOT invent experience)
  - Clarifying scope, ownership, or outcomes
  - Improving emphasis, ordering, or wording
  - Removing or de-emphasizing irrelevant content
- Avoid generic advice. Each recommendation must map directly to a job requirement.

STEP 4 — Iteratively Revise the Resume
- Apply the proposed improvements directly to the resume.
- Preserve factual accuracy and credibility at all times.
- Do not exaggerate titles, scope, or responsibilities.
- Prefer precision and clarity over buzzwords.
- After each revision pass:
  - Re-evaluate the updated resume against the job description.
  - Identify remaining gaps or misalignments.
  - Make additional targeted revisions if warranted.

STEP 5 — Stopping Criteria
- Stop iterating only when ALL of the following are true:
  - The resume is strongly aligned with the job description's core requirements
  - The narrative is coherent, senior-appropriate, and compelling
  - No material gaps remain that can be addressed without fabricating experience
  - The resume would be credible and competitive if reviewed by a hiring manager for this role

CONSTRAINTS:
- Do not invent experience.
- Do not misrepresent titles, timelines, or scope.
- Do not optimize for keyword stuffing.
- Optimize for clarity, credibility, and role fit.

OUTPUT FORMAT:
Return your response as valid JSON:
{
  "improvement_summary": [
    "bullet point explaining a key change made",
    "bullet point explaining why the resume is now better suited",
    "bullet point noting any remaining limitations"
  ],
  "revised_resume": "The complete revised resume in Markdown format"
}"""


@dataclass
class ResumeGenerationResult:
    """Result of resume generation."""

    resume_markdown: str
    """Generated resume in Markdown format."""

    role_lens: str
    """Role lens used for generation."""


@dataclass
class ResumeImprovementResult:
    """Result of resume improvement."""

    resume_markdown: str
    """Improved resume in Markdown format."""

    improvement_summary: list[str]
    """Summary of improvements made."""


class ResumeGeneratorSkill(BaseSkill):
    """Skill that generates customized resumes with two-pass refinement."""

    def execute(
        self,
        context: SkillContext,
        job: dict,
        base_resume: str,
        analysis: dict | None = None,
        role_lens: str = "engineering",
    ) -> SkillResult:
        """Generate a customized resume for a job.

        Args:
            context: Execution context with config and learned preferences.
            job: Job dictionary with posting details.
            base_resume: Base resume text.
            analysis: Optional analysis from JobDescriptionAnalyzerSkill.
            role_lens: Role lens for tailoring (engineering/product/program).

        Returns:
            SkillResult with ResumeGenerationResult data.
        """
        # First pass: Generate resume
        resume_md = self._generate_resume_content(job, base_resume, analysis, role_lens)
        if not resume_md:
            return SkillResult.fail("Failed to generate resume content")

        # Second pass: Review for defensibility
        resume_md = self._refine_resume_defensibility(resume_md, job, base_resume)

        result = ResumeGenerationResult(
            resume_markdown=resume_md,
            role_lens=role_lens,
        )

        return SkillResult.ok(result)

    def improve_resume(
        self,
        context: SkillContext,
        job: dict,
        current_resume: str,
        base_resume: str,
    ) -> SkillResult:
        """Iteratively improve an existing resume.

        Args:
            context: Execution context.
            job: Job dictionary.
            current_resume: Current resume markdown to improve.
            base_resume: Original base resume for reference.

        Returns:
            SkillResult with ResumeImprovementResult data.
        """
        job_context = self._build_job_context(job)

        try:
            result = self.client.complete_json(
                system=RESUME_IMPROVE_PROMPT,
                user=f"""Improve this resume to better align with the target job.

TARGET JOB:
{job_context}

CURRENT TAILORED RESUME:
{current_resume}

BASE RESUME (original facts - do not invent beyond this):
{base_resume}

Analyze the current resume against the job requirements, identify improvement opportunities, and iteratively revise until the resume is strongly aligned with the job while remaining credible and defensible.""",
                max_tokens=8000,
            )
        except ValueError as e:
            return SkillResult.fail(f"Failed to parse improvement response: {e}")

        improved_resume = result.get("revised_resume", "")
        improvement_summary = result.get("improvement_summary", [])

        if not improved_resume:
            return SkillResult.fail("No improved resume in response")

        improvement_result = ResumeImprovementResult(
            resume_markdown=improved_resume,
            improvement_summary=improvement_summary,
        )

        return SkillResult.ok(improvement_result)

    def _generate_resume_content(
        self, job: dict, resume_text: str, analysis: dict | None, role_lens: str
    ) -> str | None:
        """Generate customized resume content."""
        job_text = json.dumps(job, indent=2)
        analysis_text = json.dumps(analysis, indent=2) if analysis else "No prior analysis"

        # Role-lens specific guidance
        role_lens_guidance = self._get_role_lens_guidance(role_lens, "resume")

        response = self.client.complete(
            system=RESUME_GENERATION_PROMPT,
            user=f"""Create a customized resume for this job:

## TARGET JOB:
{job_text}

## ROLE LENS: {role_lens.upper()}
{role_lens_guidance}

## BASE RESUME (source material - use only this information):
{resume_text}

## ANALYSIS & RECOMMENDATIONS:
{analysis_text}

Ensure that the Professional Summary and the resume overall reflect the {role_lens} lens.

Generate a tailored resume in Markdown format.
.""",
            max_tokens=4096,
        )

        return response

    def _refine_resume_defensibility(self, resume: str, job: dict, base_resume: str) -> str:
        """Second pass: review resume for defensibility and remove generic/inflated content."""
        job_text = json.dumps(job, indent=2)

        return self.client.complete(
            system=RESUME_DEFENSIBILITY_PROMPT,
            user=f"""Review this tailored resume for defensibility and authenticity.

## TARGET JOB (for context on what might be keyword-stuffed):
{job_text}

## ORIGINAL BASE RESUME (ground truth - what the candidate actually did):
{base_resume}

## TAILORED RESUME TO REVIEW:
{resume}

Ensure every claim is defensible and grounded in the original resume. Remove or tone down anything that sounds inflated or mirrors the job description too closely. Output only the refined resume in Markdown.""",
            max_tokens=4096,
        )

    def _get_role_lens_guidance(self, role_lens: str, doc_type: str) -> str:
        """Return role-lens specific guidance for resume generation."""
        guidance = {
            "engineering": {
                "resume": """This is an ENGINEERING role. Emphasize:
- Technical systems architecture and ownership
- Code, infrastructure, and platform decisions
- Scaling engineering teams and establishing technical practices
- Production reliability, observability, and operational excellence
- AI/ML systems from experimentation to production deployment
- Technical mentorship and growing engineers""",
            },
            "product": {
                "resume": """This is a PRODUCT role. Emphasize:
- Product strategy, vision, and roadmap ownership
- Customer outcomes and business metrics
- Cross-functional leadership with engineering, design, sales
- Data-driven decision making and experimentation
- Market analysis and competitive positioning
- Prioritization frameworks and trade-off decisions""",
            },
            "program": {
                "resume": """This is a PROGRAM role. Emphasize:
- Cross-functional coordination and delivery execution
- Stakeholder management across engineering, product, leadership
- Process design, risk management, and dependency tracking
- Program-level metrics, reporting, and visibility
- Driving alignment and unblocking teams
- Launch coordination and operational readiness""",
            }
        }
        return guidance.get(role_lens, guidance["engineering"]).get(doc_type, "")

    def _build_job_context(self, job: dict) -> str:
        """Build a comprehensive job context string for prompts."""
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
