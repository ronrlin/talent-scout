"""Base service class with shared functionality.

Extracted from agents/base_agent.py. No Rich imports, no console output.
Returns structured data; raises typed exceptions.
"""

import json
import logging
from pathlib import Path

from claude_client import ClaudeClient
from config_loader import load_config
from data_store import DataStore
from pipeline_store import PipelineStore

logger = logging.getLogger(__name__)


class BaseService:
    """Base class for all services with shared functionality.

    Mirrors BaseAgent's constructor and utility methods but without
    Rich console output. Services log instead of printing.
    """

    def __init__(
        self,
        config: dict | None = None,
        data_store: DataStore | None = None,
        pipeline: PipelineStore | None = None,
        client: ClaudeClient | None = None,
    ):
        """Initialize the service.

        Args:
            config: Configuration dictionary. If None, loads from config.json.
            data_store: DataStore instance. If None, creates one from config.
            pipeline: PipelineStore instance. If None, creates one from config.
            client: ClaudeClient instance. If None, creates one.
        """
        self.config = config or load_config()
        self.data_store = data_store or DataStore(self.config)
        self.pipeline = pipeline or PipelineStore(self.config)
        self.client = client or ClaudeClient()

        self.data_dir = Path(__file__).parent.parent / "data"
        self.output_dir = Path(__file__).parent.parent / "output"
        self.input_dir = Path(__file__).parent.parent / "input"

        # Ensure data directory exists
        self.data_dir.mkdir(exist_ok=True)

        # Load learned preferences if available
        self.learned_preferences = self._load_learned_preferences()

    def _load_learned_preferences(self) -> dict | None:
        """Load learned preferences from data/learned-preferences.json.

        Returns:
            Preferences dictionary if file exists and is valid, None otherwise.
        """
        prefs_file = self.data_dir / "learned-preferences.json"
        if prefs_file.exists():
            try:
                with open(prefs_file) as f:
                    prefs = json.load(f)
                    logger.debug("Loaded learned preferences from job feedback")
                    return prefs
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def _build_learned_context(self, context_type: str) -> str:
        """Build context string from learned preferences for prompt injection.

        Args:
            context_type: Type of context to build. One of:
                - "company_scout": For company discovery prompts
                - "job_search": For job search/discovery prompts
                - "job_scoring": For job match scoring prompts

        Returns:
            Formatted string to append to prompts, or empty string if no preferences.
        """
        if not self.learned_preferences:
            return ""

        if context_type == "company_scout":
            return self._build_company_scout_context()
        elif context_type == "job_search":
            return self._build_job_search_context()
        elif context_type == "job_scoring":
            return self._build_job_scoring_context()
        else:
            return ""

    def _build_company_scout_context(self) -> str:
        """Build learned context for company scouting prompts."""
        parts = ["\n\n--- LEARNED PREFERENCES FROM USER FEEDBACK ---"]

        positive = self.learned_preferences.get(
            "positive_analysis", self.learned_preferences.get("analysis", {})
        )
        negative = self.learned_preferences.get("negative_analysis", {})
        targeting = self.learned_preferences.get("improved_targeting", {})
        improvements = self.learned_preferences.get("prompt_improvements", {})

        parts.append("\n## POSITIVE SIGNALS (prioritize these):")

        industries = positive.get("industry_patterns", [])
        if industries:
            parts.append(f"Preferred industries: {', '.join(industries[:5])}")

        company_chars = positive.get("company_characteristics", [])
        if company_chars:
            parts.append(f"Preferred company traits: {', '.join(company_chars[:5])}")

        ideal_profile = targeting.get("ideal_company_profile", "")
        if ideal_profile:
            parts.append(f"Ideal company profile: {ideal_profile}")

        has_negative = False
        negative_parts = ["\n## NEGATIVE SIGNALS (deprioritize these):"]

        companies_to_avoid = targeting.get("companies_to_avoid", "")
        if companies_to_avoid:
            negative_parts.append(f"Company types to avoid: {companies_to_avoid}")
            has_negative = True

        company_red_flags = negative.get("company_red_flags", [])
        if company_red_flags:
            negative_parts.append(f"Company red flags: {', '.join(company_red_flags[:5])}")
            has_negative = True

        if has_negative:
            parts.extend(negative_parts)

        scout_additions = improvements.get("company_scout_additions", "")
        if scout_additions:
            parts.append(f"\nAdditional guidance: {scout_additions}")

        parts.append("\n--- END LEARNED PREFERENCES ---")

        return "\n".join(parts)

    def _build_job_search_context(self) -> str:
        """Build learned context for job search/discovery prompts."""
        parts = ["\n\n--- LEARNED PREFERENCES FROM USER FEEDBACK ---"]

        targeting = self.learned_preferences.get("improved_targeting", {})
        improvements = self.learned_preferences.get("prompt_improvements", {})
        negative = self.learned_preferences.get("negative_analysis", {})
        scoring = self.learned_preferences.get("scoring_adjustments", {})

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

        has_negative = False
        negative_parts = ["\n## NEGATIVE SIGNALS (deprioritize/penalize these):"]

        titles_to_avoid = targeting.get("titles_to_avoid", [])
        if titles_to_avoid:
            negative_parts.append(
                f"Avoid job titles containing: {', '.join(titles_to_avoid[:5])}"
            )
            has_negative = True

        red_flags = targeting.get("red_flag_keywords", [])
        if red_flags:
            negative_parts.append(
                f"Red flag keywords (lower score): {', '.join(red_flags[:8])}"
            )
            has_negative = True

        role_red_flags = negative.get("role_red_flags", [])
        if role_red_flags:
            negative_parts.append(
                f"Role characteristics to avoid: {', '.join(role_red_flags[:5])}"
            )
            has_negative = True

        if has_negative:
            parts.extend(negative_parts)

        exclusions = improvements.get("job_search_exclusions", "")
        if exclusions:
            parts.append(f"\nExclusion rules: {exclusions}")

        job_search_additions = improvements.get("job_search_additions", "")
        if job_search_additions:
            parts.append(f"\nAdditional guidance: {job_search_additions}")

        scoring_criteria = improvements.get("match_scoring_criteria", "")
        if scoring_criteria:
            parts.append(f"\nScoring criteria: {scoring_criteria}")

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

    def _build_job_scoring_context(self) -> str:
        """Build learned context specifically for job scoring prompts."""
        parts = ["\n\n--- LEARNED SCORING PREFERENCES ---"]
        parts.append("Apply these preferences when calculating match_score:")

        targeting = self.learned_preferences.get("improved_targeting", {})
        negative = self.learned_preferences.get("negative_analysis", {})
        scoring = self.learned_preferences.get("scoring_adjustments", {})

        primary_titles = targeting.get("primary_titles", [])
        if primary_titles:
            parts.append(
                f"\nBOOST SCORE (+15-25 points) for roles matching: {', '.join(primary_titles[:5])}"
            )

        must_have = targeting.get("must_have_keywords", [])
        if must_have:
            parts.append(
                f"BOOST SCORE (+10 points) if job contains: {', '.join(must_have[:6])}"
            )

        boost_factors = scoring.get("boost_factors", [])
        if boost_factors and isinstance(boost_factors, list):
            parts.append(f"Additional boost factors: {', '.join(boost_factors[:4])}")

        titles_to_avoid = targeting.get("titles_to_avoid", [])
        if titles_to_avoid:
            parts.append(
                f"\nPENALIZE SCORE (-20-30 points) for roles matching: {', '.join(titles_to_avoid[:5])}"
            )

        red_flags = targeting.get("red_flag_keywords", [])
        if red_flags:
            parts.append(
                f"PENALIZE SCORE (-15 points) if job contains: {', '.join(red_flags[:6])}"
            )

        role_red_flags = negative.get("role_red_flags", [])
        if role_red_flags:
            parts.append(
                f"PENALIZE SCORE (-10 points) for: {', '.join(role_red_flags[:4])}"
            )

        penalty_factors = scoring.get("penalty_factors", [])
        if penalty_factors and isinstance(penalty_factors, list):
            parts.append(f"Additional penalty factors: {', '.join(penalty_factors[:4])}")

        parts.append("\nApply these adjustments to arrive at the final match_score.")
        parts.append("--- END SCORING PREFERENCES ---")

        return "\n".join(parts)

    def _load_base_resume(self) -> str | None:
        """Load the base resume from markdown file.

        Returns:
            Resume text or None if file doesn't exist.
        """
        resume_path = self.input_dir / "base-resume.md"

        if not resume_path.exists():
            logger.warning("Resume not found at %s", resume_path)
            return None

        try:
            return resume_path.read_text()
        except Exception as e:
            logger.error("Error reading resume: %s", e)
            return None

    def _load_additional_context(self) -> str | None:
        """Load additional context from input/additional_context.md.

        Returns:
            Additional context text or None if file doesn't exist.
        """
        context_path = self.input_dir / "additional_context.md"
        if not context_path.exists():
            return None
        try:
            return context_path.read_text()
        except Exception:
            return None
