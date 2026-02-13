#!/usr/bin/env python3
"""Talent Scout - AI-powered job search automation."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config_loader import (
    load_config,
    get_locations,
    get_location_slug,
    get_all_location_slugs,
    is_remote_enabled,
)
from data_store import DataStore
from pipeline_store import PipelineStore, PIPELINE_STAGES, CLOSED_OUTCOMES
from services import (
    JobService,
    ProfileService,
    DiscoveryService,
    ComposerService,
    CorpusService,
    JobNotFoundError,
    ProfileNotFoundError,
    ResumeNotFoundError,
    GenerationFailedError,
    ValidationError,
    PipelineError,
    TalentScoutError,
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
  9. Record application   → scout apply <job_id> --via "company site"
  10. Check what's next   → scout next
  11. Prepare interview   → scout interview-prep <job_id>

PROFILE:
  profile         View/manage your candidate profile
  profile --refresh  Re-parse profile from base resume

DISCOVERY:
  companies     Scout target companies by location (from config.json)
  research      Research a company OR import a job from URL
  import-jobs   Import jobs from markdown files in import-jobs/
  jobs          List all discovered job opportunities (--stage filter)

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

PIPELINE MANAGEMENT:
  apply            Record that you submitted an application
  status           View or set pipeline stage for a job
  pipeline         Kanban-style overview of all jobs by stage
  next             Prioritized action dashboard — what to do next

  Pipeline stages: discovered → researched → resume_ready → applied →
                   screening → interviewing → offer → closed

CORPUS:
  corpus build   Build experience bullet corpus from existing resumes
  corpus update  Update corpus with new bullets from recent resumes
  corpus stats   Show corpus statistics

API:
  serve          Start the Talent Scout API server

EXAMPLES:
  scout profile --refresh
  scout companies --location "Palo Alto, CA" --count 10
  scout research "Google"
  scout research https://jobs.example.com/posting/12345
  scout jobs --company ModMed
  scout jobs --stage applied
  scout delete JOB-NVIDIA-123 --reason "Too technical"
  scout analyze JOB-MODMED-ABC
  scout resume JOB-MODMED-ABC
  scout apply JOB-MODMED-ABC --via "company site"
  scout next
  scout pipeline
  scout status JOB-MODMED-ABC
  scout status JOB-MODMED-ABC screening
  scout resume-improve JOB-MODMED-ABC
  scout interview-prep JOB-MODMED-ABC
  scout corpus build
  scout serve --port 8000
"""


def _create_services(config, data_store, pipeline):
    """Create all service instances sharing the same stores."""
    return {
        "job": JobService(config=config, data_store=data_store, pipeline=pipeline),
        "profile": ProfileService(config=config, data_store=data_store, pipeline=pipeline),
        "discovery": DiscoveryService(config=config, data_store=data_store, pipeline=pipeline),
        "composer": ComposerService(config=config, data_store=data_store, pipeline=pipeline),
        "corpus": CorpusService(config=config, data_store=data_store, pipeline=pipeline),
    }


@click.group(help=HELP_TEXT)
@click.pass_context
def cli(ctx):
    """Talent Scout - AI-powered job search automation."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config()
    ctx.obj["data_store"] = DataStore(ctx.obj["config"])
    ctx.obj["pipeline"] = PipelineStore(ctx.obj["config"])
    ctx.obj["services"] = _create_services(
        ctx.obj["config"], ctx.obj["data_store"], ctx.obj["pipeline"]
    )


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
    """View or refresh your candidate profile."""
    svc = ctx.obj["services"]["profile"]

    if refresh:
        console.print("\n[bold blue]Refreshing profile from base resume...[/bold blue]\n")
        try:
            from rich.progress import Progress, SpinnerColumn, TextColumn
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                progress.add_task("Parsing resume...", total=None)
                result = svc.refresh_profile()
            console.print("[green]Profile updated successfully[/green]")
        except (ResumeNotFoundError, GenerationFailedError) as e:
            console.print(f"[red]{e}[/red]")
            return
    else:
        console.print("\n[bold blue]Candidate Profile[/bold blue]\n")
        try:
            result = svc.get_profile()
        except ProfileNotFoundError:
            console.print("[yellow]No profile found. Run 'scout profile --refresh' to generate.[/yellow]")
            return

    # Display profile
    _print_profile(result)


def _print_profile(profile):
    """Display formatted profile."""
    identity = profile.identity
    name = identity.get("name", "Unknown")
    email = identity.get("email", "")
    location = identity.get("location", "")

    console.print(Panel(
        f"[bold]{name}[/bold]\n"
        f"[dim]{email}[/dim]\n"
        f"[dim]{location}[/dim]",
        title="Candidate Profile",
    ))

    if profile.summary:
        console.print(f"\n[bold]Summary:[/bold]\n{profile.summary}")

    if profile.experience:
        console.print("\n[bold]Experience:[/bold]")
        for exp in profile.experience[:5]:
            title = exp.get("title", "Unknown")
            company = exp.get("company", "Unknown")
            dates = f"{exp.get('start_date', '?')} - {exp.get('end_date', '?')}"
            console.print(f"  - {title} at [cyan]{company}[/cyan] [dim]({dates})[/dim]")
        if len(profile.experience) > 5:
            console.print(f"  [dim]... and {len(profile.experience) - 5} more positions[/dim]")

    skills = profile.skills
    if skills:
        console.print("\n[bold]Skills:[/bold]")
        if skills.get("technical"):
            console.print(f"  Technical: {', '.join(skills['technical'][:8])}")
        if skills.get("leadership"):
            console.print(f"  Leadership: {', '.join(skills['leadership'][:5])}")
        if skills.get("domains"):
            console.print(f"  Domains: {', '.join(skills['domains'][:5])}")

    prefs = profile.preferences
    if prefs:
        console.print("\n[bold]Target Preferences:[/bold]")
        roles = prefs.get("target_roles", [])
        if roles:
            console.print(f"  Roles: {', '.join(roles[:4])}")
        locations = prefs.get("locations", [])
        if locations:
            remote = " + Remote" if prefs.get("include_remote") else ""
            console.print(f"  Locations: {', '.join(locations)}{remote}")

    learned = profile.learned_preferences
    if learned:
        console.print("\n[bold]Learned Preferences:[/bold]")
        primary_titles = learned.get("primary_titles", [])
        if primary_titles:
            console.print(f"  Priority titles: {', '.join(primary_titles[:4])}")
        red_flags = learned.get("red_flag_keywords", [])
        if red_flags:
            console.print(f"  Avoiding: {', '.join(red_flags[:4])}")

    console.print(f"\n[dim]Profile generated: {profile.generated_at or 'Unknown'}[/dim]")


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
    svc = ctx.obj["services"]["discovery"]

    if count is None:
        count = config["preferences"]["companies_per_location"]

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
        if location in configured_locations:
            locations_to_scout = [location]
        else:
            matched = [loc for loc in configured_locations if location.lower() in loc.lower()]
            if matched:
                locations_to_scout = matched
            else:
                console.print(f"[yellow]Location '{location}' not found in config.[/yellow]")
                console.print(f"[dim]Configured locations: {', '.join(configured_locations)}[/dim]")
                if include_remote:
                    console.print("[dim]Remote is also enabled.[/dim]")
                return

    for loc in locations_to_scout:
        console.print(f"\n[bold blue]Scouting companies for: {loc}[/bold blue]")
        try:
            results = svc.scout_companies(location=loc, count=count)
            _print_companies_summary(results)
            console.print(f"[green]Found {len(results)} companies for {loc}[/green]")
        except GenerationFailedError as e:
            console.print(f"[red]{e}[/red]")


def _print_companies_summary(companies):
    """Print a summary of found companies."""
    console.print("\n[bold]Top companies found:[/bold]")
    for i, company in enumerate(companies[:5], 1):
        score = company.priority_score or "?"
        public = "public" if company.public else "private"
        console.print(
            f"  {i}. {company.name} "
            f"[dim]({public}, score: {score})[/dim]"
        )
    if len(companies) > 5:
        console.print(f"  [dim]... and {len(companies) - 5} more[/dim]")


@cli.command()
@click.argument("target")
@click.pass_context
def research(ctx, target: str):
    """Research a company or import a job from URL."""
    svc = ctx.obj["services"]["discovery"]

    if target.startswith("http://") or target.startswith("https://"):
        console.print(f"\n[bold blue]Importing job from URL...[/bold blue]")
        try:
            job = svc.import_job_from_url(target)
            _print_job_import_summary(job)
            console.print(f"\n[green]Job imported successfully![/green]")
        except GenerationFailedError as e:
            console.print(f"\n[red]{e}[/red]")
    else:
        console.print(f"\n[bold blue]Researching: {target}[/bold blue]")
        try:
            result = svc.research_company(target)
            _print_research_summary(result)
            console.print(f"\n[green]Research complete. Found {len(result.jobs)} potential job(s).[/green]")
        except GenerationFailedError as e:
            console.print(f"\n[red]{e}[/red]")


def _print_job_import_summary(job):
    """Print summary of imported job."""
    company = job.get("company", "Unknown")
    title = job.get("title", "Unknown")
    location = job.get("location", "Unknown")
    location_type = job.get("location_type", "remote")
    score = job.get("match_score", "?")
    requirements = job.get("requirements_summary", "Not specified")

    console.print(Panel(
        f"[bold]{title}[/bold] at [cyan]{company}[/cyan]\n"
        f"[dim]Location: {location} ({location_type})[/dim]\n"
        f"[dim]Match Score: {score}/100[/dim]\n\n"
        f"[bold]Requirements:[/bold]\n{requirements}\n\n"
        f"[dim]ID: {job['id']}[/dim]",
        title="Job Imported",
    ))


def _print_research_summary(result):
    """Print research summary."""
    company_info = result.company
    jobs = result.jobs

    if company_info:
        name = company_info.get("company_name", "Unknown")
        desc = company_info.get("description", "No description")
        industry = company_info.get("industry", "Unknown")
        employees = company_info.get("employee_count", "Unknown")
        public = "Public" if company_info.get("public") else "Private"

        console.print(Panel(
            f"[bold]{name}[/bold] ({public})\n"
            f"[dim]{industry} - ~{employees} employees[/dim]\n\n"
            f"{desc}",
            title="Company Overview",
        ))

    if jobs:
        console.print(f"\n[bold]Found {len(jobs)} relevant job(s):[/bold]")
        for job in jobs[:5]:
            score = job.get("match_score", "?")
            loc = job.get("location", "Unknown")
            console.print(f"  - {job['title']} [dim]({loc}, score: {score})[/dim]")
            console.print(f"    [dim]ID: {job['id']}[/dim]")
        if len(jobs) > 5:
            console.print(f"  [dim]... and {len(jobs) - 5} more[/dim]")
    else:
        console.print("\n[yellow]No matching jobs found[/yellow]")


@cli.command("import-jobs")
@click.pass_context
def import_jobs(ctx):
    """Import jobs from markdown files in import-jobs/ directory."""
    svc = ctx.obj["services"]["discovery"]

    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_files = list(IMPORT_DIR.glob("*.md"))

    if not md_files:
        console.print(f"[yellow]No markdown files found in {IMPORT_DIR}[/yellow]")
        console.print("[dim]Place job description markdown files in the import-jobs/ directory[/dim]")
        return

    console.print(f"\n[bold blue]Found {len(md_files)} file(s) to import[/bold blue]\n")

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

            job = svc.import_job_from_markdown(content, md_file.name)
            md_file.unlink()
            console.print(f"[green]  Imported and deleted: {md_file.name}[/green]\n")
            imported += 1
        except GenerationFailedError as e:
            console.print(f"[red]  Failed to import: {md_file.name} - {e}[/red]\n")
            failed += 1
        except Exception as e:
            console.print(f"[red]  Error processing {md_file.name}: {e}[/red]\n")
            failed += 1

    console.print(f"\n[bold]Import complete:[/bold] {imported} imported, {failed} failed")


@cli.command()
@click.option("--location", type=str, default="all", help="Filter by location.")
@click.option("--company", help="Filter jobs by company name.")
@click.option("--stage", help="Filter jobs by pipeline stage.")
@click.pass_context
def jobs(ctx, location: str, company: str | None, stage: str | None):
    """List discovered job opportunities."""
    svc = ctx.obj["services"]["job"]

    try:
        all_jobs = svc.get_jobs(location=location, company=company, stage=stage)
    except ValidationError as e:
        console.print(f"[red]{e}[/red]")
        console.print(f"[dim]Valid stages: {', '.join(PIPELINE_STAGES)}[/dim]")
        return

    if not all_jobs:
        console.print("[yellow]No jobs found. Run 'scout research <company>' to discover jobs.[/yellow]")
        return

    table = Table(title=f"Discovered Jobs ({len(all_jobs)} total)")
    table.add_column("ID", style="dim")
    table.add_column("Company", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Location", style="green")
    table.add_column("Score", justify="right", style="yellow")
    table.add_column("Stage", style="magenta")

    for job in all_jobs:
        table.add_row(
            job.id,
            job.company,
            job.title,
            job.location,
            str(job.match_score or "?"),
            job.stage or "-",
        )

    console.print(table)


# ============================================================================
# Feedback Loop Commands
# ============================================================================


@cli.command()
@click.pass_context
def learn(ctx):
    """Analyze imported jobs to improve targeting."""
    svc = ctx.obj["services"]["discovery"]
    console.print("\n[bold blue]Learning from job feedback...[/bold blue]\n")

    try:
        result = svc.learn_from_feedback()
    except GenerationFailedError as e:
        console.print(f"[red]{e}[/red]")
        return

    if result.positive_count == 0 and result.negative_count == 0:
        console.print("[yellow]No feedback found. To improve targeting:[/yellow]")
        console.print("  - Import jobs you like: scout research <job_url>")
        console.print("  - Delete jobs you don't want: scout delete <job_id>")
        return

    if result.positive_count:
        console.print(f"[bold]Positive signals:[/bold] {result.positive_count} imported job(s)")
    if result.negative_count:
        console.print(f"[bold]Negative signals:[/bold] {result.negative_count} deleted job(s)")

    # Print insights
    if result.insights:
        console.print(Panel(result.insights, title="Key Insights"))

    targeting = result.targeting
    if targeting.get("primary_titles"):
        console.print("\n[bold green]Job Titles to Target:[/bold green]")
        for title in targeting["primary_titles"][:5]:
            console.print(f"  - {title}")
    if targeting.get("red_flag_keywords"):
        console.print("\n[bold red]Red Flag Keywords:[/bold red]")
        console.print(f"  {', '.join(targeting['red_flag_keywords'][:8])}")

    console.print("\n[green]Learning complete! Future searches will use these insights.[/green]")
    console.print("\n[dim]Run 'scout companies' or 'scout research' to use improved targeting.[/dim]")


@cli.command()
@click.argument("job_id")
@click.option("--reason", "-r", help="Reason for removing.")
@click.pass_context
def delete(ctx, job_id: str, reason: str | None):
    """Remove a job and learn from the feedback."""
    svc = ctx.obj["services"]["job"]

    try:
        result = svc.delete_job(job_id, reason)
    except JobNotFoundError:
        console.print(f"[red]Job not found: {job_id}[/red]")
        console.print("[dim]Use 'scout jobs' to see available job IDs[/dim]")
        return

    console.print(f"[green]Removed:[/green] {result.title} at {result.company}")
    console.print(f"[dim]This feedback will improve future targeting. Run 'scout learn' to update.[/dim]")


# ============================================================================
# Pipeline Management Commands
# ============================================================================


@cli.command("apply")
@click.argument("job_id")
@click.option("--via", help="How you applied.")
@click.option("--notes", help="Notes about the application.")
@click.option("--date", help="Application date (ISO format).")
@click.pass_context
def apply_job(ctx, job_id: str, via: str | None, notes: str | None, date: str | None):
    """Record that you submitted an application."""
    svc = ctx.obj["services"]["job"]
    config = ctx.obj["config"]

    try:
        svc.apply(job_id, via=via, notes=notes, date=date)
    except JobNotFoundError:
        console.print(f"[red]Job not found: {job_id}[/red]")
        console.print("[dim]Use 'scout jobs' to see available job IDs[/dim]")
        return
    except PipelineError as e:
        console.print(f"[red]{e}[/red]")
        return

    job_detail = svc.get_job(job_id)
    follow_up_days = config.get("preferences", {}).get("pipeline", {}).get("follow_up_days", 7)
    console.print(f"\n[green]Applied:[/green] {job_detail.title} at {job_detail.company}")
    if via:
        console.print(f"[dim]Via: {via}[/dim]")
    console.print(f"[dim]Follow-up reminder in {follow_up_days} days. Run 'scout next' to check.[/dim]")


@cli.command("status")
@click.argument("job_id")
@click.argument("stage", required=False)
@click.option("--outcome", help="Outcome when closing.")
@click.pass_context
def status(ctx, job_id: str, stage: str | None, outcome: str | None):
    """View or set pipeline stage for a job."""
    svc = ctx.obj["services"]["job"]

    try:
        job_detail = svc.get_job(job_id)
    except JobNotFoundError:
        console.print(f"[red]Job not found: {job_id}[/red]")
        console.print("[dim]Use 'scout jobs' to see available job IDs[/dim]")
        return

    if stage is None:
        # VIEW MODE
        entry = svc.get_pipeline_entry(job_id)
        if not entry:
            console.print(f"\n[yellow]{job_detail.title} at {job_detail.company} -- not tracked in pipeline[/yellow]")
            console.print("[dim]This job predates pipeline tracking or was not imported through standard commands.[/dim]")
            return

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        updated = datetime.fromisoformat(entry.updated_at)
        days_in_stage = (now - updated).days

        console.print(f"\n[bold]{job_detail.title}[/bold] at [cyan]{job_detail.company}[/cyan]")
        console.print(f"Current stage: [magenta]{entry.status}[/magenta] ({days_in_stage} days)")

        if entry.history:
            console.print()
            timeline_table = Table(title="Timeline")
            timeline_table.add_column("Date", style="dim")
            timeline_table.add_column("Stage", style="magenta")
            timeline_table.add_column("Trigger", style="cyan")

            for h in entry.history:
                try:
                    dt = datetime.fromisoformat(h.timestamp)
                    date_str = dt.strftime("%b %d %H:%M")
                except (ValueError, TypeError):
                    date_str = h.timestamp[:16] if len(h.timestamp) > 16 else h.timestamp
                timeline_table.add_row(date_str, h.stage, h.trigger)
            console.print(timeline_table)

        artifacts = entry.artifacts
        has_artifacts = any(v for v in artifacts.values())
        if has_artifacts:
            console.print("\n[bold]Artifacts:[/bold]")
            for atype, apath in artifacts.items():
                if apath:
                    console.print(f"  {atype}: [dim]{apath}[/dim]")

        if entry.notes:
            console.print("\n[bold]Notes:[/bold]")
            for n in entry.notes[-5:]:
                ts = n.get("timestamp", "?")
                try:
                    dt = datetime.fromisoformat(ts)
                    date_str = dt.strftime("%b %d")
                except (ValueError, TypeError):
                    date_str = ts[:10] if len(ts) > 10 else ts
                console.print(f"  [{date_str}] {n.get('text', '')}")
    else:
        # SET MODE
        if stage == "closed":
            if not outcome:
                console.print(f"[red]--outcome required when closing. Options: {', '.join(CLOSED_OUTCOMES)}[/red]")
                return
            try:
                svc.close(job_id, outcome)
                console.print(f"\n[green]Closed:[/green] {job_detail.title} at {job_detail.company} ({outcome})")
                console.print("[dim]This outcome will improve future targeting. Run 'scout learn' to update.[/dim]")
            except ValidationError as e:
                console.print(f"[red]{e}[/red]")
            except PipelineError as e:
                console.print(f"[red]{e}[/red]")
        else:
            try:
                svc.set_status(job_id, stage)
                console.print(f"\n[green]Updated:[/green] {job_detail.title} at {job_detail.company} -> {stage}")
            except ValidationError as e:
                console.print(f"[red]{e}[/red]")
                console.print(f"[dim]Valid stages: {', '.join(PIPELINE_STAGES)}[/dim]")
            except PipelineError as e:
                console.print(f"[red]{e}[/red]")


@cli.command("pipeline")
@click.option("--stage", "filter_stage", help="Show only jobs at a specific stage.")
@click.pass_context
def pipeline_view(ctx, filter_stage: str | None):
    """Kanban-style overview of all jobs by stage."""
    svc = ctx.obj["services"]["job"]

    try:
        overview = svc.get_pipeline_overview(filter_stage=filter_stage)
    except ValidationError as e:
        console.print(f"[red]{e}[/red]")
        console.print(f"[dim]Valid stages: {', '.join(PIPELINE_STAGES)}[/dim]")
        return

    if overview.total == 0:
        console.print("[yellow]No jobs in pipeline. Import or research jobs to start tracking.[/yellow]")
        return

    console.print()

    for stage_name in PIPELINE_STAGES:
        if stage_name not in overview.stages:
            continue
        entries = overview.stages[stage_name]
        stage_label = stage_name.upper().replace("_", " ")

        if not entries:
            console.print(f"  [dim]{stage_label} (0)[/dim]")
            continue

        console.print(f"  [bold]{stage_label} ({len(entries)})[/bold]")
        for entry in entries:
            label = f"{entry.title} at {entry.company}"
            if stage_name == "closed":
                console.print(f"    [dim]{label}[/dim]")
            else:
                console.print(f"    {label} [dim]({entry.id})[/dim]")
        console.print()

    # Summary
    parts = [f"{overview.total} opportunities"]
    for stage_name, count in overview.summary.items():
        if count and stage_name not in ("discovered", "closed"):
            parts.append(f"{count} {stage_name.replace('_', ' ')}")
    console.print(f"  [bold]Summary:[/bold] {' | '.join(parts)}")


@cli.command("next")
@click.pass_context
def next_actions(ctx):
    """Prioritized action dashboard -- what to do next."""
    svc = ctx.obj["services"]["job"]

    actionable = svc.get_actionable()

    overdue = actionable.overdue
    ready = actionable.ready_to_act
    in_progress = actionable.in_progress
    next_up = actionable.next_up

    if not any([overdue, ready, in_progress, next_up]):
        console.print("[yellow]No actionable items. Import or research jobs to get started.[/yellow]")
        return

    console.print()

    if overdue:
        console.print("[bold red]OVERDUE (action needed now)[/bold red]")
        for item in overdue:
            days = item.days_since_update or 0
            console.print(f"  [red]{item.job_id}[/red]  {item.title} at {item.company}")
            console.print(f"    {item.status.replace('_', ' ').title()} {days} days ago -- follow up or update status.")
        console.print()

    if ready:
        console.print("[bold green]READY TO APPLY (materials complete)[/bold green]")
        for item in ready:
            console.print(f"  [green]{item.job_id}[/green]  {item.title} at {item.company}")
            console.print(f"    [dim]scout apply {item.job_id} --via \"company site\"[/dim]")
        console.print()

    if in_progress:
        console.print("[bold yellow]IN PROGRESS (waiting)[/bold yellow]")
        for item in in_progress:
            days = item.days_since_update or 0
            console.print(f"  [yellow]{item.job_id}[/yellow]  {item.title} at {item.company}")
            console.print(f"    {item.status.replace('_', ' ').title()} -- {days} day(s) ago.")
        console.print()

    if next_up:
        console.print("[bold cyan]NEXT UP (highest-scored unstarted jobs)[/bold cyan]")
        for item in next_up[:5]:
            current = item.status
            if current == "discovered":
                suggestion = f"scout analyze {item.job_id}"
            else:
                suggestion = f"scout resume {item.job_id}"
            console.print(f"  [cyan]{item.job_id}[/cyan]  {item.title} at {item.company} (score: {item.match_score})")
            console.print(f"    [dim]{suggestion}[/dim]")
        if len(next_up) > 5:
            console.print(f"  [dim]... and {len(next_up) - 5} more[/dim]")
        console.print()


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
    """Analyze a job posting and match against your profile."""
    svc = ctx.obj["services"]["composer"]
    console.print(f"\n[bold blue]Analyzing job: {job_id}[/bold blue]\n")

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            progress.add_task("Analyzing job requirements...", total=None)
            result = svc.analyze_job(job_id)
        _print_analysis(result.analysis, job_id, svc)
    except (JobNotFoundError, ResumeNotFoundError, GenerationFailedError) as e:
        console.print(f"[red]{e}[/red]")


def _print_analysis(analysis, job_id, svc):
    """Print job analysis summary."""
    job = svc.data_store.get_job(job_id)
    job_summary = analysis.get("job_summary", {})
    match = analysis.get("match_assessment", {})
    recs = analysis.get("resume_recommendations", {})

    console.print(Panel(
        f"[bold]{job_summary.get('title', job.get('title', 'Unknown'))}[/bold] at "
        f"[cyan]{job_summary.get('company', job.get('company', 'Unknown'))}[/cyan]\n\n"
        f"[bold]Experience Required:[/bold] {job_summary.get('experience_required', 'Not specified')}",
        title="Job Summary"
    ))

    score = match.get("overall_score", "?")
    score_color = "green" if isinstance(score, int) and score >= 75 else "yellow" if isinstance(score, int) and score >= 50 else "red"
    console.print(f"\n[bold]Match Score:[/bold] [{score_color}]{score}/100[/{score_color}]")

    strengths = match.get("strengths", [])
    if strengths:
        console.print("\n[bold green]Your Strengths:[/bold green]")
        for s in strengths[:4]:
            console.print(f"  - {s}")

    gaps = match.get("gaps", [])
    if gaps:
        console.print("\n[bold yellow]Potential Gaps:[/bold yellow]")
        for g in gaps[:3]:
            console.print(f"  - {g}")

    domain_connections = match.get("domain_connections", [])
    if domain_connections:
        dc_lines = []
        for dc in domain_connections:
            conn_type = dc.get("connection_type", "unknown").replace("_", " ").title()
            dc_lines.append(
                f"[bold]{dc.get('candidate_experience', '?')}[/bold]\n"
                f"  -> {dc.get('target_domain', '?')} [dim]({conn_type})[/dim]\n"
                f"  [italic]{dc.get('reasoning', '')}[/italic]"
            )
        console.print(Panel("\n\n".join(dc_lines), title="[bold magenta]Domain Connections[/bold magenta]", border_style="magenta"))

    keywords = recs.get("keywords_to_include", [])
    if keywords:
        console.print("\n[bold]Keywords to Include:[/bold]")
        console.print(f"  {', '.join(keywords[:8])}")

    console.print("\n[dim]Run 'scout resume <job_id>' to generate a customized resume[/dim]")


@cli.command()
@click.argument("job_id")
@click.option("--format", "output_format", type=click.Choice(["pdf", "docx", "both"]), default=None)
@click.pass_context
def resume(ctx, job_id: str, output_format: str | None):
    """Generate a customized resume for a job."""
    svc = ctx.obj["services"]["composer"]
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")
    console.print(f"\n[bold blue]Generating resume for: {job_id}[/bold blue]\n")

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            progress.add_task("Generating customized resume...", total=None)
            result = svc.generate_resume(job_id, output_format=output_format)

        console.print(f"[green]Resume saved to:[/green] {result.markdown_path}")
        for fmt, path in result.artifacts.items():
            if path:
                console.print(f"[green]{fmt.upper()} saved to:[/green] {path}")
    except (JobNotFoundError, ResumeNotFoundError, GenerationFailedError) as e:
        console.print(f"[red]{e}[/red]")


@cli.command("cover-letter")
@click.argument("job_id")
@click.option("--format", "output_format", type=click.Choice(["pdf", "docx", "both"]), default=None)
@click.pass_context
def cover_letter(ctx, job_id: str, output_format: str | None):
    """Generate a cover letter for a job."""
    svc = ctx.obj["services"]["composer"]
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")
    console.print(f"\n[bold blue]Generating cover letter for: {job_id}[/bold blue]\n")

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            progress.add_task("Generating cover letter...", total=None)
            result = svc.generate_cover_letter(job_id, output_format=output_format)

        console.print(f"[green]Cover letter saved to:[/green] {result.markdown_path}")
        for fmt, path in result.artifacts.items():
            if path:
                console.print(f"[green]{fmt.upper()} saved to:[/green] {path}")
    except (JobNotFoundError, ResumeNotFoundError, GenerationFailedError) as e:
        console.print(f"[red]{e}[/red]")


@cli.command("resume-gen")
@click.argument("job_id")
@click.option("--format", "output_format", type=click.Choice(["pdf", "docx", "both"]), default=None)
@click.pass_context
def resume_gen(ctx, job_id: str, output_format: str | None):
    """Regenerate output from existing resume markdown."""
    svc = ctx.obj["services"]["composer"]
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")

    md_path = svc.find_document_by_job_id(job_id, "resume")
    if not md_path:
        console.print(f"[red]No resume markdown found for job: {job_id}[/red]")
        console.print("[dim]Run 'scout resume <job_id>' first to generate the resume.[/dim]")
        return

    fmt_label = "PDF + DOCX" if output_format == "both" else output_format.upper()
    console.print(f"\n[bold blue]Regenerating {fmt_label} from: {md_path.name}[/bold blue]\n")

    results = svc.regenerate_output(md_path, "resume", output_format)
    generated = {fmt: path for fmt, path in results.items() if path}
    if generated:
        for fmt, path in generated.items():
            console.print(f"[green]{fmt.upper()} saved to:[/green] {path}")
    else:
        console.print("[red]Output generation failed[/red]")


@cli.command("cover-letter-gen")
@click.argument("job_id")
@click.option("--format", "output_format", type=click.Choice(["pdf", "docx", "both"]), default=None)
@click.pass_context
def cover_letter_gen(ctx, job_id: str, output_format: str | None):
    """Regenerate output from existing cover letter markdown."""
    svc = ctx.obj["services"]["composer"]
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")

    md_path = svc.find_document_by_job_id(job_id, "cover-letter")
    if not md_path:
        console.print(f"[red]No cover letter markdown found for job: {job_id}[/red]")
        console.print("[dim]Run 'scout cover-letter <job_id>' first to generate the cover letter.[/dim]")
        return

    fmt_label = "PDF + DOCX" if output_format == "both" else output_format.upper()
    console.print(f"\n[bold blue]Regenerating {fmt_label} from: {md_path.name}[/bold blue]\n")

    results = svc.regenerate_output(md_path, "cover-letter", output_format)
    generated = {fmt: path for fmt, path in results.items() if path}
    if generated:
        for fmt, path in generated.items():
            console.print(f"[green]{fmt.upper()} saved to:[/green] {path}")
    else:
        console.print("[red]Output generation failed[/red]")


@cli.command("resume-improve")
@click.argument("job_id")
@click.option("--format", "output_format", type=click.Choice(["pdf", "docx", "both"]), default=None)
@click.pass_context
def resume_improve(ctx, job_id: str, output_format: str | None):
    """Iteratively improve a resume for better job alignment."""
    svc = ctx.obj["services"]["composer"]
    config = ctx.obj["config"]
    output_format = output_format or config.get("preferences", {}).get("output_format", "pdf")
    console.print(f"\n[bold blue]Improving resume for: {job_id}[/bold blue]\n")

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            progress.add_task("Improving resume (3-phase pipeline)...", total=None)
            result = svc.improve_resume(job_id, output_format=output_format)

        # Print edit summary
        metadata = result.metadata
        _print_edit_summary(
            metadata.get("edit_plan", {}),
            metadata.get("apply_report", []),
            metadata.get("audit_report", []),
        )

        console.print(f"\n[green]Resume improved and saved to:[/green] {result.markdown_path}")
        if metadata.get("edit_plan_path"):
            console.print(f"[dim]Edit plan saved to:[/dim] {metadata['edit_plan_path']}")
        for fmt, path in result.artifacts.items():
            if path:
                console.print(f"[green]{fmt.upper()} saved to:[/green] {path}")
    except (JobNotFoundError, ResumeNotFoundError, GenerationFailedError) as e:
        console.print(f"[red]{e}[/red]")


def _print_edit_summary(edit_plan, apply_report, audit_report):
    """Print structured edit summary."""
    edits = edit_plan.get("edit_plan", [])
    if not edits:
        console.print("[yellow]No edits were proposed.[/yellow]")
        return

    edit_lines = []
    for i, edit in enumerate(edits, 1):
        edit_type = edit.get("edit_type", "replace")
        target = edit.get("target", "unknown")
        rationale = edit.get("rationale", "")
        edit_lines.append(f"[bold]{i}. [{edit_type.upper()}][/bold] {target}")
        edit_lines.append(f"   [dim]{rationale}[/dim]")

    console.print(Panel("\n".join(edit_lines), title=f"[bold green]Edit Plan ({len(edits)} edits)[/bold green]", border_style="green"))

    failed = [r for r in apply_report if not r.get("applied")]
    if failed:
        fail_lines = [f"- {r.get('target', '?')}: {r.get('reason', 'unknown')}" for r in failed]
        console.print(Panel("\n".join(fail_lines), title="[bold yellow]Edits That Needed Fallback[/bold yellow]", border_style="yellow"))

    if audit_report:
        audit_lines = [f"- {item}" for item in audit_report]
        console.print(Panel("\n".join(audit_lines), title="[bold cyan]Credibility Audit[/bold cyan]", border_style="cyan"))

    remaining_gaps = edit_plan.get("remaining_gaps", [])
    if remaining_gaps:
        gap_lines = [f"- {gap}" for gap in remaining_gaps]
        console.print(Panel("\n".join(gap_lines), title="[dim]Remaining Gaps[/dim]", border_style="dim"))


@cli.command("interview-prep")
@click.argument("job_id")
@click.pass_context
def interview_prep(ctx, job_id: str):
    """Generate screening interview talking points for a job."""
    svc = ctx.obj["services"]["composer"]
    console.print(f"\n[bold blue]Generating interview prep for: {job_id}[/bold blue]\n")

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            progress.add_task("Generating interview prep...", total=None)
            result = svc.generate_interview_prep(job_id)

        metadata = result.metadata
        dc_count = metadata.get("domain_connection_count", 0)
        if dc_count > 0:
            console.print(f"  Domain connection talking points: [cyan]{dc_count}[/cyan]")
        console.print(f"  Sections generated: [cyan]{metadata.get('section_count', 0)}[/cyan]")
        console.print(f"\n[green]Interview prep saved to:[/green] {result.markdown_path}")
    except (JobNotFoundError, ResumeNotFoundError, GenerationFailedError) as e:
        console.print(f"[red]{e}[/red]")


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
    """Manage the experience bullet corpus."""
    pass


@corpus.command("build")
@click.pass_context
def corpus_build(ctx):
    """Build the experience bullet corpus from existing resumes."""
    svc = ctx.obj["services"]["corpus"]
    console.print("\n[bold blue]Building experience bullet corpus...[/bold blue]\n")

    try:
        metadata = svc.build()
        console.print("[green]Corpus built successfully![/green]\n")
        console.print(f"  Resumes processed: {metadata.get('resumes_processed', 0)}")
        console.print(f"  Experience entries: {metadata.get('experiences_count', 0)}")
        console.print(f"  Total bullets: {metadata.get('bullets_count', 0)}")
        console.print(f"  Skills indexed: {metadata.get('skills_indexed', 0)}")
        console.print(f"  Themes indexed: {metadata.get('themes_indexed', 0)}")
        console.print("\n[dim]Corpus saved to data/skills-corpus.json[/dim]")
    except GenerationFailedError as e:
        console.print(f"[red]{e}[/red]")


@corpus.command("update")
@click.pass_context
def corpus_update(ctx):
    """Update corpus with new bullets from recent resumes."""
    svc = ctx.obj["services"]["corpus"]
    console.print("\n[bold blue]Updating experience bullet corpus...[/bold blue]\n")

    try:
        metadata = svc.update()
        console.print("[green]Corpus updated successfully![/green]\n")
        console.print(f"  Resumes processed: {metadata.get('resumes_processed', 0)}")
        console.print(f"  Experience entries: {metadata.get('experiences_count', 0)}")
        console.print(f"  Total bullets: {metadata.get('bullets_count', 0)}")
    except GenerationFailedError as e:
        console.print(f"[red]{e}[/red]")


@corpus.command("stats")
@click.pass_context
def corpus_stats(ctx):
    """Show corpus statistics."""
    svc = ctx.obj["services"]["corpus"]

    stats = svc.get_stats()

    if not stats.version:
        console.print("[yellow]No corpus found. Run 'scout corpus build' first.[/yellow]")
        return

    console.print("\n[bold blue]Skills Corpus Statistics[/bold blue]\n")
    console.print(f"  Version: {stats.version}")
    console.print(f"  Generated: {stats.generated_at}")
    console.print(f"  Source resumes: {stats.source_resumes}")
    console.print(f"  Experience entries: {stats.experience_entries}")
    console.print(f"  Total bullets: {stats.total_bullets}")
    console.print(f"  Skills indexed: {stats.skills_indexed}")
    console.print(f"  Themes indexed: {stats.themes_indexed}")

    if stats.top_skills:
        console.print("\n[bold]Top 10 Skills:[/bold]")
        for s in stats.top_skills:
            console.print(f"  {s['skill']}: {s['bullet_count']} bullets")

    if stats.top_themes:
        console.print("\n[bold]Top 10 Themes:[/bold]")
        for t in stats.top_themes:
            console.print(f"  {t['theme']}: {t['bullet_count']} bullets")


# ============================================================================
# API Server Command
# ============================================================================


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to.")
@click.option("--port", default=8000, type=int, help="Port to bind to.")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development.")
def serve(host, port, reload):
    """Start the Talent Scout API server."""
    import uvicorn
    console.print(f"\n[bold blue]Starting Talent Scout API server...[/bold blue]")
    console.print(f"[dim]API docs at http://{host}:{port}/docs[/dim]\n")
    uvicorn.run("api.app:create_app", host=host, port=port, reload=reload, factory=True)


if __name__ == "__main__":
    cli()
