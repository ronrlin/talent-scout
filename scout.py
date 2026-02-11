#!/usr/bin/env python3
"""Talent Scout - AI-powered job search automation."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from config_loader import (
    load_config,
    get_locations,
    get_location_slug,
    get_all_location_slugs,
    is_remote_enabled,
)
from data_store import DataStore
from agents import (
    CandidateProfilerAgent,
    OpportunityScoutAgent,
    ApplicationComposerAgent,
)

console = Console()
IMPORT_DIR = Path(__file__).parent / "import-jobs"


HELP_TEXT = """
Talent Scout - AI-powered job search automation

WORKFLOW:
  1. Set up profile       → scout profile --refresh
  2. Scout companies      → scout companies --location "Palo Alto, CA"
  3. Research & import    → scout research "Company" or scout research <url>
  4. Review jobs          → scout jobs
  5. Learn preferences    → scout learn (after importing/deleting jobs)
  6. Analyze fit          → scout analyze <job_id>
  7. Generate resume      → scout resume <job_id>
  8. Generate cover       → scout cover-letter <job_id>
  9. Prepare for interview → scout interview-prep <job_id>

PROFILE:
  profile         View/manage your candidate profile
  profile --refresh  Re-parse profile from base resume

DISCOVERY:
  companies     Scout target companies by location (from config.json)
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
  resume-gen       Regenerate output from edited resume markdown
  cover-letter-gen Regenerate output from edited cover letter markdown
  interview-prep   Generate screening interview talking points

  All output commands support --format pdf|docx|both (default from config).

CORPUS:
  corpus build   Build experience bullet corpus from existing resumes
  corpus update  Update corpus with new bullets from recent resumes
  corpus stats   Show corpus statistics

EXAMPLES:
  scout profile --refresh
  scout companies --location "Palo Alto, CA" --count 10
  scout research "Google"
  scout research https://jobs.example.com/posting/12345
  scout jobs --company ModMed
  scout delete JOB-NVIDIA-123 --reason "Too technical"
  scout analyze JOB-MODMED-ABC
  scout resume JOB-MODMED-ABC
  scout resume-improve JOB-MODMED-ABC
  scout interview-prep JOB-MODMED-ABC
  scout corpus build
"""


@click.group(help=HELP_TEXT)
@click.pass_context
def cli(ctx):
    """Talent Scout - AI-powered job search automation."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config()
    ctx.obj["data_store"] = DataStore(ctx.obj["config"])


# ============================================================================
# Profile Commands
# ============================================================================


@cli.command()
@click.option(
    "--refresh",
    is_flag=True,
    help="Re-parse profile from base resume.",
)
@click.pass_context
def profile(ctx, refresh: bool):
    """View or refresh your candidate profile.

    The profile is extracted from your base resume and includes
    learned preferences from job feedback.
    """
    config = ctx.obj["config"]
    agent = CandidateProfilerAgent(config)

    if refresh:
        console.print("\n[bold blue]Refreshing profile from base resume...[/bold blue]\n")
        result = agent.refresh_profile()
        if not result:
            console.print("[red]Profile refresh failed[/red]")
    else:
        console.print("\n[bold blue]Candidate Profile[/bold blue]\n")
        agent.view_profile()


# ============================================================================
# Discovery Commands
# ============================================================================


@cli.command()
@click.option(
    "--location",
    type=str,
    default="all",
    help="Target location to scout (e.g., 'Palo Alto, CA' or 'remote' or 'all').",
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

    # Build list of locations to scout
    configured_locations = get_locations(config)
    include_remote = is_remote_enabled(config)

    if location.lower() == "all":
        locations_to_scout = list(configured_locations)
        if include_remote:
            locations_to_scout.append("remote")
    elif location.lower() == "remote":
        if include_remote:
            locations_to_scout = ["remote"]
        else:
            console.print("[yellow]Remote is not enabled in config.json. Set 'include_remote: true' to enable.[/yellow]")
            return
    else:
        # Check if it's a configured location
        if location in configured_locations:
            locations_to_scout = [location]
        else:
            # Try to find a partial match
            matched = [loc for loc in configured_locations if location.lower() in loc.lower()]
            if matched:
                locations_to_scout = matched
            else:
                console.print(f"[yellow]Location '{location}' not found in config.[/yellow]")
                console.print(f"[dim]Configured locations: {', '.join(configured_locations)}[/dim]")
                if include_remote:
                    console.print("[dim]Remote is also enabled.[/dim]")
                return

    agent = OpportunityScoutAgent(config)

    for loc in locations_to_scout:
        console.print(f"\n[bold blue]Scouting companies for: {loc}[/bold blue]")
        results = agent.scout_companies(location=loc, count=count)
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
    agent = OpportunityScoutAgent(config)

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
        result = agent.research_company(target)

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

    agent = OpportunityScoutAgent(config)
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
    type=str,
    default="all",
    help="Filter jobs by location (e.g., 'Palo Alto, CA' or 'remote' or 'all').",
)
@click.option("--company", help="Filter jobs by company name.")
@click.pass_context
def jobs(ctx, location: str, company: str | None):
    """List discovered job opportunities."""
    config = ctx.obj["config"]
    data_store = ctx.obj["data_store"]
    all_location_slugs = get_all_location_slugs(config)

    # Determine which location slug to use
    location_slug = None
    if location.lower() == "all":
        location_slug = None  # Get all
    elif location.lower() == "remote":
        location_slug = "remote"
    else:
        # Try to match the location to a slug
        slug = get_location_slug(location)
        if slug in all_location_slugs:
            location_slug = slug
        else:
            # Try partial match on configured locations
            configured_locations = get_locations(config)
            matched = [loc for loc in configured_locations if location.lower() in loc.lower()]
            if matched:
                location_slug = get_location_slug(matched[0])

    # Get jobs using DataStore
    all_jobs = data_store.get_jobs(location_slug=location_slug, company=company)

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


# ============================================================================
# Feedback Loop Commands
# ============================================================================


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

    agent = OpportunityScoutAgent(config)
    result = agent.learn_from_feedback()

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
    data_store = ctx.obj["data_store"]
    agent = OpportunityScoutAgent(config)

    # Find and remove the job using DataStore
    job = data_store.delete_job(job_id)

    if not job:
        console.print(f"[red]Job not found: {job_id}[/red]")
        console.print("[dim]Use 'scout jobs' to see available job IDs[/dim]")
        return

    # Store for negative learning
    agent.record_deleted_job(job, reason)

    console.print(f"[green]Removed:[/green] {job.get('title')} at {job.get('company')}")
    console.print(f"[dim]This feedback will improve future targeting. Run 'scout learn' to update.[/dim]")


# ============================================================================
# Application Commands
# ============================================================================


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

    agent = ApplicationComposerAgent(config)
    result = agent.analyze_job(job_id)

    if not result:
        console.print("[red]Analysis failed[/red]")


@cli.command()
@click.argument("job_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["pdf", "docx", "both"]),
    default=None,
    help="Output format (default: from config, or pdf).",
)
@click.pass_context
def resume(ctx, job_id: str, output_format: str | None):
    """Generate a customized resume for a job.

    Creates a tailored resume based on your base resume,
    optimized for the specific job posting.
    """
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")
    console.print(f"\n[bold blue]Generating resume for: {job_id}[/bold blue]\n")

    agent = ApplicationComposerAgent(config)
    result = agent.generate_resume(job_id, output_format=output_format)

    if not result:
        console.print("[red]Resume generation failed[/red]")


@cli.command("cover-letter")
@click.argument("job_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["pdf", "docx", "both"]),
    default=None,
    help="Output format (default: from config, or pdf).",
)
@click.pass_context
def cover_letter(ctx, job_id: str, output_format: str | None):
    """Generate a cover letter for a job.

    Creates a personalized cover letter based on the job
    requirements and your experience.
    """
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")
    console.print(f"\n[bold blue]Generating cover letter for: {job_id}[/bold blue]\n")

    agent = ApplicationComposerAgent(config)
    result = agent.generate_cover_letter(job_id, output_format=output_format)

    if not result:
        console.print("[red]Cover letter generation failed[/red]")


@cli.command("resume-gen")
@click.argument("job_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["pdf", "docx", "both"]),
    default=None,
    help="Output format (default: from config, or pdf).",
)
@click.pass_context
def resume_gen(ctx, job_id: str, output_format: str | None):
    """Regenerate output from existing resume markdown.

    Use this after manually editing a resume markdown file
    to regenerate PDF/DOCX without re-running AI generation.
    """
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")
    agent = ApplicationComposerAgent(config)

    # Find the markdown file
    md_path = agent.find_document_by_job_id(job_id, "resume")
    if not md_path:
        console.print(f"[red]No resume markdown found for job: {job_id}[/red]")
        console.print("[dim]Run 'scout resume <job_id>' first to generate the resume.[/dim]")
        return

    fmt_label = "PDF + DOCX" if output_format == "both" else output_format.upper()
    console.print(f"\n[bold blue]Regenerating {fmt_label} from: {md_path.name}[/bold blue]\n")

    results = agent.regenerate_output(md_path, "resume", output_format)
    generated = {fmt: path for fmt, path in results.items() if path}
    if generated:
        for fmt, path in generated.items():
            console.print(f"[green]{fmt.upper()} saved to:[/green] {path}")
    else:
        console.print("[red]Output generation failed[/red]")


@cli.command("cover-letter-gen")
@click.argument("job_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["pdf", "docx", "both"]),
    default=None,
    help="Output format (default: from config, or pdf).",
)
@click.pass_context
def cover_letter_gen(ctx, job_id: str, output_format: str | None):
    """Regenerate output from existing cover letter markdown.

    Use this after manually editing a cover letter markdown file
    to regenerate PDF/DOCX without re-running AI generation.
    """
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")
    agent = ApplicationComposerAgent(config)

    # Find the markdown file
    md_path = agent.find_document_by_job_id(job_id, "cover-letter")
    if not md_path:
        console.print(f"[red]No cover letter markdown found for job: {job_id}[/red]")
        console.print("[dim]Run 'scout cover-letter <job_id>' first to generate the cover letter.[/dim]")
        return

    fmt_label = "PDF + DOCX" if output_format == "both" else output_format.upper()
    console.print(f"\n[bold blue]Regenerating {fmt_label} from: {md_path.name}[/bold blue]\n")

    results = agent.regenerate_output(md_path, "cover-letter", output_format)
    generated = {fmt: path for fmt, path in results.items() if path}
    if generated:
        for fmt, path in generated.items():
            console.print(f"[green]{fmt.upper()} saved to:[/green] {path}")
    else:
        console.print("[red]Output generation failed[/red]")


@cli.command("resume-improve")
@click.argument("job_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["pdf", "docx", "both"]),
    default=None,
    help="Output format (default: from config, or pdf).",
)
@click.pass_context
def resume_improve(ctx, job_id: str, output_format: str | None):
    """Iteratively improve a resume for better job alignment.

    Reviews an existing resume against the job description and
    makes targeted improvements while maintaining credibility.
    """
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")
    console.print(f"\n[bold blue]Improving resume for: {job_id}[/bold blue]\n")

    agent = ApplicationComposerAgent(config)
    result = agent.improve_resume(job_id, output_format=output_format)

    if not result:
        console.print("[red]Resume improvement failed[/red]")


@cli.command("interview-prep")
@click.argument("job_id")
@click.pass_context
def interview_prep(ctx, job_id: str):
    """Generate screening interview talking points for a job.

    Creates a preparation document with elevator pitch, domain
    connection talking points, anticipated Q&A, and gap mitigation
    strategies tailored to the specific role.
    """
    config = ctx.obj["config"]
    console.print(f"\n[bold blue]Generating interview prep for: {job_id}[/bold blue]\n")

    agent = ApplicationComposerAgent(config)
    result = agent.generate_interview_prep(job_id)

    if not result:
        console.print("[red]Interview prep generation failed[/red]")


@cli.command()
@click.argument("company_name")
@click.option("--connection", help="Specific connection to reach out to.")
@click.pass_context
def outreach(ctx, company_name: str, connection: str | None):
    """Generate cold outreach email for a company."""
    console.print(f"[yellow]Outreach generator not yet implemented[/yellow]")
    console.print(f"Would generate outreach for: {company_name}")


# ============================================================================
# Corpus Commands
# ============================================================================


@cli.group()
def corpus():
    """Manage the experience bullet corpus.

    The corpus is a library of proven experience bullets extracted from
    generated resumes. It provides consistent language and faster generation
    by allowing Claude to select and adapt existing bullets rather than
    creating new ones from scratch.
    """
    pass


@corpus.command("build")
@click.pass_context
def corpus_build(ctx):
    """Build the experience bullet corpus from existing resumes.

    Scans all generated resumes in output/resumes/ and extracts
    experience bullets, deduplicating similar entries and enriching
    with skills and themes for better matching.
    """
    from claude_client import ClaudeClient
    from skills import CorpusBuilderSkill

    config = ctx.obj["config"]
    data_store = ctx.obj["data_store"]

    console.print("\n[bold blue]Building experience bullet corpus...[/bold blue]\n")

    client = ClaudeClient()
    skill = CorpusBuilderSkill(client, data_store, config)

    result = skill.build_corpus()

    if result.success:
        console.print("[green]Corpus built successfully![/green]\n")
        console.print(f"  Resumes processed: {result.metadata.get('resumes_processed', 0)}")
        console.print(f"  Experience entries: {result.metadata.get('experiences_count', 0)}")
        console.print(f"  Total bullets: {result.metadata.get('bullets_count', 0)}")
        console.print(f"  Skills indexed: {result.metadata.get('skills_indexed', 0)}")
        console.print(f"  Themes indexed: {result.metadata.get('themes_indexed', 0)}")
        console.print("\n[dim]Corpus saved to data/skills-corpus.json[/dim]")
    else:
        console.print(f"[red]Corpus build failed: {result.error}[/red]")


@corpus.command("update")
@click.pass_context
def corpus_update(ctx):
    """Update corpus with new bullets from recent resumes.

    Compares current resumes to the existing corpus and adds any
    new bullet formulations discovered during recent resume generation.
    """
    from claude_client import ClaudeClient
    from skills import CorpusBuilderSkill

    config = ctx.obj["config"]
    data_store = ctx.obj["data_store"]

    console.print("\n[bold blue]Updating experience bullet corpus...[/bold blue]\n")

    client = ClaudeClient()
    skill = CorpusBuilderSkill(client, data_store, config)

    result = skill.update_corpus()

    if result.success:
        console.print("[green]Corpus updated successfully![/green]\n")
        console.print(f"  Resumes processed: {result.metadata.get('resumes_processed', 0)}")
        console.print(f"  Experience entries: {result.metadata.get('experiences_count', 0)}")
        console.print(f"  Total bullets: {result.metadata.get('bullets_count', 0)}")
    else:
        console.print(f"[red]Corpus update failed: {result.error}[/red]")


@corpus.command("stats")
@click.pass_context
def corpus_stats(ctx):
    """Show corpus statistics."""
    data_store = ctx.obj["data_store"]

    corpus_data = data_store.get_corpus()

    if not corpus_data:
        console.print("[yellow]No corpus found. Run 'scout corpus build' first.[/yellow]")
        return

    console.print("\n[bold blue]Skills Corpus Statistics[/bold blue]\n")
    console.print(f"  Version: {corpus_data.get('version', 'unknown')}")
    console.print(f"  Generated: {corpus_data.get('generated_at', 'unknown')}")
    console.print(f"  Source resumes: {corpus_data.get('source_resumes', 0)}")

    experiences = corpus_data.get("experiences", {})
    total_bullets = sum(
        len(exp.get("bullets", []))
        for exp in experiences.values()
    )

    console.print(f"  Experience entries: {len(experiences)}")
    console.print(f"  Total bullets: {total_bullets}")
    console.print(f"  Skills indexed: {len(corpus_data.get('skills_index', {}))}")
    console.print(f"  Themes indexed: {len(corpus_data.get('themes_index', {}))}")

    # Show top skills
    skills_index = corpus_data.get("skills_index", {})
    if skills_index:
        sorted_skills = sorted(
            skills_index.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]
        console.print("\n[bold]Top 10 Skills:[/bold]")
        for skill, bullet_ids in sorted_skills:
            console.print(f"  {skill}: {len(bullet_ids)} bullets")

    # Show top themes
    themes_index = corpus_data.get("themes_index", {})
    if themes_index:
        sorted_themes = sorted(
            themes_index.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]
        console.print("\n[bold]Top 10 Themes:[/bold]")
        for theme, bullet_ids in sorted_themes:
            console.print(f"  {theme}: {len(bullet_ids)} bullets")


if __name__ == "__main__":
    cli()
