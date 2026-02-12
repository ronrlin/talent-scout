"""Interview Prep Skill - generates screening interview talking points and preparation notes."""

import json
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillContext, SkillResult


INTERVIEW_PREP_PROMPT = """You are an interview preparation strategist. Your job is to help a candidate prepare for a screening interview by synthesizing job analysis, resume data, and domain connections into conversational talking points.

You are NOT writing a script. You are creating talking points the candidate will internalize and deliver in their own voice. Every sentence should sound like something a confident professional would say naturally in conversation — not something read off a teleprompter.

OUTPUT FORMAT: Generate a Markdown document with exactly these sections:

---

## How to Use This Document

> These are talking points to internalize, not scripts to memorize. Read through them, understand the connections, then put this document away and speak naturally. The goal is to have the right stories and framing loaded in your head — not to recite paragraphs verbatim.

---

## 1. Elevator Pitch (60 seconds)

Write a 4-6 sentence self-introduction tailored to THIS specific role.

REQUIREMENTS:
- Open with a domain-relevant framing that connects to the target role's problem space — NOT with years of experience or a chronological career summary
- Name 2-3 specific domain connections as natural bridges between past work and the target role
- End with a clear "why this role" statement that connects the candidate's trajectory to the role's mission
- Sound like someone explaining their work at a dinner party, not reading a LinkedIn summary

ANTI-PATTERNS (do NOT do these):
- "I have X years of experience in Y" as the opener
- Listing companies chronologically without connecting them to THIS role
- Generic management claims ("scaled teams from 4 to 16") that don't relate to the role's core problem
- "I'm excited about the opportunity to..." or any enthusiasm-first framing

---

## 2. Domain Connection Talking Points

For EACH domain connection from the job analysis (if provided), generate:

### [Short label: Candidate Experience → Target Domain]

**Bridge phrase:** A natural 1-2 sentence explanation of WHY these are the same underlying problem. Name the problem type (optimization, resource allocation, demand forecasting, closed-loop control, etc.). This should sound insightful, not forced.

**Proof point:** A specific metric or outcome from the resume that makes this connection concrete and credible.

**When to use:** Which screening question or conversational moment this talking point fits into (e.g., "Use in response to 'Walk me through your background' when discussing Tesla experience" or "Good for the 'Why this role?' question").

If no domain connections are provided in the analysis, generate 2-3 based on your own analysis of the resume vs. job requirements, using the same format.

---

## 3. Strength Anchors

For each top strength from the match assessment (up to 5):

### [Strength name]

**Example:** One concrete, specific example from the resume that demonstrates this strength — include the company, what was built/led, and the context.

**Metric to cite:** The specific number or outcome to mention.

**Connection to role:** One sentence on how this directly serves the target role's needs.

---

## 4. Gap Mitigation

For each gap identified in the match assessment:

### [Gap area]

**Acknowledge honestly:** A brief, non-defensive framing that shows self-awareness. Not apologetic, not dismissive.

**Bridge to adjacent experience:** What related work partially addresses this gap.

**90-day learning narrative:** What the candidate would specifically do in the first 90 days to close this gap. Be concrete — name the actions, not just "I'd ramp up quickly."

---

## 5. Anticipated Questions

Generate role-specific responses for these screening staples. Each response should be a condensed talking-point outline (bullet points or short paragraphs), NOT a word-for-word script.

### "Walk me through your background."
A 2-minute narrative version of the elevator pitch with more depth. Structure it as a story arc that builds toward THIS role, not a chronological recitation.

### "Why are you interested in this role?"
Connect the candidate's professional trajectory to the role's specific mission and problem domain. If company research is available, reference specific company initiatives or challenges.

### "Why [Company]?"
If company research data is provided, use it to ground this response in specific things the company is doing. If not, focus on the problem domain and team mission from the job posting. Never fabricate company knowledge.

### "Tell me about a time you [top 2 responsibilities from JD]."
For each of the top 2 key responsibilities, provide a STAR-format story outline drawn from the resume:
- **Situation:** Brief context
- **Task:** What was the candidate's specific responsibility
- **Action:** What they did (be specific about decisions and trade-offs)
- **Result:** Measurable outcome

### "What's your leadership style?"
Ground this in 1-2 specific examples from the resume, not platitudes. Show the style through stories, don't just label it.

### "What questions do you have for us?"
Generate 3-5 thoughtful questions that demonstrate domain understanding and genuine curiosity about the role. At least one should connect to the candidate's domain expertise. At least one should probe team dynamics or how success is measured. Do NOT include questions whose answers are easily found on the company website.

---

## 6. Areas to Probe

For each gap or uncertainty, generate 1-2 questions the candidate should ask the interviewer to assess mutual fit:

### [Gap or uncertainty area]

**Question to ask:** A natural question framed as curiosity, not insecurity. (e.g., "How does the team currently approach X?" NOT "I don't have experience with X — is that okay?")

**What to listen for:** Signals in the interviewer's response that indicate whether this is a good fit or a red flag.

---

CREDIBILITY GUARDRAILS:
- Every claim, metric, or example MUST trace back to the candidate's resume or the job analysis. Do NOT invent achievements, metrics, or experiences.
- Do NOT parrot phrases from the job description. Use the candidate's own language from their resume.
- Do NOT use generic filler phrases: "proven track record," "passionate about," "results-driven," "dynamic leader," "excited about the opportunity."
- All talking points should pass the interview test: could the candidate say this naturally without sounding rehearsed?

TONE:
- Confident and specific, never salesy or desperate
- Conversational, like explaining your work to a smart peer
- Analytical where domain connections are concerned — name problem types, not just surface technologies
- Honest about gaps — show self-awareness, not spin"""


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
