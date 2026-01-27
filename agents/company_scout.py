"""Company Scout Agent - discovers and prioritizes target companies."""

import json
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from config_loader import get_anthropic_api_key

console = Console()

LOCATION_DESCRIPTIONS = {
    "boca": "Boca Raton, Florida or South Florida (Miami, Fort Lauderdale, Palm Beach area)",
    "palo": "Palo Alto, California or the San Francisco Bay Area / Silicon Valley",
    "remote": "remote-friendly companies that allow fully remote work",
}

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


class CompanyScoutAgent:
    """Agent that scouts and prioritizes target companies."""

    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=get_anthropic_api_key())
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
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

        positive_analysis = self.learned_preferences.get("positive_analysis", self.learned_preferences.get("analysis", {}))
        negative_analysis = self.learned_preferences.get("negative_analysis", {})
        targeting = self.learned_preferences.get("improved_targeting", {})
        improvements = self.learned_preferences.get("prompt_improvements", {})

        # POSITIVE SIGNALS
        parts.append("\n## POSITIVE SIGNALS (prioritize these):")

        industries = positive_analysis.get("industry_patterns", [])
        if industries:
            parts.append(f"Preferred industries: {', '.join(industries[:5])}")

        company_chars = positive_analysis.get("company_characteristics", [])
        if company_chars:
            parts.append(f"Preferred company traits: {', '.join(company_chars[:5])}")

        ideal_profile = targeting.get("ideal_company_profile", "")
        if ideal_profile:
            parts.append(f"Ideal company profile: {ideal_profile}")

        # NEGATIVE SIGNALS
        has_negative = False
        negative_parts = ["\n## NEGATIVE SIGNALS (deprioritize these):"]

        companies_to_avoid = targeting.get("companies_to_avoid", "")
        if companies_to_avoid:
            negative_parts.append(f"Company types to avoid: {companies_to_avoid}")
            has_negative = True

        company_red_flags = negative_analysis.get("company_red_flags", [])
        if company_red_flags:
            negative_parts.append(f"Company red flags: {', '.join(company_red_flags[:5])}")
            has_negative = True

        if has_negative:
            parts.extend(negative_parts)

        # Additional guidance
        scout_additions = improvements.get("company_scout_additions", "")
        if scout_additions:
            parts.append(f"\nAdditional guidance: {scout_additions}")

        parts.append("\n--- END LEARNED PREFERENCES ---")

        return "\n".join(parts)

    def scout(self, location: str, count: int = 15) -> list[dict]:
        """Scout companies for a given location."""
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
            system_prompt = SCOUT_SYSTEM_PROMPT + self._build_learned_context()

            # Call Claude
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )

            progress.update(task, description="Processing results...")

            # Parse response
            companies = self._parse_response(response.content[0].text)

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
        location_desc = LOCATION_DESCRIPTIONS.get(location, location)

        seed_section = ""
        if seed_companies:
            seed_list = "\n".join(f"- {name}" for name in seed_companies)
            seed_section = f"""
Here are some seed companies I'm interested in. Include any that have presence in {location_desc}:
{seed_list}

Expand on this list with additional companies that match my criteria.
"""

        return f"""Find {count} technology companies that have offices or presence in {location_desc}.

{seed_section}

Target roles I'm looking for:
- Engineering Manager
- Software Manager
- Technical Product Manager
- Director of Analytics Engineering

Preferences:
- Prefer public companies or well-funded late-stage startups
- Software should be a revenue driver for the company
- Strong engineering culture is important
- Minimum ~100 employees

Return exactly {count} companies as JSON. Prioritize quality and fit over quantity."""

    def _parse_response(self, text: str) -> list[dict]:
        """Parse Claude's response into structured data."""
        # Try to extract JSON from the response
        try:
            # Handle case where response might have markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text.strip())
            return data.get("companies", [])
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing response: {e}[/red]")
            console.print(f"[dim]Raw response: {text[:500]}...[/dim]")
            return []

    def _save_results(self, location: str, companies: list[dict]) -> None:
        """Save results to JSON file."""
        output_path = self.data_dir / f"companies-{location}.json"

        data = {
            "location": location,
            "location_description": LOCATION_DESCRIPTIONS.get(location, location),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(companies),
            "companies": companies,
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        console.print(f"[dim]Saved to {output_path}[/dim]")

    def _print_summary(self, companies: list[dict]) -> None:
        """Print a summary of found companies."""
        console.print("\n[bold]Top companies found:[/bold]")
        for i, company in enumerate(companies[:5], 1):
            score = company.get("priority_score", "?")
            public = "📈" if company.get("public") else "🏢"
            console.print(
                f"  {i}. {public} {company['name']} "
                f"[dim](score: {score})[/dim]"
            )

        if len(companies) > 5:
            console.print(f"  [dim]... and {len(companies) - 5} more[/dim]")
