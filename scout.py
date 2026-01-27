#!/usr/bin/env python3
"""Talent Scout - AI-powered job search automation."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from config_loader import load_config
from agents import CompanyScoutAgent, CompanyResearcherAgent, LearningAgent, JobResearcherAgent

console = Console()
DATA_DIR = Path(__file__).parent / "data"
IMPORT_DIR = Path(__file__).parent / "import-jobs"


HELP_TEXT = """
Talent Scout - AI-powered job search automation

WORKFLOW:
  1. Scout companies    → scout companies --location boca
  2. Research & import  → scout research "Company" or scout research <url>
  3. Review jobs        → scout jobs
  4. Learn preferences  → scout learn (after importing/deleting jobs)
  5. Analyze fit        → scout analyze <job_id>
  6. Generate resume    → scout resume <job_id>
  7. Generate cover     → scout cover-letter <job_id>

DISCOVERY:
  companies     Scout target companies by location (boca/palo/remote)
  research      Research a company OR import a job from URL
  import-jobs   Import jobs from markdown files in import-jobs/
  jobs          List all discovered job opportunities

FEEDBACK LOOP:
  learn         Analyze imported/deleted jobs to improve targeting
  delete        Remove a job (teaches system what you don't want)

APPLICATION:
  analyze          Analyze job requirements and match against your profile
  resume           Generate a customized resume for a specific job
  cover-letter     Generate a tailored cover letter
  resume-improve   Iteratively improve resume for better job alignment
  resume-gen       Regenerate PDF from edited resume markdown
  cover-letter-gen Regenerate PDF from edited cover letter markdown

EXAMPLES:
  scout companies --location boca --count 10
  scout research "Google"
  scout research https://jobs.example.com/posting/12345
  scout jobs --company ModMed
  scout delete JOB-NVIDIA-123 --reason "Too technical"
  scout analyze JOB-MODMED-ABC
  scout resume JOB-MODMED-ABC
  scout resume-improve JOB-MODMED-ABC
"""


@click.group(help=HELP_TEXT)
@click.pass_context
def cli(ctx):
    """Talent Scout - AI-powered job search automation."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config()


@cli.command()
@click.option(
    "--location",
    type=click.Choice(["boca", "palo", "remote", "all"]),
    default="all",
    help="Target location to scout companies for.",
)
@click.option(
    "--count",
    type=int,
    default=None,
    help="Number of companies to find per location.",
)
@click.pass_context
def companies(ctx, location: str, count: int | None):
    """Scout and prioritize target companies by location."""
    config = ctx.obj["config"]

    if count is None:
        count = config["preferences"]["companies_per_location"]

    locations = [location] if location != "all" else ["boca", "palo", "remote"]

    agent = CompanyScoutAgent(config)

    for loc in locations:
        console.print(f"\n[bold blue]Scouting companies for: {loc}[/bold blue]")
        results = agent.scout(location=loc, count=count)
        console.print(f"[green]Found {len(results)} companies for {loc}[/green]")


@cli.command()
@click.argument("target")
@click.pass_context
def research(ctx, target: str):
    """Research a company or import a job from URL.

    TARGET can be either:
    - A company name (e.g., "Google") to research the company and find jobs
    - A job posting URL (e.g., "https://...") to import a specific job
    """
    config = ctx.obj["config"]
    agent = CompanyResearcherAgent(config)

    # Detect if target is a URL
    if target.startswith("http://") or target.startswith("https://"):
        console.print(f"\n[bold blue]Importing job from URL...[/bold blue]")
        result = agent.import_job_from_url(target)

        if result:
            console.print(f"\n[green]Job imported successfully![/green]")
        else:
            console.print(f"\n[red]Failed to import job from URL[/red]")
    else:
        # Treat as company name
        console.print(f"\n[bold blue]Researching: {target}[/bold blue]")
        result = agent.research(target)

        jobs_count = len(result.get("jobs", []))
        console.print(f"\n[green]Research complete. Found {jobs_count} potential job(s).[/green]")


@cli.command("import-jobs")
@click.pass_context
def import_jobs(ctx):
    """Import jobs from markdown files in import-jobs/ directory.

    Place job descriptions (copy-pasted from job postings) as markdown files
    in the import-jobs/ directory. Each file will be parsed and imported.
    Files are deleted after successful import.

    Example:
        1. Copy job description text from a website
        2. Save as import-jobs/google-engineering-manager.md
        3. Run: scout import-jobs
    """
    config = ctx.obj["config"]

    # Ensure import directory exists
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Find all markdown files
    md_files = list(IMPORT_DIR.glob("*.md"))

    if not md_files:
        console.print(f"[yellow]No markdown files found in {IMPORT_DIR}[/yellow]")
        console.print("[dim]Place job description markdown files in the import-jobs/ directory[/dim]")
        return

    console.print(f"\n[bold blue]Found {len(md_files)} file(s) to import[/bold blue]\n")

    agent = CompanyResearcherAgent(config)
    imported = 0
    failed = 0

    for md_file in md_files:
        console.print(f"[cyan]Processing: {md_file.name}[/cyan]")

        try:
            content = md_file.read_text()

            if not content.strip():
                console.print(f"[yellow]  Skipping empty file: {md_file.name}[/yellow]")
                failed += 1
                continue

            result = agent.import_job_from_markdown(content, md_file.name)

            if result:
                # Delete the file after successful import
                md_file.unlink()
                console.print(f"[green]  Imported and deleted: {md_file.name}[/green]\n")
                imported += 1
            else:
                console.print(f"[red]  Failed to import: {md_file.name}[/red]\n")
                failed += 1

        except Exception as e:
            console.print(f"[red]  Error processing {md_file.name}: {e}[/red]\n")
            failed += 1

    console.print(f"\n[bold]Import complete:[/bold] {imported} imported, {failed} failed")


@cli.command()
@click.option(
    "--location",
    type=click.Choice(["boca", "palo", "remote", "all"]),
    default="all",
    help="Filter jobs by location.",
)
@click.option("--company", help="Filter jobs by company name.")
@click.pass_context
def jobs(ctx, location: str, company: str | None):
    """List discovered job opportunities."""
    locations = [location] if location != "all" else ["boca", "palo", "remote"]

    all_jobs = []
    for loc in locations:
        jobs_file = DATA_DIR / f"jobs-{loc}.json"
        if jobs_file.exists():
            with open(jobs_file) as f:
                data = json.load(f)
                for job in data.get("jobs", []):
                    job["_location_file"] = loc
                    all_jobs.append(job)

    # Filter by company if specified
    if company:
        all_jobs = [j for j in all_jobs if company.lower() in j.get("company", "").lower()]

    if not all_jobs:
        console.print("[yellow]No jobs found. Run 'scout research <company>' to discover jobs.[/yellow]")
        return

    # Sort by match score
    all_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)

    # Display as table
    table = Table(title=f"Discovered Jobs ({len(all_jobs)} total)")
    table.add_column("ID", style="dim")
    table.add_column("Company", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Location", style="green")
    table.add_column("Score", justify="right", style="yellow")

    for job in all_jobs:
        table.add_row(
            job.get("id", "?"),
            job.get("company", "?"),
            job.get("title", "?"),
            job.get("location", "?"),
            str(job.get("match_score", "?")),
        )

    console.print(table)


@cli.command()
@click.pass_context
def learn(ctx):
    """Analyze imported jobs to improve targeting.

    This command analyzes jobs you've manually imported to understand
    your preferences and improve future job discovery. It also learns
    from jobs you've deleted to avoid similar matches.
    """
    config = ctx.obj["config"]
    console.print("\n[bold blue]Learning from job feedback...[/bold blue]\n")

    agent = LearningAgent(config)
    result = agent.analyze_and_learn()

    if result:
        console.print("\n[dim]Run 'scout companies' or 'scout research' to use improved targeting.[/dim]")


@cli.command()
@click.argument("job_id")
@click.option("--reason", "-r", help="Reason for removing (helps improve future targeting).")
@click.pass_context
def delete(ctx, job_id: str, reason: str | None):
    """Remove a job and learn from the feedback.

    Deleting a job teaches the system what you DON'T want,
    improving future job discovery and prioritization.
    """
    config = ctx.obj["config"]
    agent = LearningAgent(config)

    # Find and remove the job
    job, location = _find_and_remove_job(job_id)

    if not job:
        console.print(f"[red]Job not found: {job_id}[/red]")
        console.print("[dim]Use 'scout jobs' to see available job IDs[/dim]")
        return

    # Store for negative learning
    agent.record_deleted_job(job, reason)

    console.print(f"[green]Removed:[/green] {job.get('title')} at {job.get('company')}")
    console.print(f"[dim]This feedback will improve future targeting. Run 'scout learn' to update.[/dim]")


def _find_and_remove_job(job_id: str) -> tuple[dict | None, str | None]:
    """Find a job by ID and remove it from its location file."""
    for location in ["boca", "palo", "remote"]:
        jobs_file = DATA_DIR / f"jobs-{location}.json"
        if not jobs_file.exists():
            continue

        with open(jobs_file) as f:
            data = json.load(f)

        jobs = data.get("jobs", [])
        for i, job in enumerate(jobs):
            if job.get("id") == job_id:
                # Remove the job
                removed_job = jobs.pop(i)
                data["jobs"] = jobs

                # Save updated file
                with open(jobs_file, "w") as f:
                    json.dump(data, f, indent=2)

                return removed_job, location

    return None, None


@cli.command()
@click.argument("company_name")
@click.pass_context
def connections(ctx, company_name: str):
    """Find connections at a specific company."""
    console.print(f"[yellow]Connection finder not yet implemented[/yellow]")
    console.print(f"Would find connections at: {company_name}")


@cli.command()
@click.argument("job_id")
@click.pass_context
def analyze(ctx, job_id: str):
    """Analyze a job posting and match against your profile.

    Provides match assessment, gap analysis, and recommendations
    for customizing your resume and cover letter.
    """
    config = ctx.obj["config"]
    console.print(f"\n[bold blue]Analyzing job: {job_id}[/bold blue]\n")

    agent = JobResearcherAgent(config)
    result = agent.analyze_job(job_id)

    if not result:
        console.print("[red]Analysis failed[/red]")


@cli.command()
@click.argument("job_id")
@click.pass_context
def resume(ctx, job_id: str):
    """Generate a customized resume for a job.

    Creates a tailored resume based on your base resume,
    optimized for the specific job posting.
    """
    config = ctx.obj["config"]
    console.print(f"\n[bold blue]Generating resume for: {job_id}[/bold blue]\n")

    agent = JobResearcherAgent(config)
    result = agent.generate_resume(job_id)

    if not result:
        console.print("[red]Resume generation failed[/red]")


@cli.command("cover-letter")
@click.argument("job_id")
@click.pass_context
def cover_letter(ctx, job_id: str):
    """Generate a cover letter for a job.

    Creates a personalized cover letter based on the job
    requirements and your experience.
    """
    config = ctx.obj["config"]
    console.print(f"\n[bold blue]Generating cover letter for: {job_id}[/bold blue]\n")

    agent = JobResearcherAgent(config)
    result = agent.generate_cover_letter(job_id)

    if not result:
        console.print("[red]Cover letter generation failed[/red]")


@cli.command("resume-gen")
@click.argument("job_id")
@click.pass_context
def resume_gen(ctx, job_id: str):
    """Regenerate PDF from existing resume markdown.

    Use this after manually editing a resume markdown file
    to regenerate just the PDF without re-running AI generation.
    """
    config = ctx.obj["config"]
    agent = JobResearcherAgent(config)

    # Find the markdown file
    md_path = agent.find_document_by_job_id(job_id, "resume")
    if not md_path:
        console.print(f"[red]No resume markdown found for job: {job_id}[/red]")
        console.print("[dim]Run 'scout resume <job_id>' first to generate the resume.[/dim]")
        return

    console.print(f"\n[bold blue]Regenerating PDF from: {md_path.name}[/bold blue]\n")

    pdf_path = agent.regenerate_pdf(md_path, "resume")
    if pdf_path:
        console.print(f"[green]PDF saved to:[/green] {pdf_path}")
    else:
        console.print("[red]PDF generation failed[/red]")


@cli.command("cover-letter-gen")
@click.argument("job_id")
@click.pass_context
def cover_letter_gen(ctx, job_id: str):
    """Regenerate PDF from existing cover letter markdown.

    Use this after manually editing a cover letter markdown file
    to regenerate just the PDF without re-running AI generation.
    """
    config = ctx.obj["config"]
    agent = JobResearcherAgent(config)

    # Find the markdown file
    md_path = agent.find_document_by_job_id(job_id, "cover-letter")
    if not md_path:
        console.print(f"[red]No cover letter markdown found for job: {job_id}[/red]")
        console.print("[dim]Run 'scout cover-letter <job_id>' first to generate the cover letter.[/dim]")
        return

    console.print(f"\n[bold blue]Regenerating PDF from: {md_path.name}[/bold blue]\n")

    pdf_path = agent.regenerate_pdf(md_path, "cover-letter")
    if pdf_path:
        console.print(f"[green]PDF saved to:[/green] {pdf_path}")
    else:
        console.print("[red]PDF generation failed[/red]")


@cli.command("resume-improve")
@click.argument("job_id")
@click.pass_context
def resume_improve(ctx, job_id: str):
    """Iteratively improve a resume for better job alignment.

    This command takes an existing tailored resume and improves it
    through multiple passes to better align with the job requirements
    while maintaining credibility and accuracy.

    The process:
    1. Analyzes job requirements and implicit hiring criteria
    2. Evaluates current resume alignment
    3. Identifies improvement opportunities
    4. Iteratively revises until strongly aligned
    5. Outputs summary of changes made
    """
    config = ctx.obj["config"]
    console.print(f"\n[bold blue]Improving resume for: {job_id}[/bold blue]\n")

    agent = JobResearcherAgent(config)
    result = agent.improve_resume(job_id)

    if not result:
        console.print("[red]Resume improvement failed[/red]")


@cli.command()
@click.argument("company_name")
@click.option("--connection", help="Specific connection to reach out to.")
@click.pass_context
def outreach(ctx, company_name: str, connection: str | None):
    """Generate cold outreach email for a company."""
    console.print(f"[yellow]Outreach generator not yet implemented[/yellow]")
    console.print(f"Would generate outreach for: {company_name}")


if __name__ == "__main__":
    cli()
