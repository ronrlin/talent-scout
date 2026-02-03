"""Cover Letter Generator Skill - generates tailored cover letters with two-pass refinement."""

import json
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillContext, SkillResult


COVER_LETTER_PROMPT = """You are an expert cover letter writer. Create a compelling cover letter for a job application.

Guidelines:
- Professional and direct tone
- 3-4 paragraphs maximum
- Opening: Hook + why this company/role
- Middle: 2-3 key qualifications with specific examples from resume
- Closing: Call to action + enthusiasm

Output in clean Markdown format. Do NOT invent experiences not in the resume."""

COVER_LETTER_SPECIFICITY_PROMPT = """You are an expert editor focused on making cover letters highly specific and tailored.

Your task: Review the cover letter below and identify any sentence that could plausibly appear in a cover letter for a DIFFERENT company without modification.

For each such generic sentence, either:
1. REWRITE it to include specific details about the target company, role, or how the candidate's specific experience relates to THIS company's unique situation
2. REMOVE it entirely if it adds no specific value

Examples of GENERIC sentences to fix:
- "I am excited to apply for this position" → Remove or specify what about THIS role
- "My experience aligns well with your needs" → Name the specific experience and specific need
- "I would welcome the opportunity to discuss" → Too boilerplate, rewrite or cut
- "I am confident I can contribute to your team" → Generic confidence statement
- "Throughout my career, I have developed strong leadership skills" → Which career moments? What kind of leadership?

Examples of SPECIFIC sentences to KEEP:
- "At Tesla, I built an LLM-driven diagnostic system that reduced fleet troubleshooting time by 40%"
- "Your focus on multi-agent orchestration mirrors the distributed AI systems I architected at Waymo"
- "The Manager of AI & Analytics role's emphasis on Spark and distributed computing directly matches my work scaling data pipelines at Apple"

Rules:
- Maintain the same overall structure and flow
- Keep all specific company names, metrics, technologies, and concrete achievements
- The result should read as if it could ONLY be sent to this specific company
- Output ONLY the revised cover letter in Markdown (no explanations)"""


@dataclass
class CoverLetterGenerationResult:
    """Result of cover letter generation."""

    cover_letter_markdown: str
    """Generated cover letter in Markdown format."""

    role_lens: str
    """Role lens used for generation."""


class CoverLetterGeneratorSkill(BaseSkill):
    """Skill that generates tailored cover letters with two-pass refinement."""

    def execute(
        self,
        context: SkillContext,
        job: dict,
        base_resume: str,
        analysis: dict | None = None,
        role_lens: str = "engineering",
    ) -> SkillResult:
        """Generate a cover letter for a job.

        Args:
            context: Execution context with config and learned preferences.
            job: Job dictionary with posting details.
            base_resume: Base resume text.
            analysis: Optional analysis from JobDescriptionAnalyzerSkill.
            role_lens: Role lens for tailoring (engineering/product/program).

        Returns:
            SkillResult with CoverLetterGenerationResult data.
        """
        # First pass: Generate cover letter
        cover_letter_md = self._generate_cover_letter_content(
            job, base_resume, analysis, role_lens
        )
        if not cover_letter_md:
            return SkillResult.fail("Failed to generate cover letter content")

        # Second pass: Refine for specificity
        cover_letter_md = self._refine_cover_letter_specificity(cover_letter_md, job)

        result = CoverLetterGenerationResult(
            cover_letter_markdown=cover_letter_md,
            role_lens=role_lens,
        )

        return SkillResult.ok(result)

    def _generate_cover_letter_content(
        self, job: dict, resume_text: str, analysis: dict | None, role_lens: str
    ) -> str | None:
        """Generate cover letter content."""
        job_text = json.dumps(job, indent=2)
        analysis_text = json.dumps(analysis, indent=2) if analysis else "No prior analysis"

        # Role-lens specific guidance
        role_lens_guidance = self._get_role_lens_guidance(role_lens)

        response = self.client.complete(
            system=COVER_LETTER_PROMPT,
            user=f"""Create a cover letter for this job application:

## TARGET JOB:
{job_text}

## ROLE LENS: {role_lens.upper()}
{role_lens_guidance}

## CANDIDATE RESUME:
{resume_text}

## ANALYSIS (if available):
{analysis_text}

Generate a concise, high-signal cover letter in Markdown format.

The purpose of the letter is to demonstrate—through concrete examples—how my past decisions, systems, and leadership approach prepare me to succeed in the referenced role. The letter should read as authored by a senior {role_lens} leader, not as an expression of enthusiasm or a restatement of the job description.

Structural requirement:
- Begin with exactly ONE framing sentence that establishes the overarching problem space, leadership focus, or type of systems I have built or led.
- This opening sentence must be general (no company names, no job title, no praise for the employer) and should orient the reader to the examples that follow.
- After the opening sentence, immediately move into concrete experience.

Hard constraints:
- Do NOT use generic motivation or evaluation phrases (e.g., "I'm excited to apply," "drawn to your mission," "aligns well," "directly applicable," "ideal fit," "passionate about," "cutting-edge," "innovative").
- Do NOT paraphrase, summarize, or mirror the job description or company values. Assume the reader already knows them.
- Do NOT mention years of experience, education, or personal interest in the company.
- Avoid sentences that explicitly explain *why* an experience matches the role; show the experience and let the relevance be implicit.

Content requirements:
- Reference the job title naturally within a sentence (not as a heading or label).
- Write 2–3 short paragraphs total (excluding greeting and closing).
- Each paragraph must be anchored in a specific system, organizational change, or responsibility I owned or led.
- At least one paragraph should reflect people leadership or organizational design decisions.
- Avoid listing multiple technologies or skills in a single sentence.
- Apply the {role_lens} lens when selecting which experiences to highlight.

Style requirements:
- Vary paragraph structure and sentence rhythm; avoid repeating the same narrative pattern across paragraphs.
- Prefer concrete actions, constraints, and outcomes over abstractions or summaries.
- Use a confident, matter-of-fact professional tone (neither deferential nor sales-oriented).
- No header titled "Cover Letter."

Length:
- Approximately 200–300 words total.

Output only the cover letter in Markdown.""",
            max_tokens=2048,
        )

        return response

    def _refine_cover_letter_specificity(self, cover_letter: str, job: dict) -> str:
        """Second pass: review and rewrite generic sentences to be company-specific."""
        job_text = json.dumps(job, indent=2)

        return self.client.complete(
            system=COVER_LETTER_SPECIFICITY_PROMPT,
            user=f"""Review this cover letter and rewrite any generic sentences to be specific to this company and role.

## TARGET COMPANY/ROLE:
{job_text}

## COVER LETTER TO REFINE:
{cover_letter}

Output only the refined cover letter in Markdown.""",
            max_tokens=2048,
        )

    def _get_role_lens_guidance(self, role_lens: str) -> str:
        """Return role-lens specific guidance for cover letter generation."""
        guidance = {
            "engineering": """This is an ENGINEERING role. Frame experience around:
- Systems you built or architected and their technical constraints
- Engineering team leadership and scaling
- Production operations and reliability outcomes
- Technical decision-making and trade-offs""",
            "product": """This is a PRODUCT role. Frame experience around:
- Products you shaped and the customer/business outcomes
- Strategic decisions about what to build and why
- Working with engineering teams to deliver product value
- Metrics, experimentation, and iteration""",
            "program": """This is a PROGRAM role. Frame experience around:
- Complex programs you drove to completion
- Cross-functional coordination and stakeholder alignment
- Process improvements and delivery outcomes
- Risk identification and mitigation"""
        }
        return guidance.get(role_lens, guidance["engineering"])
