"""Profile service - candidate profile management.

Extracted from agents/candidate_profiler.py.
"""

import hashlib
import logging
from datetime import datetime, timezone

from .base_service import BaseService
from .exceptions import ProfileNotFoundError, ResumeNotFoundError, GenerationFailedError
from .models import ProfileResponse

logger = logging.getLogger(__name__)

PROFILE_EXTRACTION_PROMPT = """You are an expert resume parser. Extract structured information from this resume.

Return your response as valid JSON matching this schema:
{
  "identity": {
    "name": "Full Name",
    "email": "email@example.com or null",
    "phone": "phone number or null",
    "linkedin": "LinkedIn URL or null",
    "location": "City, State or null"
  },
  "summary": "A structured 2-3 sentence summary of the candidate's professional profile",
  "experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "start_date": "Month Year or Year",
      "end_date": "Month Year, Year, or Present",
      "highlights": ["key accomplishment 1", "key accomplishment 2"],
      "skills_used": ["skill1", "skill2"]
    }
  ],
  "skills": {
    "technical": ["programming languages, frameworks, tools"],
    "leadership": ["leadership and management skills"],
    "domains": ["industry domains, areas of expertise"]
  },
  "education": [
    {
      "institution": "University Name",
      "degree": "Degree Type",
      "field": "Field of Study",
      "year": "Graduation Year or null"
    }
  ]
}

Extract information accurately from the resume. Do not invent or assume information not present."""


class ProfileService(BaseService):
    """Service for candidate profile management.

    Handles profile retrieval, refresh, and summary generation.
    """

    def get_profile(self) -> ProfileResponse:
        """Get the current candidate profile.

        Returns:
            ProfileResponse model.

        Raises:
            ProfileNotFoundError: If no profile exists.
        """
        profile = self.data_store.get_profile()
        if not profile:
            raise ProfileNotFoundError()

        return ProfileResponse(**profile)

    def refresh_profile(self) -> ProfileResponse:
        """Re-parse the base resume and update the profile.

        Returns:
            Updated ProfileResponse model.

        Raises:
            ResumeNotFoundError: If base resume cannot be loaded.
            GenerationFailedError: If Claude parsing fails.
        """
        resume_text = self._load_base_resume()
        if not resume_text:
            raise ResumeNotFoundError(str(self.input_dir / "base-resume.md"))

        resume_hash = hashlib.sha256(resume_text.encode()).hexdigest()

        # Extract structured profile from resume
        try:
            extracted = self.client.complete_json(
                system=PROFILE_EXTRACTION_PROMPT,
                user=f"Parse this resume and extract structured information:\n\n{resume_text}",
                max_tokens=4096,
            )
        except ValueError as e:
            raise GenerationFailedError("Profile extraction", str(e))

        # Load config preferences
        config_prefs = self.config.get("preferences", {})

        # Load learned preferences if available
        learned_prefs = self.data_store.get_learned_preferences()

        # Build complete profile
        profile = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_resume_hash": resume_hash,
            "identity": extracted.get("identity", {}),
            "summary": extracted.get("summary", ""),
            "experience": extracted.get("experience", []),
            "skills": extracted.get("skills", {}),
            "education": extracted.get("education", []),
            "preferences": {
                "target_roles": config_prefs.get("target_roles", []),
                "locations": config_prefs.get("locations", []),
                "include_remote": config_prefs.get("include_remote", True),
            },
            "learned_preferences": self._extract_learned_preferences(learned_prefs),
        }

        # Save profile
        self.data_store.save_profile(profile)
        logger.info("Profile updated successfully")

        return ProfileResponse(**profile)

    def get_profile_summary(self) -> str:
        """Get a text summary of the profile for prompt injection.

        Returns:
            Summary string or empty if no profile.
        """
        profile = self.data_store.get_profile()
        if not profile:
            return ""

        parts = []

        identity = profile.get("identity", {})
        name = identity.get("name")
        if name:
            parts.append(f"Candidate: {name}")

        summary = profile.get("summary", "")
        if summary:
            parts.append(f"Background: {summary}")

        experience = profile.get("experience", [])
        if experience:
            current = experience[0]
            parts.append(
                f"Current role: {current.get('title', '?')} at {current.get('company', '?')}"
            )

        skills = profile.get("skills", {})
        technical = skills.get("technical", [])
        if technical:
            parts.append(f"Key skills: {', '.join(technical[:6])}")

        prefs = profile.get("preferences", {})
        roles = prefs.get("target_roles", [])
        if roles:
            parts.append(f"Target roles: {', '.join(roles[:3])}")

        return "\n".join(parts)

    def _extract_learned_preferences(self, learned_prefs: dict | None) -> dict:
        """Extract relevant learned preferences for the profile."""
        if not learned_prefs:
            return {}

        targeting = learned_prefs.get("improved_targeting", {})
        scoring = learned_prefs.get("scoring_adjustments", {})

        return {
            "primary_titles": targeting.get("primary_titles", []),
            "titles_to_avoid": targeting.get("titles_to_avoid", []),
            "must_have_keywords": targeting.get("must_have_keywords", []),
            "red_flag_keywords": targeting.get("red_flag_keywords", []),
            "ideal_company_profile": targeting.get("ideal_company_profile", ""),
            "boost_factors": scoring.get("boost_factors", []),
            "penalty_factors": scoring.get("penalty_factors", []),
            "insights": learned_prefs.get("insights", ""),
        }
