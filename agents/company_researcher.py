"""Company Researcher Agent - deep research on companies and job discovery."""

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from config_loader import get_anthropic_api_key

console = Console()

RESEARCH_SYSTEM_PROMPT = """You are a company research analyst helping with a job search. Your task is to provide comprehensive research on a specific company.

Research and provide:
1. **Company Overview**: Mission, what they do, their products/services
2. **Recent News**: Any significant recent developments, funding, acquisitions, leadership changes (from the last 6-12 months)
3. **Financial Health**: For public companies, recent performance. For private, funding status and investor backing
4. **Engineering Culture**: What's known about their tech stack, engineering practices, culture
5. **Key Leadership**: CEO, CTO, VP Engineering, and other relevant leaders
6. **Office Locations**: Where they have engineering presence

Return your response as valid JSON matching this schema:
{
  "company_name": "Official Company Name",
  "website": "https://...",
  "description": "What the company does in 2-3 sentences",
  "mission": "Company mission statement or values",
  "industry": "Industry/sector",
  "founded": "Year founded",
  "headquarters": "City, State",
  "employee_count": "Approximate employee count",
  "public": true/false,
  "stock_ticker": "TICK or null",
  "recent_news": [
    {"headline": "...", "summary": "...", "date": "approximate date"}
  ],
  "financial_summary": "Brief financial health summary",
  "engineering_culture": "What's known about eng culture, tech stack",
  "leadership": [
    {"name": "...", "title": "...", "linkedin": "url or null"}
  ],
  "office_locations": ["City, State", ...],
  "relevance_notes": "Why this company might be good for an Engineering Manager / TPM role"
}

Be accurate and factual. If you're unsure about something, say so rather than making it up."""

JOB_SEARCH_SYSTEM_PROMPT = """You are a job search assistant. Given information about a company, identify current job openings that match these target roles:
- Engineering Manager
- Software Manager
- Technical Product Manager
- Director of Analytics Engineering
- Director of Engineering
- VP of Engineering

Also look for related roles like:
- Senior Engineering Manager
- Group Engineering Manager
- Head of Engineering
- Principal Product Manager (Technical)

Based on what you know about this company, list any current or likely job openings in these categories.

Return your response as valid JSON:
{
  "jobs": [
    {
      "title": "Job Title",
      "department": "Engineering/Product/etc",
      "location": "City, State or Remote",
      "location_type": "boca|palo|remote",
      "url": "careers page URL if known, otherwise null",
      "posted_date": "approximate date or null",
      "requirements_summary": "Key requirements if known",
      "match_score": 0-100,
      "match_notes": "Why this role matches the candidate profile"
    }
  ],
  "careers_page": "URL to company careers page",
  "notes": "Any notes about job search at this company"
}

For location_type:
- "boca" = Boca Raton, South Florida, Miami area
- "palo" = Palo Alto, San Francisco Bay Area, Silicon Valley
- "remote" = Remote/distributed

Be realistic - only include jobs you have reasonable confidence exist or are likely to exist based on company size and typical hiring patterns."""

JOB_URL_PARSE_PROMPT = """You are a job posting parser. Given the raw content from a job posting URL, extract the key information.

Return your response as valid JSON:
{
  "company": "Company Name",
  "title": "Job Title",
  "department": "Engineering/Product/etc",
  "location": "City, State or Remote",
  "location_type": "boca|palo|remote",
  "posted_date": "Date if found, otherwise null",
  "requirements_summary": "Key requirements (years experience, skills, etc)",
  "responsibilities_summary": "Key responsibilities",
  "compensation": "Salary/compensation if mentioned, otherwise null",
  "match_score": 0-100,
  "match_notes": "Assessment of how well this matches an Engineering Manager / Technical Product Manager profile"
}

For location_type, use these rules:
- "boca" = Boca Raton, South Florida, Miami, Fort Lauderdale, Palm Beach, or anywhere in Florida
- "palo" = Palo Alto, San Francisco, Bay Area, Silicon Valley, San Jose, Mountain View, Sunnyvale, or anywhere in the SF Bay Area
- "remote" = Remote, distributed, work from anywhere, or hybrid with remote option

If the location doesn't match boca or palo, default to "remote".

For match_score, consider how well the role aligns with these target profiles:
- Engineering Manager (team leadership, technical management, software delivery)
- Technical Product Manager (product strategy with technical depth)
- Director of Engineering (senior leadership, multiple teams)
- Director of Analytics Engineering (data platform leadership)

Be thorough in extracting requirements and responsibilities."""


class CompanyResearcherAgent:
    """Agent that researches companies and discovers job openings."""

    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=get_anthropic_api_key())
        self.data_dir = Path(__file__).parent.parent / "data"
        self.research_dir = self.data_dir / "research"
        self.research_dir.mkdir(parents=True, exist_ok=True)
        self.learned_preferences = self._load_learned_preferences()

    def _load_learned_preferences(self) -> dict | None:
        """Load learned preferences if available."""
        prefs_file = self.data_dir / "learned-preferences.json"
        if prefs_file.exists():
            try:
                with open(prefs_file) as f:
                    prefs = json.load(f)
                    console.print("[dim]Using learned preferences from job feedback[/dim]")
                    return prefs
            except Exception:
                pass
        return None

    def _build_learned_context(self) -> str:
        """Build additional prompt context from learned preferences."""
        if not self.learned_preferences:
            return ""

        parts = ["\n\n--- LEARNED PREFERENCES FROM USER FEEDBACK ---"]

        targeting = self.learned_preferences.get("improved_targeting", {})
        improvements = self.learned_preferences.get("prompt_improvements", {})
        negative = self.learned_preferences.get("negative_analysis", {})
        scoring = self.learned_preferences.get("scoring_adjustments", {})

        # POSITIVE SIGNALS - what to look for
        parts.append("\n## POSITIVE SIGNALS (prioritize these):")

        primary_titles = targeting.get("primary_titles", [])
        if primary_titles:
            parts.append(f"Target job titles: {', '.join(primary_titles[:5])}")

        must_have = targeting.get("must_have_keywords", [])
        if must_have:
            parts.append(f"Must-have keywords: {', '.join(must_have[:8])}")

        nice_to_have = targeting.get("nice_to_have_keywords", [])
        if nice_to_have:
            parts.append(f"Bonus keywords (boost score): {', '.join(nice_to_have[:8])}")

        # NEGATIVE SIGNALS - what to avoid
        has_negative = False
        negative_parts = ["\n## NEGATIVE SIGNALS (deprioritize/penalize these):"]

        titles_to_avoid = targeting.get("titles_to_avoid", [])
        if titles_to_avoid:
            negative_parts.append(f"Avoid job titles containing: {', '.join(titles_to_avoid[:5])}")
            has_negative = True

        red_flags = targeting.get("red_flag_keywords", [])
        if red_flags:
            negative_parts.append(f"Red flag keywords (lower score): {', '.join(red_flags[:8])}")
            has_negative = True

        role_red_flags = negative.get("role_red_flags", [])
        if role_red_flags:
            negative_parts.append(f"Role characteristics to avoid: {', '.join(role_red_flags[:5])}")
            has_negative = True

        if has_negative:
            parts.extend(negative_parts)

        # Exclusions from prompt improvements
        exclusions = improvements.get("job_search_exclusions", "")
        if exclusions:
            parts.append(f"\nExclusion rules: {exclusions}")

        # Additional guidance
        job_search_additions = improvements.get("job_search_additions", "")
        if job_search_additions:
            parts.append(f"\nAdditional guidance: {job_search_additions}")

        # Scoring criteria
        scoring_criteria = improvements.get("match_scoring_criteria", "")
        if scoring_criteria:
            parts.append(f"\nScoring criteria: {scoring_criteria}")

        # Scoring adjustments
        boost_factors = scoring.get("boost_factors", [])
        penalty_factors = scoring.get("penalty_factors", [])
        if boost_factors or penalty_factors:
            parts.append("\n## SCORING ADJUSTMENTS:")
            if boost_factors and isinstance(boost_factors, list):
                parts.append(f"Boost score for: {', '.join(boost_factors[:5])}")
            if penalty_factors and isinstance(penalty_factors, list):
                parts.append(f"Penalize score for: {', '.join(penalty_factors[:5])}")

        parts.append("\n--- END LEARNED PREFERENCES ---")

        return "\n".join(parts)

    def research(self, company_name: str) -> dict:
        """Research a company and find job openings."""
        slug = self._slugify(company_name)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Company research
            task = progress.add_task(f"Researching {company_name}...", total=None)
            company_info = self._research_company(company_name)

            # Step 2: Job search
            progress.update(task, description=f"Finding jobs at {company_name}...")
            jobs_info = self._find_jobs(company_name, company_info)

            # Step 3: Try to fetch careers page
            progress.update(task, description="Checking careers page...")
            careers_data = self._fetch_careers_page(jobs_info.get("careers_page"))

        # Combine results
        result = {
            "company": company_info,
            "jobs": jobs_info.get("jobs", []),
            "careers_page": jobs_info.get("careers_page"),
            "search_notes": jobs_info.get("notes"),
            "researched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save research
        self._save_research(slug, result)

        # Add jobs to location files
        self._save_jobs(company_name, jobs_info.get("jobs", []))

        # Print summary
        self._print_summary(company_info, jobs_info.get("jobs", []))

        return result

    def import_job_from_markdown(self, content: str, filename: str) -> dict | None:
        """Import a job posting from markdown content (copy-pasted job description).

        Args:
            content: The markdown/text content of the job description
            filename: The source filename (for reference)

        Returns:
            The imported job dict, or None if parsing failed
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Parsing {filename}...", total=None)

            # Parse with Claude (reuse the same parsing logic)
            job = self._parse_job_posting(f"manual import from {filename}", content)

            if not job:
                console.print(f"[red]Could not parse job from {filename}[/red]")
                return None

        # Add ID and source tracking
        company_name = job.get("company") or "unknown"
        company_slug = self._slugify(company_name)
        job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        job["url"] = None  # No URL for manual imports
        job["source"] = "imported"  # Mark as manually imported for learning
        job["imported_at"] = datetime.now(timezone.utc).isoformat()
        job["source_file"] = filename
        job["company"] = company_name  # Ensure company is set

        # Save to appropriate location file
        self._save_jobs(company_name, [job])

        # Print summary
        self._print_job_summary(job)

        return job

    def import_job_from_url(self, url: str) -> dict | None:
        """Import a job posting from a URL."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Fetch the URL
            task = progress.add_task("Fetching job posting...", total=None)
            content = self._fetch_url_content(url)

            if not content:
                console.print("[red]Could not fetch job posting from URL[/red]")
                return None

            # Step 2: Parse with Claude
            progress.update(task, description="Parsing job details...")
            job = self._parse_job_posting(url, content)

            if not job:
                console.print("[red]Could not parse job posting[/red]")
                return None

        # Add ID, URL, and source tracking
        company_name = job.get("company") or "unknown"
        company_slug = self._slugify(company_name)
        job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        job["url"] = url
        job["source"] = "imported"  # Mark as manually imported for learning
        job["imported_at"] = datetime.now(timezone.utc).isoformat()
        job["company"] = company_name  # Ensure company is set

        # Save to appropriate location file
        self._save_jobs(company_name, [job])

        # Print summary
        self._print_job_summary(job)

        return job

    def _fetch_url_content(self, url: str) -> str | None:
        """Fetch content from a URL."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.text
                else:
                    console.print(f"[red]HTTP {response.status_code} fetching URL[/red]")
        except Exception as e:
            console.print(f"[red]Error fetching URL: {e}[/red]")
        return None

    def _parse_job_posting(self, url: str, content: str) -> dict | None:
        """Parse job posting content with Claude."""
        # Truncate content if too long (keep first 50k chars)
        if len(content) > 50000:
            content = content[:50000] + "\n... [truncated]"

        # Build system prompt with learned preferences for scoring
        system_prompt = JOB_URL_PARSE_PROMPT + self._build_url_parse_context()

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Parse this job posting from {url}:\n\n{content}",
                }
            ],
        )

        return self._parse_json_response(response.content[0].text)

    def _build_url_parse_context(self) -> str:
        """Build learned context specifically for URL parsing/scoring."""
        if not self.learned_preferences:
            return ""

        parts = ["\n\n--- LEARNED SCORING PREFERENCES ---"]
        parts.append("Apply these preferences when calculating match_score:")

        targeting = self.learned_preferences.get("improved_targeting", {})
        negative = self.learned_preferences.get("negative_analysis", {})
        scoring = self.learned_preferences.get("scoring_adjustments", {})

        # Boost factors
        primary_titles = targeting.get("primary_titles", [])
        if primary_titles:
            parts.append(f"\nBOOST SCORE (+15-25 points) for roles matching: {', '.join(primary_titles[:5])}")

        must_have = targeting.get("must_have_keywords", [])
        if must_have:
            parts.append(f"BOOST SCORE (+10 points) if job contains: {', '.join(must_have[:6])}")

        boost_factors = scoring.get("boost_factors", [])
        if boost_factors and isinstance(boost_factors, list):
            parts.append(f"Additional boost factors: {', '.join(boost_factors[:4])}")

        # Penalty factors
        titles_to_avoid = targeting.get("titles_to_avoid", [])
        if titles_to_avoid:
            parts.append(f"\nPENALIZE SCORE (-20-30 points) for roles matching: {', '.join(titles_to_avoid[:5])}")

        red_flags = targeting.get("red_flag_keywords", [])
        if red_flags:
            parts.append(f"PENALIZE SCORE (-15 points) if job contains: {', '.join(red_flags[:6])}")

        role_red_flags = negative.get("role_red_flags", [])
        if role_red_flags:
            parts.append(f"PENALIZE SCORE (-10 points) for: {', '.join(role_red_flags[:4])}")

        penalty_factors = scoring.get("penalty_factors", [])
        if penalty_factors and isinstance(penalty_factors, list):
            parts.append(f"Additional penalty factors: {', '.join(penalty_factors[:4])}")

        parts.append("\nApply these adjustments to arrive at the final match_score.")
        parts.append("--- END SCORING PREFERENCES ---")

        return "\n".join(parts)

    def _print_job_summary(self, job: dict) -> None:
        """Print summary of imported job."""
        company = job.get("company", "Unknown")
        title = job.get("title", "Unknown")
        location = job.get("location", "Unknown")
        location_type = job.get("location_type", "remote")
        score = job.get("match_score", "?")
        requirements = job.get("requirements_summary", "Not specified")

        console.print(
            Panel(
                f"[bold]{title}[/bold] at [cyan]{company}[/cyan]\n"
                f"[dim]Location: {location} ({location_type})[/dim]\n"
                f"[dim]Match Score: {score}/100[/dim]\n\n"
                f"[bold]Requirements:[/bold]\n{requirements}\n\n"
                f"[dim]ID: {job['id']}[/dim]",
                title="Job Imported",
            )
        )

    def _research_company(self, company_name: str) -> dict:
        """Get detailed company research from Claude."""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=RESEARCH_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Research this company: {company_name}\n\nProvide comprehensive information for a job seeker targeting Engineering Manager and Technical Product Manager roles.",
                }
            ],
        )

        return self._parse_json_response(response.content[0].text)

    def _find_jobs(self, company_name: str, company_info: dict) -> dict:
        """Find job openings at the company."""
        context = json.dumps(company_info, indent=2) if company_info else "No additional context"

        # Build enhanced prompt with learned preferences
        learned_context = self._build_learned_context()

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=JOB_SEARCH_SYSTEM_PROMPT + learned_context,
            messages=[
                {
                    "role": "user",
                    "content": f"""Find job openings at {company_name}.

Company context:
{context}

Target locations (in priority order):
1. Boca Raton / South Florida
2. Palo Alto / Bay Area
3. Remote

Find relevant Engineering Manager, Director, and Technical Product Manager roles.""",
                }
            ],
        )

        jobs_data = self._parse_json_response(response.content[0].text)

        # Add unique IDs and source to jobs
        for job in jobs_data.get("jobs", []):
            job["id"] = f"JOB-{self._slugify(company_name).upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
            job["company"] = company_name
            job["source"] = "discovered"  # Mark as auto-discovered

        return jobs_data

    def _fetch_careers_page(self, url: str | None) -> dict | None:
        """Attempt to fetch and analyze a careers page."""
        if not url:
            return None

        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return {"url": url, "status": "accessible", "content_length": len(response.text)}
        except Exception as e:
            console.print(f"[dim]Could not fetch careers page: {e}[/dim]")

        return {"url": url, "status": "not_accessible"}

    def _parse_json_response(self, text: str) -> dict:
        """Parse Claude's JSON response."""
        try:
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing response: {e}[/red]")
            return {}

    def _slugify(self, name: str) -> str:
        """Convert company name to slug."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug

    def _save_research(self, slug: str, data: dict) -> None:
        """Save research to JSON file."""
        output_path = self.research_dir / f"{slug}.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        console.print(f"[dim]Saved research to {output_path}[/dim]")

    def _save_jobs(self, company_name: str, jobs: list[dict]) -> None:
        """Save jobs to location-specific files."""
        if not jobs:
            return

        # Group jobs by location
        jobs_by_location: dict[str, list] = {"boca": [], "palo": [], "remote": []}

        for job in jobs:
            loc = job.get("location_type", "remote")
            if loc in jobs_by_location:
                jobs_by_location[loc].append(job)

        # Update each location file
        for location, location_jobs in jobs_by_location.items():
            if not location_jobs:
                continue

            jobs_file = self.data_dir / f"jobs-{location}.json"

            # Load existing jobs
            existing_data = {"jobs": []}
            if jobs_file.exists():
                with open(jobs_file) as f:
                    existing_data = json.load(f)

            # Add new jobs (avoid duplicates by ID, or by company+title+source for discovered jobs)
            existing_ids = {j.get("id") for j in existing_data.get("jobs", [])}
            existing_discovered = {
                (j["company"], j["title"])
                for j in existing_data.get("jobs", [])
                if j.get("source") != "imported"
            }

            added_count = 0
            for job in location_jobs:
                # Skip if exact same ID already exists
                if job.get("id") in existing_ids:
                    continue

                # For discovered jobs, skip if company+title matches another discovered job
                # But always allow imported jobs (user explicitly added them)
                if job.get("source") != "imported":
                    key = (job["company"], job["title"])
                    if key in existing_discovered:
                        continue
                    existing_discovered.add(key)

                existing_data["jobs"].append(job)
                existing_ids.add(job.get("id"))
                added_count += 1

            # Save updated jobs (only if something was added)
            if added_count > 0:
                existing_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                with open(jobs_file, "w") as f:
                    json.dump(existing_data, f, indent=2)
                console.print(f"[dim]Added {added_count} jobs to {jobs_file}[/dim]")

    def _print_summary(self, company_info: dict, jobs: list[dict]) -> None:
        """Print research summary."""
        if company_info:
            name = company_info.get("company_name", "Unknown")
            desc = company_info.get("description", "No description")
            industry = company_info.get("industry", "Unknown")
            employees = company_info.get("employee_count", "Unknown")
            public = "📈 Public" if company_info.get("public") else "🏢 Private"

            console.print(
                Panel(
                    f"[bold]{name}[/bold] {public}\n"
                    f"[dim]{industry} • ~{employees} employees[/dim]\n\n"
                    f"{desc}",
                    title="Company Overview",
                )
            )

        if jobs:
            console.print(f"\n[bold]Found {len(jobs)} relevant job(s):[/bold]")
            for job in jobs[:5]:
                score = job.get("match_score", "?")
                loc = job.get("location", "Unknown")
                console.print(
                    f"  • {job['title']} [dim]({loc}, score: {score})[/dim]"
                )
                console.print(f"    [dim]ID: {job['id']}[/dim]")

            if len(jobs) > 5:
                console.print(f"  [dim]... and {len(jobs) - 5} more[/dim]")
        else:
            console.print("\n[yellow]No matching jobs found[/yellow]")
