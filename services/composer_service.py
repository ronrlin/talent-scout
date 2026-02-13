"""Composer service - job analysis, resume/cover letter generation, interview prep.

Extracted from agents/application_composer.py.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from skills import (
    JobDescriptionAnalyzerSkill,
    ResumeGeneratorSkill,
    CoverLetterGeneratorSkill,
    InterviewPrepSkill,
    SkillContext,
)

from .base_service import BaseService
from .document_converter import convert_document
from .exceptions import (
    JobNotFoundError,
    ResumeNotFoundError,
    GenerationFailedError,
    AnalysisNotFoundError,
)
from .models import AnalysisResult, GenerationResult

logger = logging.getLogger(__name__)


class ComposerService(BaseService):
    """Service for application materials - analysis, resumes, cover letters, interview prep.

    Wraps ApplicationComposerAgent's business logic with typed exceptions
    and Pydantic response models.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Initialize skills
        self.job_analyzer = JobDescriptionAnalyzerSkill(
            self.client, self.data_store, self.config
        )
        self.resume_generator = ResumeGeneratorSkill(
            self.client, self.data_store, self.config
        )
        self.cover_letter_generator = CoverLetterGeneratorSkill(
            self.client, self.data_store, self.config
        )
        self.interview_prep_skill = InterviewPrepSkill(
            self.client, self.data_store, self.config
        )

        # Ensure output directories exist
        for subdir in ("resumes", "cover-letters", "analysis", "interview-prep"):
            (self.output_dir / subdir).mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Job Analysis
    # =========================================================================

    def analyze_job(self, job_id: str) -> AnalysisResult:
        """Analyze a job posting and match against user's profile.

        Args:
            job_id: ID of the job to analyze.

        Returns:
            AnalysisResult with analysis data.

        Raises:
            JobNotFoundError: If job not found.
            ResumeNotFoundError: If base resume not found.
            GenerationFailedError: If analysis fails.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        resume_text = self._load_base_resume()
        if not resume_text:
            raise ResumeNotFoundError(str(self.input_dir / "base-resume.md"))

        context = SkillContext(config=self.config)
        result = self.job_analyzer.execute(context, job, resume_text)

        if not result.success:
            raise GenerationFailedError("Job analysis", result.error)

        raw_analysis = result.metadata.get("raw_analysis", {})

        # Save analysis
        output_path = self.output_dir / "analysis" / f"{job_id}-analysis.json"
        self._save_analysis(job_id, job, raw_analysis)

        # Pipeline: advance to researched, record artifact
        self.pipeline.advance(job_id, "researched", "auto:analyze")
        self.pipeline.record_artifact(job_id, "analysis", str(output_path))

        return AnalysisResult(
            job_id=job_id,
            analysis=raw_analysis,
            analysis_path=str(output_path),
        )

    # =========================================================================
    # Resume Generation
    # =========================================================================

    def generate_resume(self, job_id: str, output_format: str = "pdf") -> GenerationResult:
        """Generate a customized resume for a job.

        Args:
            job_id: ID of the job to generate resume for.
            output_format: "pdf", "docx", or "both".

        Returns:
            GenerationResult with paths to generated files.

        Raises:
            JobNotFoundError: If job not found.
            ResumeNotFoundError: If base resume not found.
            GenerationFailedError: If generation fails.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        role_lens = self.job_analyzer.determine_role_lens(job)

        resume_text = self._load_base_resume()
        if not resume_text:
            raise ResumeNotFoundError(str(self.input_dir / "base-resume.md"))

        analysis = self._load_analysis(job_id)

        # Load additional context if enabled
        additional_context = None
        ac_mode = os.environ.get("TALENT_SCOUT_ADDITIONAL_CONTEXT", "")
        if ac_mode == "resume":
            additional_context = self._load_additional_context()

        context = SkillContext(config=self.config)
        result = self.resume_generator.execute(
            context,
            job=job,
            base_resume=resume_text,
            analysis=analysis,
            role_lens=role_lens,
            additional_context=additional_context,
        )

        if not result.success:
            raise GenerationFailedError("Resume generation", result.error)

        resume_md = result.data.resume_markdown

        # Save markdown
        company_name = self._sanitize_filename(job.get("company", "Unknown"))
        job_title = self._sanitize_filename(job.get("title", "Unknown"))
        md_path = self.output_dir / "resumes" / f"Ron Lin Resume - {company_name} - {job_title}.md"

        with open(md_path, "w") as f:
            f.write(resume_md)

        # Pipeline
        self.pipeline.advance(job_id, "resume_ready", "auto:resume")
        self.pipeline.record_artifact(job_id, "resume", str(md_path))

        # Generate output format(s)
        output_paths = convert_document(md_path, "resume", output_format)

        return GenerationResult(
            job_id=job_id,
            doc_type="resume",
            markdown_path=str(md_path),
            artifacts={fmt: str(path) if path else None for fmt, path in output_paths.items()},
            metadata={"role_lens": role_lens},
        )

    def improve_resume(self, job_id: str, output_format: str = "pdf") -> GenerationResult:
        """Improve an existing resume using three-phase pipeline.

        Args:
            job_id: ID of the job the resume is for.
            output_format: "pdf", "docx", or "both".

        Returns:
            GenerationResult with paths to improved files.

        Raises:
            JobNotFoundError: If job not found.
            ResumeNotFoundError: If no existing resume found.
            GenerationFailedError: If improvement fails.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        resume_path = self.find_document_by_job_id(job_id, "resume")
        if not resume_path:
            raise ResumeNotFoundError(
                f"No existing resume found for job: {job_id}. "
                "Run 'scout resume <job_id>' first."
            )

        with open(resume_path) as f:
            current_resume = f.read()

        base_resume = self._load_base_resume()
        if not base_resume:
            raise ResumeNotFoundError(str(self.input_dir / "base-resume.md"))

        # Load analysis — auto-run if missing
        analysis = self._load_analysis(job_id)
        if not analysis:
            logger.info("No analysis found for %s, running analyze first", job_id)
            try:
                analysis_result = self.analyze_job(job_id)
                analysis = analysis_result.analysis
            except Exception:
                logger.warning("Analysis failed, proceeding with degraded improvement")

        role_lens = self.job_analyzer.determine_role_lens(job)

        # Extract positioning signals
        positioning_strategy = None
        role_archetype = None
        if analysis:
            resume_recs = analysis.get("resume_recommendations", {})
            positioning_strategy = resume_recs.get("positioning_strategy")
            job_summary = analysis.get("job_summary", {})
            role_archetype = job_summary.get("role_archetype")

        # Load additional context if enabled
        additional_context = None
        ac_mode = os.environ.get("TALENT_SCOUT_ADDITIONAL_CONTEXT", "")
        if ac_mode == "improve":
            additional_context = self._load_additional_context()

        context = SkillContext(config=self.config)

        # Phase 1: Generate edit plan
        edit_plan_result = self.resume_generator.plan_resume_edits(
            context,
            job=job,
            current_resume=current_resume,
            base_resume=base_resume,
            analysis=analysis,
            role_lens=role_lens,
            positioning_strategy=positioning_strategy,
            role_archetype=role_archetype,
            additional_context=additional_context,
        )

        if not edit_plan_result.success:
            raise GenerationFailedError("Edit plan generation", edit_plan_result.error)

        edit_plan = edit_plan_result.data

        # Save versioned edit plan
        edit_plan_path = self._save_edit_plan(job_id, edit_plan)

        # Phase 2: Apply edits
        apply_result = self.resume_generator.apply_resume_edits(
            current_resume, edit_plan
        )

        if not apply_result.success:
            raise GenerationFailedError("Edit application", apply_result.error)

        modified_resume = apply_result.data["resume"]
        apply_report = apply_result.data["report"]

        # Phase 3: Credibility audit
        audit_result = self.resume_generator.audit_resume_edits(
            context,
            modified_resume=modified_resume,
            original_resume=current_resume,
            base_resume=base_resume,
            job=job,
            edit_plan=edit_plan,
            positioning_strategy=positioning_strategy,
            role_archetype=role_archetype,
            additional_context=additional_context,
        )

        if audit_result.success:
            final_resume = audit_result.data["resume"]
            audit_report = audit_result.data["report"]
        else:
            logger.warning("Credibility audit failed, using Phase 2 output: %s", audit_result.error)
            final_resume = modified_resume
            audit_report = []

        # Save improved resume
        with open(resume_path, "w") as f:
            f.write(final_resume)

        # Pipeline
        self.pipeline.advance(job_id, "resume_ready", "auto:resume_improve")
        self.pipeline.record_artifact(job_id, "resume", str(resume_path))

        # Regenerate output format(s)
        output_paths = convert_document(resume_path, "resume", output_format)

        return GenerationResult(
            job_id=job_id,
            doc_type="resume",
            markdown_path=str(resume_path),
            artifacts={fmt: str(path) if path else None for fmt, path in output_paths.items()},
            metadata={
                "edit_plan": edit_plan,
                "apply_report": apply_report,
                "audit_report": audit_report,
                "edit_plan_path": str(edit_plan_path) if edit_plan_path else None,
            },
        )

    # =========================================================================
    # Cover Letter Generation
    # =========================================================================

    def generate_cover_letter(self, job_id: str, output_format: str = "pdf") -> GenerationResult:
        """Generate a cover letter for a job.

        Args:
            job_id: ID of the job to generate cover letter for.
            output_format: "pdf", "docx", or "both".

        Returns:
            GenerationResult with paths to generated files.

        Raises:
            JobNotFoundError: If job not found.
            ResumeNotFoundError: If base resume not found.
            GenerationFailedError: If generation fails.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        role_lens = self.job_analyzer.determine_role_lens(job)

        resume_text = self._load_base_resume()
        if not resume_text:
            raise ResumeNotFoundError(str(self.input_dir / "base-resume.md"))

        analysis = self._load_analysis(job_id)

        context = SkillContext(config=self.config)
        result = self.cover_letter_generator.execute(
            context,
            job=job,
            base_resume=resume_text,
            analysis=analysis,
            role_lens=role_lens,
        )

        if not result.success:
            raise GenerationFailedError("Cover letter generation", result.error)

        cover_letter_md = result.data.cover_letter_markdown

        # Save markdown
        company_name = self._sanitize_filename(job.get("company", "Unknown"))
        job_title = self._sanitize_filename(job.get("title", "Unknown"))
        md_path = self.output_dir / "cover-letters" / f"Cover Letter - {company_name} - {job_title}.md"

        with open(md_path, "w") as f:
            f.write(cover_letter_md)

        # Pipeline: no advance, just record artifact
        self.pipeline.record_artifact(job_id, "cover_letter", str(md_path))

        # Generate output format(s)
        output_paths = convert_document(md_path, "cover-letter", output_format)

        return GenerationResult(
            job_id=job_id,
            doc_type="cover_letter",
            markdown_path=str(md_path),
            artifacts={fmt: str(path) if path else None for fmt, path in output_paths.items()},
            metadata={"role_lens": role_lens},
        )

    # =========================================================================
    # Interview Prep
    # =========================================================================

    def generate_interview_prep(self, job_id: str) -> GenerationResult:
        """Generate screening interview preparation materials.

        Args:
            job_id: ID of the job to prepare for.

        Returns:
            GenerationResult with path to prep document.

        Raises:
            JobNotFoundError: If job not found.
            ResumeNotFoundError: If base resume not found.
            GenerationFailedError: If generation fails.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            raise JobNotFoundError(job_id)

        role_lens = self.job_analyzer.determine_role_lens(job)

        resume_text = self._load_base_resume()
        if not resume_text:
            raise ResumeNotFoundError(str(self.input_dir / "base-resume.md"))

        # Load analysis — auto-run if missing
        analysis = self._load_analysis(job_id)
        if not analysis:
            logger.info("No analysis found for %s, running analyze first", job_id)
            try:
                analysis_result = self.analyze_job(job_id)
                analysis = analysis_result.analysis
            except Exception:
                logger.warning("Analysis failed, proceeding without analysis data")

        # Load company research (optional)
        company_name = job.get("company", "")
        company_research = None
        if company_name:
            company_slug = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
            company_research = self.data_store.get_research(company_slug)

        context = SkillContext(config=self.config)
        result = self.interview_prep_skill.execute(
            context,
            job=job,
            base_resume=resume_text,
            analysis=analysis,
            role_lens=role_lens,
            company_research=company_research,
        )

        if not result.success:
            raise GenerationFailedError("Interview prep generation", result.error)

        prep_result = result.data
        prep_md = prep_result.prep_markdown

        # Save markdown
        sanitized_company = self._sanitize_filename(job.get("company", "Unknown"))
        sanitized_title = self._sanitize_filename(job.get("title", "Unknown"))
        md_path = self.output_dir / "interview-prep" / f"Interview Prep - {sanitized_company} - {sanitized_title}.md"

        with open(md_path, "w") as f:
            f.write(prep_md)

        # Pipeline: no advance, just record artifact
        self.pipeline.record_artifact(job_id, "interview_prep", str(md_path))

        return GenerationResult(
            job_id=job_id,
            doc_type="interview_prep",
            markdown_path=str(md_path),
            metadata={
                "section_count": prep_result.section_count,
                "domain_connection_count": prep_result.domain_connection_count,
            },
        )

    # =========================================================================
    # Document Regeneration
    # =========================================================================

    def regenerate_output(
        self, md_path: Path, doc_type: str, output_format: str = "pdf"
    ) -> dict[str, Path | None]:
        """Regenerate output file(s) from an existing markdown file.

        Args:
            md_path: Path to the markdown file.
            doc_type: Type of document ("resume" or "cover-letter").
            output_format: "pdf", "docx", or "both".

        Returns:
            Dict with "pdf" and/or "docx" keys mapping to output Paths.
        """
        return convert_document(md_path, doc_type, output_format)

    def find_document_by_job_id(self, job_id: str, doc_type: str) -> Path | None:
        """Find an existing markdown document by job_id.

        Args:
            job_id: ID of the job.
            doc_type: Type of document ("resume" or "cover-letter").

        Returns:
            Path to the document or None if not found.
        """
        job = self.data_store.get_job(job_id)
        if not job:
            return None

        company_name = self._sanitize_filename(job.get("company", "Unknown"))
        job_title = self._sanitize_filename(job.get("title", "Unknown"))

        if doc_type == "resume":
            search_dir = self.output_dir / "resumes"
            pattern = f"Ron Lin Resume - {company_name} - {job_title}.md"
        else:
            search_dir = self.output_dir / "cover-letters"
            pattern = f"Cover Letter - {company_name} - {job_title}.md"

        exact_path = search_dir / pattern
        if exact_path.exists():
            return exact_path

        # Fall back to partial match
        if search_dir.exists():
            for md_file in search_dir.glob("*.md"):
                if company_name in md_file.name and job_title[:20] in md_file.name:
                    return md_file

        return None

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _save_analysis(self, job_id: str, job: dict, analysis: dict) -> None:
        """Save job analysis to file."""
        output_path = self.output_dir / "analysis" / f"{job_id}-analysis.json"

        data = {
            "job_id": job_id,
            "job": job,
            "analysis": analysis,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_analysis(self, job_id: str) -> dict | None:
        """Load existing analysis if available."""
        analysis_path = self.output_dir / "analysis" / f"{job_id}-analysis.json"

        if analysis_path.exists():
            with open(analysis_path) as f:
                data = json.load(f)
                return data.get("analysis")

        return None

    def _save_edit_plan(self, job_id: str, edit_plan: dict) -> Path | None:
        """Save versioned edit plan to disk."""
        analysis_dir = self.output_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        version = 1
        while (analysis_dir / f"{job_id}-edit-plan-v{version}.json").exists():
            version += 1

        edit_plan_path = analysis_dir / f"{job_id}-edit-plan-v{version}.json"

        data = {
            "job_id": job_id,
            "version": version,
            "edit_plan": edit_plan,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(edit_plan_path, "w") as f:
            json.dump(data, f, indent=2)

        return edit_plan_path

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use in filenames."""
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        sanitized = sanitized.strip()
        return sanitized[:50]
