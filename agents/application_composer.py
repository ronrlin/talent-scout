"""Application Composer Agent - positioning strategy, resume/cover letter generation."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from data_store import DataStore
from skills import (
    JobDescriptionAnalyzerSkill,
    ResumeGeneratorSkill,
    CoverLetterGeneratorSkill,
    SkillContext,
)
from .base_agent import BaseAgent

console = Console()


class ApplicationComposerAgent(BaseAgent):
    """Agent that handles application materials - analysis, resumes, cover letters.

    Consolidates functionality from JobResearcherAgent:
    - analyze_job
    - generate_resume
    - generate_cover_letter
    - improve_resume
    - regenerate_pdf
    """

    def __init__(self, config: dict):
        """Initialize the application composer agent.

        Args:
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.data_store = DataStore(config)

        # Initialize skills
        self.job_analyzer = JobDescriptionAnalyzerSkill(
            self.client, self.data_store, config
        )
        self.resume_generator = ResumeGeneratorSkill(
            self.client, self.data_store, config
        )
        self.cover_letter_generator = CoverLetterGeneratorSkill(
            self.client, self.data_store, config
        )

        # Ensure output directories exist
        (self.output_dir / "resumes").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "cover-letters").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "analysis").mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Job Analysis
    # =========================================================================

    def analyze_job(self, job_id: str) -> dict | None:
        """Analyze a job posting and match against user's profile.

        Args:
            job_id: ID of the job to analyze.

        Returns:
            Analysis dictionary or None if failed.
        """
        # Find the job
        job = self.data_store.get_job(job_id)
        if not job:
            console.print(f"[red]Job not found: {job_id}[/red]")
            return None

        # Load base resume
        resume_text = self._load_base_resume()
        if not resume_text:
            console.print("[red]Could not load base resume[/red]")
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

            analysis_result = result.data
            raw_analysis = result.metadata.get("raw_analysis", {})

            progress.update(task, description="Saving analysis...")

            # Save analysis
            self._save_analysis(job_id, job, raw_analysis)

        # Print summary
        self._print_analysis(job, analysis_result)

        return raw_analysis

    # =========================================================================
    # Resume Generation
    # =========================================================================

    def generate_resume(self, job_id: str) -> str | None:
        """Generate a customized resume for a job.

        Args:
            job_id: ID of the job to generate resume for.

        Returns:
            Path to saved resume markdown, or None if failed.
        """
        # Find the job
        job = self.data_store.get_job(job_id)
        if not job:
            console.print(f"[red]Job not found: {job_id}[/red]")
            return None

        # Determine role lens
        role_lens = self.job_analyzer.determine_role_lens(job)
        console.print(f"[dim]Role lens: {role_lens}[/dim]")

        # Load base resume
        resume_text = self._load_base_resume()
        if not resume_text:
            console.print("[red]Could not load base resume[/red]")
            return None

        # Load analysis if exists
        analysis = self._load_analysis(job_id)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating customized resume...", total=None)

            # Build skill context
            context = SkillContext(config=self.config)

            # Execute resume generator skill
            result = self.resume_generator.execute(
                context,
                job=job,
                base_resume=resume_text,
                analysis=analysis,
                role_lens=role_lens,
            )

            if not result.success:
                console.print(f"[red]Resume generation failed: {result.error}[/red]")
                return None

            resume_md = result.data.resume_markdown

            progress.update(task, description="Saving resume...")

            # Save markdown
            company_name = self._sanitize_filename(job.get("company", "Unknown"))
            job_title = self._sanitize_filename(job.get("title", "Unknown"))
            md_path = self.output_dir / "resumes" / f"Ron Lin Resume - {company_name} - {job_title}.md"

            with open(md_path, "w") as f:
                f.write(resume_md)

            # Try to generate PDF
            progress.update(task, description="Generating PDF...")
            pdf_path = self._convert_to_pdf(md_path, "resume")

        console.print(f"[green]Resume saved to:[/green] {md_path}")
        if pdf_path:
            console.print(f"[green]PDF saved to:[/green] {pdf_path}")

        return str(md_path)

    def improve_resume(self, job_id: str) -> str | None:
        """Iteratively improve an existing resume to better align with a job.

        Args:
            job_id: ID of the job the resume is for.

        Returns:
            Path to improved resume markdown, or None if failed.
        """
        # Find the job
        job = self.data_store.get_job(job_id)
        if not job:
            console.print(f"[red]Job not found: {job_id}[/red]")
            return None

        # Find existing resume for this job
        resume_path = self.find_document_by_job_id(job_id, "resume")
        if not resume_path:
            console.print(f"[red]No existing resume found for job: {job_id}[/red]")
            console.print("[dim]Run 'scout resume <job_id>' first to generate a resume.[/dim]")
            return None

        # Load the current resume
        with open(resume_path) as f:
            current_resume = f.read()

        # Load base resume for reference
        base_resume = self._load_base_resume()
        if not base_resume:
            console.print("[red]Could not load base resume[/red]")
            return None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing and improving resume...", total=None)

            # Build skill context
            context = SkillContext(config=self.config)

            # Execute resume improvement
            result = self.resume_generator.improve_resume(
                context,
                job=job,
                current_resume=current_resume,
                base_resume=base_resume,
            )

            if not result.success:
                console.print(f"[red]Resume improvement failed: {result.error}[/red]")
                return None

            improved_resume = result.data.resume_markdown
            improvement_summary = result.data.improvement_summary

            progress.update(task, description="Saving improved resume...")

            # Save the improved resume
            with open(resume_path, "w") as f:
                f.write(improved_resume)

            progress.update(task, description="Generating PDF...")

            # Regenerate PDF
            pdf_path = self._convert_to_pdf(resume_path, "resume")

        # Print improvement summary
        console.print(Panel(
            "\n".join(f"- {item}" for item in improvement_summary),
            title="[bold green]Improvement Summary[/bold green]",
            border_style="green"
        ))

        console.print(f"\n[green]Resume improved and saved to:[/green] {resume_path}")
        if pdf_path:
            console.print(f"[green]PDF saved to:[/green] {pdf_path}")

        return str(resume_path)

    # =========================================================================
    # Cover Letter Generation
    # =========================================================================

    def generate_cover_letter(self, job_id: str) -> str | None:
        """Generate a cover letter for a job.

        Args:
            job_id: ID of the job to generate cover letter for.

        Returns:
            Path to saved cover letter markdown, or None if failed.
        """
        # Find the job
        job = self.data_store.get_job(job_id)
        if not job:
            console.print(f"[red]Job not found: {job_id}[/red]")
            return None

        # Determine role lens
        role_lens = self.job_analyzer.determine_role_lens(job)
        console.print(f"[dim]Role lens: {role_lens}[/dim]")

        # Load base resume
        resume_text = self._load_base_resume()
        if not resume_text:
            console.print("[red]Could not load base resume[/red]")
            return None

        # Load analysis if exists
        analysis = self._load_analysis(job_id)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating cover letter...", total=None)

            # Build skill context
            context = SkillContext(config=self.config)

            # Execute cover letter generator skill
            result = self.cover_letter_generator.execute(
                context,
                job=job,
                base_resume=resume_text,
                analysis=analysis,
                role_lens=role_lens,
            )

            if not result.success:
                console.print(f"[red]Cover letter generation failed: {result.error}[/red]")
                return None

            cover_letter_md = result.data.cover_letter_markdown

            progress.update(task, description="Saving cover letter...")

            # Save markdown
            company_name = self._sanitize_filename(job.get("company", "Unknown"))
            job_title = self._sanitize_filename(job.get("title", "Unknown"))
            md_path = self.output_dir / "cover-letters" / f"Cover Letter - {company_name} - {job_title}.md"

            with open(md_path, "w") as f:
                f.write(cover_letter_md)

            # Try to generate PDF
            progress.update(task, description="Generating PDF...")
            pdf_path = self._convert_to_pdf(md_path, "cover-letter")

        console.print(f"[green]Cover letter saved to:[/green] {md_path}")
        if pdf_path:
            console.print(f"[green]PDF saved to:[/green] {pdf_path}")

        return str(md_path)

    # =========================================================================
    # Document Management
    # =========================================================================

    def find_document_by_job_id(self, job_id: str, doc_type: str) -> Path | None:
        """Find an existing markdown document by job_id.

        Args:
            job_id: ID of the job.
            doc_type: Type of document ("resume" or "cover-letter").

        Returns:
            Path to the document or None if not found.
        """
        # Find the job to get company and title
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

        # Try exact match first
        exact_path = search_dir / pattern
        if exact_path.exists():
            return exact_path

        # Fall back to searching for partial match
        if search_dir.exists():
            for md_file in search_dir.glob("*.md"):
                if company_name in md_file.name and job_title[:20] in md_file.name:
                    return md_file

        return None

    def regenerate_pdf(self, md_path: Path, doc_type: str) -> Path | None:
        """Regenerate PDF from an existing markdown file.

        Args:
            md_path: Path to the markdown file.
            doc_type: Type of document ("resume" or "cover-letter").

        Returns:
            Path to the PDF or None if failed.
        """
        return self._convert_to_pdf(md_path, doc_type)

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _load_base_resume(self) -> str | None:
        """Load the base resume from Word doc."""
        resume_path = self.input_dir / "base-resume.docx"

        if not resume_path.exists():
            console.print(f"[yellow]Resume not found at {resume_path}[/yellow]")
            return None

        try:
            doc = Document(resume_path)

            # Extract text from paragraphs
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)

            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        text_parts.append(" | ".join(row_text))

            return "\n\n".join(text_parts)

        except Exception as e:
            console.print(f"[red]Error reading resume: {e}[/red]")
            return None

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

    def _convert_to_pdf(self, md_path: Path, doc_type: str) -> Path | None:
        """Convert markdown to PDF using weasyprint."""
        try:
            import markdown
            from weasyprint import HTML

            # Read markdown
            with open(md_path) as f:
                md_content = f.read()

            # Normalize bullet characters
            md_content = re.sub(r'^•\s*', '- ', md_content, flags=re.MULTILINE)

            # Convert to HTML
            html_content = markdown.markdown(md_content, extensions=['tables'])

            # Load template based on document type
            template_dir = Path(__file__).parent.parent / "templates"
            template_file = "resume.html" if doc_type == "resume" else "cover-letter.html"
            template_path = template_dir / template_file

            with open(template_path) as f:
                template = f.read()

            # Insert content into template
            full_html = template.replace("{{content}}", html_content)

            # Generate PDF
            pdf_path = md_path.with_suffix('.pdf')
            HTML(string=full_html).write_pdf(pdf_path)

            return pdf_path

        except ImportError as e:
            console.print(f"[yellow]PDF generation skipped (missing dependency): {e}[/yellow]")
            return None
        except Exception as e:
            console.print(f"[yellow]PDF generation failed: {e}[/yellow]")
            return None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use in filenames."""
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        sanitized = sanitized.strip()
        return sanitized[:50]

    def _print_analysis(self, job: dict, analysis_result) -> None:
        """Print job analysis summary."""
        job_summary = analysis_result.job_summary
        match = analysis_result.match_assessment
        recs = analysis_result.resume_recommendations

        # Job info panel
        console.print(Panel(
            f"[bold]{job_summary.get('title', job.get('title', 'Unknown'))}[/bold] at "
            f"[cyan]{job_summary.get('company', job.get('company', 'Unknown'))}[/cyan]\n\n"
            f"[bold]Experience Required:[/bold] {job_summary.get('experience_required', 'Not specified')}",
            title="Job Summary"
        ))

        # Match score
        score = match.get("overall_score", "?")
        score_color = "green" if isinstance(score, int) and score >= 75 else "yellow" if isinstance(score, int) and score >= 50 else "red"
        console.print(f"\n[bold]Match Score:[/bold] [{score_color}]{score}/100[/{score_color}]")

        # Strengths
        strengths = match.get("strengths", [])
        if strengths:
            console.print("\n[bold green]Your Strengths:[/bold green]")
            for s in strengths[:4]:
                console.print(f"  - {s}")

        # Gaps
        gaps = match.get("gaps", [])
        if gaps:
            console.print("\n[bold yellow]Potential Gaps:[/bold yellow]")
            for g in gaps[:3]:
                console.print(f"  - {g}")

        # Keywords to include
        keywords = recs.get("keywords_to_include", [])
        if keywords:
            console.print("\n[bold]Keywords to Include:[/bold]")
            console.print(f"  {', '.join(keywords[:8])}")

        console.print("\n[dim]Run 'scout resume <job_id>' to generate a customized resume[/dim]")
