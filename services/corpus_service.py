"""Corpus service - experience bullet corpus management.

Thin wrapper around CorpusBuilderSkill.
"""

import logging

from claude_client import ClaudeClient
from skills import CorpusBuilderSkill

from .base_service import BaseService
from .exceptions import GenerationFailedError
from .models import CorpusStats

logger = logging.getLogger(__name__)


class CorpusService(BaseService):
    """Service for managing the experience bullet corpus."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.corpus_skill = CorpusBuilderSkill(
            self.client, self.data_store, self.config
        )

    def build(self) -> dict:
        """Build the experience bullet corpus from existing resumes.

        Returns:
            Dict with build metadata (resumes_processed, bullets_count, etc.).

        Raises:
            GenerationFailedError: If corpus build fails.
        """
        result = self.corpus_skill.build_corpus()

        if not result.success:
            raise GenerationFailedError("Corpus build", result.error)

        return result.metadata

    def update(self) -> dict:
        """Update corpus with new bullets from recent resumes.

        Returns:
            Dict with update metadata.

        Raises:
            GenerationFailedError: If corpus update fails.
        """
        result = self.corpus_skill.update_corpus()

        if not result.success:
            raise GenerationFailedError("Corpus update", result.error)

        return result.metadata

    def get_stats(self) -> CorpusStats:
        """Get corpus statistics.

        Returns:
            CorpusStats model, or empty stats if no corpus exists.
        """
        corpus_data = self.data_store.get_corpus()

        if not corpus_data:
            return CorpusStats()

        experiences = corpus_data.get("experiences", {})
        total_bullets = sum(
            len(exp.get("bullets", []))
            for exp in experiences.values()
        )

        skills_index = corpus_data.get("skills_index", {})
        themes_index = corpus_data.get("themes_index", {})

        # Top skills
        sorted_skills = sorted(
            skills_index.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )[:10]
        top_skills = [
            {"skill": skill, "bullet_count": len(bullet_ids)}
            for skill, bullet_ids in sorted_skills
        ]

        # Top themes
        sorted_themes = sorted(
            themes_index.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )[:10]
        top_themes = [
            {"theme": theme, "bullet_count": len(bullet_ids)}
            for theme, bullet_ids in sorted_themes
        ]

        return CorpusStats(
            version=corpus_data.get("version"),
            generated_at=corpus_data.get("generated_at"),
            source_resumes=corpus_data.get("source_resumes", 0),
            experience_entries=len(experiences),
            total_bullets=total_bullets,
            skills_indexed=len(skills_index),
            themes_indexed=len(themes_index),
            top_skills=top_skills,
            top_themes=top_themes,
        )
