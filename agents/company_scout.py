"""Company Scout Agent - discovers and prioritizes target companies."""

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from config_loader import get_location_slug, get_location_description
from data_store import DataStore
from .base_agent import BaseAgent

console = Console()

SCOUT_SYSTEM_PROMPT = """You are a company research assistant helping with a job search. Your task is to identify and evaluate technology companies that would be good targets for a job search.

The ideal target companies:
- Are technology companies where software is a revenue driver (not just a cost center)
- Have strong engineering cultures
- Are financially stable (prefer public companies or well-funded private)
- Have roles matching: Engineering Manager, Software Manager, Technical Product Manager, Director of Analytics Engineering

For each company, provide:
1. Company name
2. Website URL
3. Headquarters location
4. Industry/sector
5. Approximate employee count
6. Whether publicly traded
7. A priority score from 0-100 based on fit
8. Brief notes on why this company is a good target

Return your response as valid JSON matching this schema:
{
  "companies": [
    {
      "name": "Company Name",
      "website": "https://example.com",
      "hq_location": "City, State",
      "industry": "Industry description",
      "employee_count": "1000-5000",
      "public": true,
      "priority_score": 85,
      "notes": "Why this company is a good fit"
    }
  ]
}

Be thorough and accurate. Only include companies you're confident exist and match the criteria."""


class CompanyScoutAgent(BaseAgent):
    """Agent that scouts and prioritizes target companies."""

    def __init__(self, config: dict):
        """Initialize the company scout agent.

        Args:
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.data_store = DataStore(config)

    def scout(self, location: str, count: int = 15) -> list[dict]:
        """Scout companies for a given location.

        Args:
            location: Target location (e.g., "Palo Alto, CA" or "remote").
            count: Number of companies to find.

        Returns:
            List of company dictionaries sorted by priority score.
        """
        # Get seed companies
        target_companies = self.config.get("target_companies", [])
        excluded_companies = self.config.get("excluded_companies", [])
        excluded_names = {c["name"].lower() for c in excluded_companies}

        # Filter seed companies relevant to this location
        seed_names = [c["name"] for c in target_companies]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Researching companies for {location}...", total=None
            )

            # Build prompt with learned preferences
            prompt = self._build_prompt(location, seed_names, count)
            system_prompt = SCOUT_SYSTEM_PROMPT + self._build_learned_context("company_scout")

            # Call Claude
            try:
                result = self.client.complete_json(
                    system=system_prompt,
                    user=prompt,
                    max_tokens=4096,
                )
                companies = result.get("companies", [])
            except ValueError as e:
                console.print(f"[red]Error parsing response: {e}[/red]")
                companies = []

            progress.update(task, description="Processing results...")

            # Filter excluded companies
            companies = [
                c for c in companies if c["name"].lower() not in excluded_names
            ]

            # Sort by priority score
            companies.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

            # Limit to requested count
            companies = companies[:count]

        # Save results
        self._save_results(location, companies)

        # Print summary
        self._print_summary(companies)

        return companies

    def _build_prompt(
        self, location: str, seed_companies: list[str], count: int
    ) -> str:
        """Build the prompt for Claude."""
        location_desc = get_location_description(location)

        seed_section = ""
        if seed_companies:
            seed_list = "\n".join(f"- {name}" for name in seed_companies)
            seed_section = f"""
Here are some seed companies I'm interested in. Include any that have presence in {location_desc}:
{seed_list}

Expand on this list with additional companies that match my criteria.
"""

        # Get target roles from config
        target_roles = self.config.get("preferences", {}).get(
            "target_roles",
            [
                "Engineering Manager",
                "Software Manager",
                "Technical Product Manager",
                "Director of Analytics Engineering",
            ],
        )
        roles_text = "\n".join(f"- {role}" for role in target_roles)

        # Get company preferences
        min_size = self.config.get("preferences", {}).get("min_company_size", 100)
        prefer_public = self.config.get("preferences", {}).get(
            "prefer_public_companies", True
        )
        public_pref = (
            "Prefer public companies or well-funded late-stage startups"
            if prefer_public
            else "Consider both public and private companies"
        )

        return f"""Find {count} technology companies that have offices or presence in {location_desc}.

{seed_section}

Target roles I'm looking for:
{roles_text}

Preferences:
- {public_pref}
- Software should be a revenue driver for the company
- Strong engineering culture is important
- Minimum ~{min_size} employees

Return exactly {count} companies as JSON. Prioritize quality and fit over quantity."""

    def _save_results(self, location: str, companies: list[dict]) -> None:
        """Save results to JSON file."""
        slug = get_location_slug(location)
        self.data_store.save_companies(companies, slug, location)
        console.print(f"[dim]Saved to data/companies-{slug}.json[/dim]")

    def _print_summary(self, companies: list[dict]) -> None:
        """Print a summary of found companies."""
        console.print("\n[bold]Top companies found:[/bold]")
        for i, company in enumerate(companies[:5], 1):
            score = company.get("priority_score", "?")
            public = "public" if company.get("public") else "private"
            console.print(
                f"  {i}. {company['name']} "
                f"[dim]({public}, score: {score})[/dim]"
            )

        if len(companies) > 5:
            console.print(f"  [dim]... and {len(companies) - 5} more[/dim]")
