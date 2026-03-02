"""Resume Generator Skill - generates customized resumes with two-pass refinement."""

import json
import re
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillContext, SkillResult, _load_reference, _load_role_lens_guidance

RESUME_GENERATION_PROMPT = _load_reference("resume-generation-prompt.md")
RESUME_DEFENSIBILITY_PROMPT = _load_reference("resume-defensibility-prompt.md")
RESUME_EDIT_PLAN_PROMPT = _load_reference("resume-edit-plan-prompt.md")
RESUME_EDIT_AUDIT_PROMPT = _load_reference("resume-edit-audit-prompt.md")


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
        additional_context: str | None = None,
    ) -> SkillResult:
        """Generate a customized resume for a job.

        Args:
            context: Execution context with config and learned preferences.
            job: Job dictionary with posting details.
            base_resume: Base resume text.
            analysis: Optional analysis from JobDescriptionAnalyzerSkill.
            role_lens: Role lens for tailoring (engineering/product/program).
            additional_context: Supplementary experience bullets (real but not on base resume).

        Returns:
            SkillResult with ResumeGenerationResult data.
        """
        # First pass: Generate resume
        resume_md = self._generate_resume_content(
            job, base_resume, analysis, role_lens, additional_context
        )
        if not resume_md:
            return SkillResult.fail("Failed to generate resume content")

        # Second pass: Review for defensibility
        resume_md = self._refine_resume_defensibility(
            resume_md, job, base_resume, additional_context
        )

        result = ResumeGenerationResult(
            resume_markdown=resume_md,
            role_lens=role_lens,
        )

        return SkillResult.ok(result)

    def plan_resume_edits(
        self,
        context: SkillContext,
        job: dict,
        current_resume: str,
        base_resume: str,
        analysis: dict | None = None,
        role_lens: str = "engineering",
        positioning_strategy: str | None = None,
        role_archetype: str | None = None,
        additional_context: str | None = None,
    ) -> SkillResult:
        """Phase 1: Generate a structured edit plan for resume improvement.

        Args:
            context: Execution context.
            job: Job dictionary.
            current_resume: Current resume markdown.
            base_resume: Original base resume for reference.
            analysis: Analysis from scout analyze (match assessment, recommendations).
            role_lens: Role lens for strategic framing.
            positioning_strategy: How to position the candidate for this role.
            role_archetype: Role archetype from job analysis (e.g., org_leadership).
            additional_context: Supplementary experience bullets (real but not on base resume).

        Returns:
            SkillResult with edit plan dict as data.
        """
        job_context = self._build_job_context(job)
        role_lens_guidance = self._get_role_lens_guidance(role_lens, "resume")

        # Format analysis data for the prompt
        analysis_section = "No prior analysis available."
        if analysis:
            analysis_section = json.dumps(analysis, indent=2)

        # Build positioning context for Professional Summary guidance
        positioning_section = ""
        if positioning_strategy or role_archetype:
            positioning_section = "\n## POSITIONING GUIDANCE FOR PROFESSIONAL SUMMARY:\n"
            if role_archetype:
                positioning_section += f"Role archetype: {role_archetype}\n"
            if positioning_strategy:
                positioning_section += f"Positioning strategy: {positioning_strategy}\n"
            positioning_section += "The Professional Summary should lead with the emphasis described above, NOT default to the base resume's framing. The summary is a positioning statement tailored to this role.\n"

        # Build additional context section if provided
        additional_context_section = ""
        if additional_context:
            additional_context_section = f"""
## ADDITIONAL CONTEXT (supplementary real experiences — valid source material for edits):
These are real experiences the candidate has but that are NOT on the base resume.
They can be used as source material for "add" edits or to enrich "replace" edits.
When using this material, cite it in source_evidence as "Additional context: [relevant line]".

{additional_context}
"""

        try:
            result = self.client.complete_json(
                system=RESUME_EDIT_PLAN_PROMPT,
                user=f"""Propose surgical edits to improve this resume's alignment with the target job.

## TARGET JOB:
{job_context}

## ROLE LENS: {role_lens.upper()}
{role_lens_guidance}
{positioning_section}
## JOB ANALYSIS (match assessment, gaps, and recommendations):
{analysis_section}

## CURRENT TAILORED RESUME (the document to edit — current_text must match exactly):
{current_resume}

## BASE RESUME (ground truth — all facts must trace here):
{base_resume}
{additional_context_section}
Propose 3-8 high-impact edits. Remember: most of the resume should remain unchanged.""",
                max_tokens=4096,
            )
        except ValueError as e:
            return SkillResult.fail(f"Failed to parse edit plan response: {e}")

        # Validate edit plan structure
        edit_plan = result.get("edit_plan", [])
        if not edit_plan:
            return SkillResult.fail("No edits proposed in edit plan")

        # Hard cap at 8 edits
        if len(edit_plan) > 8:
            edit_plan = edit_plan[:8]
            result["edit_plan"] = edit_plan

        return SkillResult.ok(result)

    def apply_resume_edits(
        self,
        current_resume: str,
        edit_plan: dict,
    ) -> SkillResult:
        """Phase 2: Apply edit plan to resume programmatically.

        Uses string matching for replacements, with fuzzy matching fallback.
        Reports which edits were applied vs. which failed.

        Args:
            current_resume: Current resume markdown.
            edit_plan: Edit plan dict from Phase 1.

        Returns:
            SkillResult with {"resume": str, "report": list[dict]}.
        """
        edits = edit_plan.get("edit_plan", [])
        resume = current_resume
        report = []

        for edit in edits:
            edit_type = edit.get("edit_type", "replace")
            target = edit.get("target", "")
            current_text = edit.get("current_text", "")
            proposed_text = edit.get("proposed_text", "")

            if edit_type == "replace":
                result = self._apply_replacement(resume, current_text, proposed_text)
                if result is not None:
                    resume = result
                    report.append({"target": target, "edit_type": "replace", "applied": True})
                else:
                    # Try fuzzy match with normalized whitespace
                    result = self._apply_fuzzy_replacement(resume, current_text, proposed_text)
                    if result is not None:
                        resume = result
                        report.append({"target": target, "edit_type": "replace", "applied": True, "method": "fuzzy"})
                    else:
                        report.append({
                            "target": target,
                            "edit_type": "replace",
                            "applied": False,
                            "reason": "current_text not found in resume",
                        })

            elif edit_type == "add":
                result = self._apply_addition(resume, edit)
                if result is not None:
                    resume = result
                    report.append({"target": target, "edit_type": "add", "applied": True})
                else:
                    report.append({
                        "target": target,
                        "edit_type": "add",
                        "applied": False,
                        "reason": "Could not find insertion point",
                    })

            elif edit_type == "remove":
                result = self._apply_removal(resume, current_text)
                if result is not None:
                    resume = result
                    report.append({"target": target, "edit_type": "remove", "applied": True})
                else:
                    report.append({
                        "target": target,
                        "edit_type": "remove",
                        "applied": False,
                        "reason": "current_text not found in resume",
                    })

        # Handle failed edits via Claude fallback
        failed_edits = [
            (i, edit) for i, (edit, r) in enumerate(zip(edits, report))
            if not r.get("applied")
        ]

        if failed_edits:
            fallback_result = self._apply_edits_via_claude(resume, failed_edits)
            if fallback_result:
                resume = fallback_result
                for i, _ in failed_edits:
                    report[i]["applied"] = True
                    report[i]["method"] = "claude_fallback"
                    report[i].pop("reason", None)

        return SkillResult.ok({"resume": resume, "report": report})

    def audit_resume_edits(
        self,
        context: SkillContext,
        modified_resume: str,
        original_resume: str,
        base_resume: str,
        job: dict,
        edit_plan: dict,
        positioning_strategy: str | None = None,
        role_archetype: str | None = None,
        additional_context: str | None = None,
    ) -> SkillResult:
        """Phase 3: Credibility audit on changed lines only.

        Args:
            context: Execution context.
            modified_resume: Resume after Phase 2 edits.
            original_resume: Resume before any edits.
            base_resume: Original base resume.
            job: Job dictionary.
            edit_plan: Edit plan from Phase 1.
            positioning_strategy: How to position the candidate for this role.
            role_archetype: Role archetype from job analysis (e.g., org_leadership).
            additional_context: Supplementary experience bullets (real but not on base resume).

        Returns:
            SkillResult with {"resume": str, "report": list[str]}.
        """
        job_context = self._build_job_context(job)
        edits = edit_plan.get("edit_plan", [])

        # Build a summary of what changed for the auditor
        changes_summary = []
        for edit in edits:
            edit_type = edit.get("edit_type", "replace")
            target = edit.get("target", "")
            if edit_type == "replace":
                changes_summary.append(
                    f"[{edit_type.upper()}] {target}\n"
                    f"  Before: {edit.get('current_text', '')}\n"
                    f"  After: {edit.get('proposed_text', '')}"
                )
            elif edit_type == "add":
                changes_summary.append(
                    f"[ADD] {target}\n"
                    f"  New text: {edit.get('proposed_text', '')}"
                )
            elif edit_type == "remove":
                changes_summary.append(
                    f"[REMOVE] {target}\n"
                    f"  Removed: {edit.get('current_text', '')}"
                )

        # Build positioning context so auditor knows the intended summary direction
        positioning_section = ""
        if positioning_strategy or role_archetype:
            positioning_section = "\n## POSITIONING GUIDANCE (for Professional Summary audit):\n"
            if role_archetype:
                positioning_section += f"Role archetype: {role_archetype}\n"
            if positioning_strategy:
                positioning_section += f"Intended positioning: {positioning_strategy}\n"
            positioning_section += "Summary edits that align with this positioning should be passed, not softened back toward the base resume's framing.\n"

        # Build additional context section if provided
        additional_context_section = ""
        if additional_context:
            additional_context_section = f"""
## ADDITIONAL CONTEXT (supplementary real experiences — also valid ground truth):
Claims sourced from this material ARE credible and should pass the credibility check.

{additional_context}
"""

        try:
            result = self.client.complete_json(
                system=RESUME_EDIT_AUDIT_PROMPT,
                user=f"""Audit these resume edits for credibility and naturalness.

## TARGET JOB (to check for parroting):
{job_context}

## BASE RESUME (ground truth):
{base_resume}
{additional_context_section}{positioning_section}
## EDITS THAT WERE APPLIED:
{chr(10).join(changes_summary)}

## MODIFIED RESUME (after edits):
{modified_resume}

Review ONLY the changed lines. Do not touch anything else.""",
                max_tokens=4096,
            )
        except ValueError as e:
            return SkillResult.fail(f"Failed to parse audit response: {e}")

        # Apply audit fixes
        resume = modified_resume
        audit_results = result.get("audit_results", [])
        audit_summary = result.get("audit_summary", [])

        for audit_item in audit_results:
            verdict = audit_item.get("verdict", "pass")
            if verdict == "soften":
                revised = audit_item.get("revised_text", "")
                # Find the proposed_text from the matching edit and replace it
                target = audit_item.get("target", "")
                for edit in edits:
                    if edit.get("target") == target and edit.get("proposed_text"):
                        replacement = self._apply_replacement(
                            resume, edit["proposed_text"], revised
                        )
                        if replacement is not None:
                            resume = replacement
                        break
            elif verdict == "revert":
                # Revert to the original text
                target = audit_item.get("target", "")
                for edit in edits:
                    if edit.get("target") == target:
                        if edit.get("edit_type") == "replace" and edit.get("current_text"):
                            revert = self._apply_replacement(
                                resume, edit["proposed_text"], edit["current_text"]
                            )
                            if revert is not None:
                                resume = revert
                        break

        return SkillResult.ok({"resume": resume, "report": audit_summary})

    # =========================================================================
    # Edit Application Helpers
    # =========================================================================

    def _apply_replacement(
        self, resume: str, current_text: str, proposed_text: str
    ) -> str | None:
        """Apply an exact string replacement. Returns None if not found."""
        if not current_text or current_text not in resume:
            return None
        return resume.replace(current_text, proposed_text, 1)

    def _apply_fuzzy_replacement(
        self, resume: str, current_text: str, proposed_text: str
    ) -> str | None:
        """Apply replacement with normalized whitespace matching."""
        if not current_text:
            return None

        # Normalize whitespace for matching
        def normalize(text: str) -> str:
            return " ".join(text.split())

        normalized_current = normalize(current_text)
        lines = resume.split("\n")
        rebuilt = []
        found = False

        # Try to match against individual lines or consecutive line groups
        i = 0
        while i < len(lines):
            if not found:
                # Try single line match
                if normalize(lines[i]) == normalized_current:
                    # Preserve leading whitespace from original line
                    leading = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
                    rebuilt.append(leading + proposed_text.strip())
                    found = True
                    i += 1
                    continue

                # Try matching the line content (stripping markdown bullet prefix)
                line_content = lines[i].lstrip()
                if line_content.startswith("- "):
                    line_content = line_content[2:]
                current_content = current_text.lstrip()
                if current_content.startswith("- "):
                    current_content = current_content[2:]

                if normalize(line_content) == normalize(current_content):
                    leading = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
                    # Preserve bullet prefix if present
                    if lines[i].lstrip().startswith("- "):
                        prefix = leading + "- "
                        new_text = proposed_text.strip()
                        if new_text.startswith("- "):
                            new_text = new_text[2:]
                        rebuilt.append(prefix + new_text)
                    else:
                        rebuilt.append(leading + proposed_text.strip())
                    found = True
                    i += 1
                    continue

            rebuilt.append(lines[i])
            i += 1

        if found:
            return "\n".join(rebuilt)
        return None

    def _apply_addition(self, resume: str, edit: dict) -> str | None:
        """Insert a new bullet after the specified target location."""
        target = edit.get("target", "")
        proposed_text = edit.get("proposed_text", "")

        if not proposed_text:
            return None

        # Parse target like "Tesla, after bullet 3" or "Company Name, after bullet N"
        match = re.search(r"after bullet (\d+)", target, re.IGNORECASE)
        company_match = re.match(r"^(.+?),\s*after", target, re.IGNORECASE)

        if not match:
            return None

        bullet_num = int(match.group(1))
        company_hint = company_match.group(1).strip() if company_match else ""

        lines = resume.split("\n")
        result_lines = []
        in_target_section = False
        bullet_count = 0
        inserted = False

        for i, line in enumerate(lines):
            result_lines.append(line)

            # Detect section by company name in heading
            if company_hint and company_hint.lower() in line.lower() and (
                line.startswith("#") or line.startswith("**")
            ):
                in_target_section = True
                bullet_count = 0
                continue

            # Detect leaving a section (next heading)
            if in_target_section and not inserted and (
                line.startswith("### ") or line.startswith("## ")
            ) and bullet_count > 0:
                in_target_section = False

            # Count bullets in target section
            if in_target_section and line.lstrip().startswith("- "):
                bullet_count += 1
                if bullet_count == bullet_num and not inserted:
                    # Insert after this bullet
                    new_bullet = proposed_text.strip()
                    if not new_bullet.startswith("- "):
                        new_bullet = "- " + new_bullet
                    result_lines.append(new_bullet)
                    inserted = True

        if inserted:
            return "\n".join(result_lines)
        return None

    def _apply_removal(self, resume: str, current_text: str) -> str | None:
        """Remove a bullet from the resume."""
        if not current_text:
            return None

        # Try exact match first
        if current_text in resume:
            # Remove the line and any trailing newline
            result = resume.replace(current_text, "", 1)
            # Clean up double blank lines
            result = re.sub(r"\n{3,}", "\n\n", result)
            return result

        # Try fuzzy match
        def normalize(text: str) -> str:
            return " ".join(text.split())

        normalized_target = normalize(current_text)
        lines = resume.split("\n")
        result_lines = []
        found = False

        for line in lines:
            if not found and normalize(line) == normalized_target:
                found = True
                continue  # Skip this line (remove it)
            result_lines.append(line)

        if found:
            return "\n".join(result_lines)
        return None

    def _apply_edits_via_claude(
        self, resume: str, failed_edits: list[tuple[int, dict]]
    ) -> str | None:
        """Fallback: use Claude to apply edits that string matching couldn't handle."""
        if not failed_edits:
            return None

        edit_instructions = []
        for i, edit in failed_edits:
            edit_type = edit.get("edit_type", "replace")
            target = edit.get("target", "")
            current_text = edit.get("current_text", "")
            proposed_text = edit.get("proposed_text", "")

            if edit_type == "replace":
                edit_instructions.append(
                    f"EDIT {i+1} [{edit_type.upper()}]: In {target}, "
                    f"find text similar to: \"{current_text}\" "
                    f"and replace it with: \"{proposed_text}\""
                )
            elif edit_type == "add":
                edit_instructions.append(
                    f"EDIT {i+1} [ADD]: In {target}, "
                    f"add this bullet: \"{proposed_text}\""
                )
            elif edit_type == "remove":
                edit_instructions.append(
                    f"EDIT {i+1} [REMOVE]: In {target}, "
                    f"remove the bullet: \"{current_text}\""
                )

        response = self.client.complete(
            system="""Apply the specified edits to the resume. Change ONLY what is described in the edits. Do not modify any other part of the resume. Preserve all formatting, structure, and whitespace exactly. Output ONLY the modified resume in Markdown.""",
            user=f"""Apply these specific edits to the resume:

{chr(10).join(edit_instructions)}

RESUME:
{resume}""",
            max_tokens=4096,
        )

        return response if response else None

    def _generate_resume_content(
        self,
        job: dict,
        resume_text: str,
        analysis: dict | None,
        role_lens: str,
        additional_context: str | None = None,
    ) -> str | None:
        """Generate customized resume content."""
        job_text = json.dumps(job, indent=2)
        analysis_text = json.dumps(analysis, indent=2) if analysis else "No prior analysis"

        # Role-lens specific guidance
        role_lens_guidance = self._get_role_lens_guidance(role_lens, "resume")

        # Build corpus context if available
        corpus_context = self._build_corpus_context(job, role_lens)

        # Build the prompt with optional corpus section
        corpus_section = ""
        if corpus_context:
            corpus_section = f"""
## PROVEN EXPERIENCE BULLETS (prefer these over creating new ones)
{corpus_context}
"""

        # Build additional context section if provided
        additional_context_section = ""
        if additional_context:
            additional_context_section = f"""
## ADDITIONAL CONTEXT (supplementary real experiences — valid source material):
These are real experiences the candidate has but that are NOT on the base resume.
You may draw from this material to enrich the resume, especially to address gaps
identified in the analysis. These experiences are factual and defensible.

{additional_context}
"""

        source_instruction = "use only this information"
        if additional_context:
            source_instruction = "use this and additional context as source material"

        response = self.client.complete(
            system=RESUME_GENERATION_PROMPT,
            user=f"""Create a customized resume for this job:

## TARGET JOB:
{job_text}

## ROLE LENS: {role_lens.upper()}
{role_lens_guidance}
{corpus_section}
## BASE RESUME (primary source material - {source_instruction}):
{resume_text}
{additional_context_section}
## ANALYSIS & RECOMMENDATIONS:
{analysis_text}

Ensure that the Professional Summary and the resume overall reflect the {role_lens} lens.

Generate a tailored resume in Markdown format.
.""",
            max_tokens=4096,
        )

        return response

    def _build_corpus_context(self, job: dict, role_lens: str) -> str | None:
        """Build corpus context with relevant bullets for the job.

        Args:
            job: Job dictionary with posting details.
            role_lens: Role lens for filtering bullets.

        Returns:
            Formatted corpus context string, or None if no corpus available.
        """
        corpus = self.data_store.get_corpus()
        if not corpus:
            return None

        experiences = corpus.get("experiences", {})
        skills_index = corpus.get("skills_index", {})
        themes_index = corpus.get("themes_index", {})

        if not experiences:
            return None

        # Extract keywords from job for matching
        job_keywords = self._extract_job_keywords(job)

        # Find relevant bullet IDs based on skills and themes
        relevant_bullet_ids = set()

        # Match by skills from job requirements
        for keyword in job_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in skills_index:
                relevant_bullet_ids.update(skills_index[keyword_lower])
            # Also check for partial matches
            for skill, bullet_ids in skills_index.items():
                if keyword_lower in skill or skill in keyword_lower:
                    relevant_bullet_ids.update(bullet_ids)

        # Match by role lens
        for exp_key, exp_data in experiences.items():
            for bullet in exp_data.get("bullets", []):
                if bullet.get("role_lens") == role_lens:
                    relevant_bullet_ids.add(bullet.get("id"))

        # Build context from relevant bullets
        context_parts = []
        bullets_by_company: dict[str, list[dict]] = {}

        for exp_key, exp_data in experiences.items():
            company = exp_data.get("company", "Unknown")
            title = exp_data.get("title", "Unknown")

            for bullet in exp_data.get("bullets", []):
                bullet_id = bullet.get("id")
                if bullet_id in relevant_bullet_ids:
                    key = f"{company} - {title}"
                    if key not in bullets_by_company:
                        bullets_by_company[key] = []
                    bullets_by_company[key].append(bullet)

        # Format output, limiting to most relevant bullets
        max_bullets_per_role = 4
        max_total_bullets = 20
        total_bullets = 0

        for company_title, bullets in bullets_by_company.items():
            if total_bullets >= max_total_bullets:
                break

            # Sort by usage count (most used first)
            sorted_bullets = sorted(
                bullets, key=lambda b: b.get("usage_count", 0), reverse=True
            )[:max_bullets_per_role]

            context_parts.append(f"\n### {company_title}")
            for bullet in sorted_bullets:
                if total_bullets >= max_total_bullets:
                    break

                bullet_id = bullet.get("id", "?")
                text = bullet.get("text", "")
                skills = bullet.get("skills_demonstrated", [])
                lens = bullet.get("role_lens", "engineering")

                skills_str = ", ".join(skills[:5]) if skills else "general"
                context_parts.append(f"[{bullet_id}] \"{text}\"")
                context_parts.append(f"  - Skills: {skills_str}")
                context_parts.append(f"  - Good for: {lens} roles")
                total_bullets += 1

        if not context_parts:
            return None

        header = """These bullets have been used in successful resume variations.
Prefer adapting these over creating new content when they fit the job requirements:
"""
        return header + "\n".join(context_parts)

    def _extract_job_keywords(self, job: dict) -> list[str]:
        """Extract relevant keywords from a job posting.

        Args:
            job: Job dictionary.

        Returns:
            List of extracted keywords.
        """
        keywords = []

        # Extract from various job fields
        text_fields = [
            job.get("requirements_summary", ""),
            job.get("responsibilities_summary", ""),
            job.get("title", ""),
            job.get("match_notes", ""),
        ]

        # Common skill patterns to look for
        skill_patterns = [
            r"\b(Python|Java|JavaScript|TypeScript|Go|Rust|C\+\+|SQL)\b",
            r"\b(AWS|GCP|Azure|Kubernetes|Docker|Terraform)\b",
            r"\b(ML|machine learning|AI|artificial intelligence|deep learning)\b",
            r"\b(data engineering|data platform|analytics|ETL|pipeline)\b",
            r"\b(team lead|leadership|management|engineering manager)\b",
            r"\b(product|roadmap|strategy|stakeholder)\b",
            r"\b(observability|monitoring|reliability|SRE)\b",
            r"\b(autonomous|robotics|perception|simulation)\b",
        ]

        combined_text = " ".join(text_fields)

        for pattern in skill_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            keywords.extend(matches)

        # Also extract from explicit requirements if structured
        if isinstance(job.get("requirements"), list):
            keywords.extend(job["requirements"])

        # Deduplicate and normalize
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)

        return unique_keywords

    def _refine_resume_defensibility(
        self, resume: str, job: dict, base_resume: str, additional_context: str | None = None
    ) -> str:
        """Second pass: review resume for defensibility and remove generic/inflated content."""
        job_text = json.dumps(job, indent=2)

        # Build additional context section if provided
        additional_context_section = ""
        if additional_context:
            additional_context_section = f"""
## ADDITIONAL CONTEXT (supplementary real experiences — also valid ground truth):
Claims sourced from this material ARE real and should NOT be flagged as fabrication.

{additional_context}
"""

        ground_truth_instruction = "Ensure every claim is defensible and grounded in the original resume."
        if additional_context:
            ground_truth_instruction = "Ensure every claim is defensible and grounded in the original resume or additional context."

        return self.client.complete(
            system=RESUME_DEFENSIBILITY_PROMPT,
            user=f"""Review this tailored resume for defensibility and authenticity.

## TARGET JOB (for context on what might be keyword-stuffed):
{job_text}

## ORIGINAL BASE RESUME (ground truth - what the candidate actually did):
{base_resume}
{additional_context_section}
## TAILORED RESUME TO REVIEW:
{resume}

{ground_truth_instruction} Remove or tone down anything that sounds inflated or mirrors the job description too closely. Output only the refined resume in Markdown.""",
            max_tokens=4096,
        )

    def _get_role_lens_guidance(self, role_lens: str, doc_type: str) -> str:
        """Return role-lens specific guidance for resume generation."""
        guidance = _load_role_lens_guidance()
        return guidance.get(role_lens, guidance.get("engineering", {})).get(doc_type, "")

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
