"""Cover Letter Generator Skill - generates tailored cover letters with two-pass refinement."""

import json
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillContext, SkillResult, _load_reference, _load_role_lens_guidance

COVER_LETTER_PROMPT = _load_reference("cover-letter-prompt.md")
COVER_LETTER_SPECIFICITY_PROMPT = _load_reference("cover-letter-specificity-prompt.md")


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
        guidance = _load_role_lens_guidance()
        role = guidance.get(role_lens, guidance.get("engineering", {}))
        return role.get("cover_letter", "")
