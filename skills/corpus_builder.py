"""Corpus Builder Skill - extracts and manages experience bullet corpus from resumes."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from .base_skill import BaseSkill, SkillContext, SkillResult


CORPUS_EXTRACTION_PROMPT = """You are analyzing resume bullets to build a skills corpus.

For each bullet, extract:
1. skills_demonstrated: List of specific skills this bullet proves (e.g., "Python", "team leadership", "ML systems", "data engineering")
2. themes: Categories like "customer-facing", "data engineering", "team management", "analytics", "production systems", "autonomous systems"
3. role_lens: Best fit - "engineering", "product", "program", or "solutions"

Return a JSON array where each element has:
{
  "bullet_index": <index from input>,
  "skills_demonstrated": ["skill1", "skill2", ...],
  "themes": ["theme1", "theme2", ...],
  "role_lens": "engineering|product|program|solutions"
}

Be specific with skills - extract actual technologies, methodologies, and competencies mentioned or implied.
For themes, use broad categories that help match bullets to job types."""


@dataclass
class BulletEntry:
    """A single experience bullet in the corpus."""

    id: str
    text: str
    role_lens: str
    skills_demonstrated: list[str]
    themes: list[str]
    source_jobs: list[str] = field(default_factory=list)
    usage_count: int = 0


@dataclass
class ExperienceEntry:
    """An experience entry (company/role) in the corpus."""

    company: str
    title: str
    dates: str
    bullets: list[BulletEntry]


@dataclass
class Corpus:
    """The full skills corpus."""

    version: str
    generated_at: str
    source_resumes: int
    experiences: dict[str, ExperienceEntry]
    skills_index: dict[str, list[str]]
    themes_index: dict[str, list[str]]


class CorpusBuilderSkill(BaseSkill):
    """Skill that builds and manages the experience bullet corpus."""

    SIMILARITY_THRESHOLD = 0.85
    RESUMES_DIR = Path(__file__).parent.parent / "output" / "resumes"

    def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        """Build the corpus from existing resumes.

        Args:
            context: Execution context.

        Returns:
            SkillResult with corpus statistics.
        """
        return self.build_corpus()

    def build_corpus(self) -> SkillResult:
        """Build the complete corpus from all resumes.

        Returns:
            SkillResult with corpus data and statistics.
        """
        # Scan for resume files
        resume_files = list(self.RESUMES_DIR.glob("*.md"))
        if not resume_files:
            return SkillResult.fail("No resume files found in output/resumes/")

        # Extract experiences from all resumes
        all_experiences: dict[str, ExperienceEntry] = {}
        resume_count = 0

        for resume_file in resume_files:
            try:
                experiences = self._parse_resume(resume_file)
                job_id = self._extract_job_id(resume_file.stem)

                for exp_key, exp in experiences.items():
                    if exp_key in all_experiences:
                        # Merge bullets from this resume
                        self._merge_experience(all_experiences[exp_key], exp, job_id)
                    else:
                        # Add source job to all bullets
                        for bullet in exp.bullets:
                            if job_id:
                                bullet.source_jobs.append(job_id)
                        all_experiences[exp_key] = exp

                resume_count += 1
            except Exception as e:
                # Continue processing other resumes
                continue

        if not all_experiences:
            return SkillResult.fail("No experiences extracted from resumes")

        # Deduplicate bullets within each experience
        for exp_key, exp in all_experiences.items():
            exp.bullets = self._deduplicate_bullets(exp.bullets)

        # Enrich bullets with skills and themes using Claude
        all_experiences = self._enrich_bullets(all_experiences)

        # Build indexes
        skills_index, themes_index = self._build_indexes(all_experiences)

        # Create corpus
        corpus_data = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_resumes": resume_count,
            "experiences": {
                key: self._experience_to_dict(exp)
                for key, exp in all_experiences.items()
            },
            "skills_index": skills_index,
            "themes_index": themes_index,
        }

        # Save corpus
        self.data_store.save_corpus(corpus_data)

        total_bullets = sum(len(exp.bullets) for exp in all_experiences.values())

        return SkillResult.ok(
            corpus_data,
            resumes_processed=resume_count,
            experiences_count=len(all_experiences),
            bullets_count=total_bullets,
            skills_indexed=len(skills_index),
            themes_indexed=len(themes_index),
        )

    def update_corpus(self) -> SkillResult:
        """Update corpus with new bullets from recent resumes.

        Compares current resumes to existing corpus and adds new bullet formulations.

        Returns:
            SkillResult with update statistics.
        """
        existing_corpus = self.data_store.get_corpus()
        if not existing_corpus:
            # No existing corpus, build fresh
            return self.build_corpus()

        # For now, rebuild completely - incremental updates can be added later
        return self.build_corpus()

    def _parse_resume(self, resume_path: Path) -> dict[str, ExperienceEntry]:
        """Parse a resume markdown file and extract experiences.

        Args:
            resume_path: Path to the resume markdown file.

        Returns:
            Dictionary mapping experience keys to ExperienceEntry objects.
        """
        content = resume_path.read_text()
        experiences = {}

        # Find Professional Experience section
        exp_match = re.search(
            r"##\s*(Professional\s+)?Experience\s*\n(.*?)(?=\n##\s|$)",
            content,
            re.IGNORECASE | re.DOTALL,
        )

        if not exp_match:
            return experiences

        exp_section = exp_match.group(2)

        # Format A: ### Company, Location — Title with *Dates* on next line
        # Example:
        # ### Tesla Inc, Palo Alto, CA — Engineering Manager, Energy Service Engineering
        # *September 2024 - Present*
        format_a_pattern = re.compile(
            r"###\s*([^,\n]+)(?:,\s*[^—\n]+)?\s*—\s*([^\n]+)\n"  # ### Company, Location — Title
            r"\*([^*]+)\*\s*\n"  # *Dates*
            r"((?:\s*[-•]\s*[^\n]+\n?)+)",  # Bullets
            re.MULTILINE,
        )

        # Format B: **Company**, Location with *Title* | Dates on next line
        # Example:
        # **Tesla Inc**, Palo Alto, CA
        # *Engineering Manager, Energy Service Engineering* | September 2024 - Present
        format_b_pattern = re.compile(
            r"\*\*([^*]+)\*\*[,\s]*[^\n]*?\n"  # **Company**, Location
            r"\*([^*]+)\*\s*\|\s*([^\n]+)\n"  # *Title* | Dates
            r"((?:\s*[-•]\s*[^\n]+\n?)+)",  # Bullets
            re.MULTILINE,
        )

        # Try Format A first
        for match in format_a_pattern.finditer(exp_section):
            company = match.group(1).strip()
            title = match.group(2).strip()
            dates = match.group(3).strip()
            bullets_text = match.group(4)

            bullets = self._extract_bullets(company, bullets_text)
            if bullets:
                exp_key = self._generate_experience_key(company, title)
                if exp_key not in experiences:
                    experiences[exp_key] = ExperienceEntry(
                        company=company,
                        title=title,
                        dates=dates,
                        bullets=bullets,
                    )

        # Try Format B
        for match in format_b_pattern.finditer(exp_section):
            company = match.group(1).strip()
            title = match.group(2).strip()
            dates = match.group(3).strip()
            bullets_text = match.group(4)

            bullets = self._extract_bullets(company, bullets_text)
            if bullets:
                exp_key = self._generate_experience_key(company, title)
                if exp_key not in experiences:
                    experiences[exp_key] = ExperienceEntry(
                        company=company,
                        title=title,
                        dates=dates,
                        bullets=bullets,
                    )

        return experiences

    def _extract_bullets(self, company: str, bullets_text: str) -> list[BulletEntry]:
        """Extract bullet entries from text.

        Args:
            company: Company name for generating bullet IDs.
            bullets_text: Raw text containing bullets.

        Returns:
            List of BulletEntry objects.
        """
        bullets = []
        bullet_lines = re.findall(r"[-•]\s*(.+)", bullets_text)

        for i, bullet_text in enumerate(bullet_lines):
            bullet_text = bullet_text.strip()
            if bullet_text:
                bullet_id = self._generate_bullet_id(company, i)
                bullets.append(
                    BulletEntry(
                        id=bullet_id,
                        text=bullet_text,
                        role_lens="engineering",  # Default, will be enriched
                        skills_demonstrated=[],
                        themes=[],
                    )
                )

        return bullets

    def _merge_experience(
        self, existing: ExperienceEntry, new: ExperienceEntry, job_id: str | None
    ) -> None:
        """Merge bullets from a new experience into an existing one.

        Args:
            existing: The existing experience entry.
            new: The new experience entry with bullets to merge.
            job_id: The source job ID for tracking.
        """
        existing_texts = {b.text for b in existing.bullets}

        for bullet in new.bullets:
            # Check if this bullet is already present (exact match)
            if bullet.text not in existing_texts:
                if job_id:
                    bullet.source_jobs.append(job_id)
                existing.bullets.append(bullet)
            else:
                # Update source_jobs for existing bullet
                for existing_bullet in existing.bullets:
                    if existing_bullet.text == bullet.text:
                        if job_id and job_id not in existing_bullet.source_jobs:
                            existing_bullet.source_jobs.append(job_id)
                            existing_bullet.usage_count += 1
                        break

    def _deduplicate_bullets(self, bullets: list[BulletEntry]) -> list[BulletEntry]:
        """Deduplicate similar bullets using fuzzy matching.

        Args:
            bullets: List of bullet entries to deduplicate.

        Returns:
            Deduplicated list of bullets.
        """
        if not bullets:
            return bullets

        unique_bullets = []

        for bullet in bullets:
            is_duplicate = False

            for unique in unique_bullets:
                similarity = SequenceMatcher(
                    None, bullet.text.lower(), unique.text.lower()
                ).ratio()

                if similarity >= self.SIMILARITY_THRESHOLD:
                    # Merge source jobs and increment usage
                    unique.source_jobs.extend(
                        job
                        for job in bullet.source_jobs
                        if job not in unique.source_jobs
                    )
                    unique.usage_count += bullet.usage_count + 1
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_bullets.append(bullet)

        return unique_bullets

    def _enrich_bullets(
        self, experiences: dict[str, ExperienceEntry]
    ) -> dict[str, ExperienceEntry]:
        """Enrich bullets with skills and themes using Claude.

        Args:
            experiences: Dictionary of experience entries.

        Returns:
            Enriched experience entries.
        """
        # Collect all bullets for batch processing
        all_bullets = []
        bullet_refs = []  # (exp_key, bullet_index)

        for exp_key, exp in experiences.items():
            for i, bullet in enumerate(exp.bullets):
                all_bullets.append(
                    {"index": len(all_bullets), "text": bullet.text, "title": exp.title}
                )
                bullet_refs.append((exp_key, i))

        if not all_bullets:
            return experiences

        # Process in batches to avoid context limits
        batch_size = 30
        for batch_start in range(0, len(all_bullets), batch_size):
            batch = all_bullets[batch_start : batch_start + batch_size]

            try:
                batch_input = json.dumps(batch, indent=2)
                result = self.client.complete_json(
                    system=CORPUS_EXTRACTION_PROMPT,
                    user=f"Analyze these resume bullets and extract skills, themes, and role lens:\n\n{batch_input}",
                    max_tokens=4000,
                )

                # Handle both array and object responses
                if isinstance(result, dict) and "bullets" in result:
                    result = result["bullets"]

                if isinstance(result, list):
                    for item in result:
                        idx = item.get("bullet_index")
                        if idx is not None and batch_start <= idx < batch_start + len(
                            batch
                        ):
                            global_idx = batch_start + (idx - batch_start)
                            if global_idx < len(bullet_refs):
                                exp_key, bullet_idx = bullet_refs[global_idx]
                                bullet = experiences[exp_key].bullets[bullet_idx]
                                bullet.skills_demonstrated = item.get(
                                    "skills_demonstrated", []
                                )
                                bullet.themes = item.get("themes", [])
                                bullet.role_lens = item.get("role_lens", "engineering")
            except Exception:
                # Continue with unenriched bullets if Claude fails
                continue

        return experiences

    def _build_indexes(
        self, experiences: dict[str, ExperienceEntry]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Build skill and theme indexes.

        Args:
            experiences: Dictionary of experience entries.

        Returns:
            Tuple of (skills_index, themes_index).
        """
        skills_index: dict[str, list[str]] = {}
        themes_index: dict[str, list[str]] = {}

        for exp in experiences.values():
            for bullet in exp.bullets:
                # Index by skills
                for skill in bullet.skills_demonstrated:
                    skill_lower = skill.lower()
                    if skill_lower not in skills_index:
                        skills_index[skill_lower] = []
                    if bullet.id not in skills_index[skill_lower]:
                        skills_index[skill_lower].append(bullet.id)

                # Index by themes
                for theme in bullet.themes:
                    theme_lower = theme.lower()
                    if theme_lower not in themes_index:
                        themes_index[theme_lower] = []
                    if bullet.id not in themes_index[theme_lower]:
                        themes_index[theme_lower].append(bullet.id)

        return skills_index, themes_index

    def _generate_experience_key(self, company: str, title: str) -> str:
        """Generate a unique key for an experience entry.

        Args:
            company: Company name.
            title: Job title.

        Returns:
            Slugified key.
        """
        slug = f"{company}-{title}".lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug

    def _generate_bullet_id(self, company: str, index: int) -> str:
        """Generate a unique ID for a bullet.

        Args:
            company: Company name.
            index: Bullet index within the experience.

        Returns:
            Bullet ID string.
        """
        company_slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
        return f"{company_slug}-{index:03d}"

    def _extract_job_id(self, filename: str) -> str | None:
        """Extract job ID from resume filename if possible.

        Args:
            filename: Resume filename without extension.

        Returns:
            Job ID or None if not extractable.
        """
        # Filenames are like "Ron Lin Resume - Company - Title"
        # We don't have job IDs in filenames, so return None
        # The corpus will track source resumes by filename instead
        return filename

    def _experience_to_dict(self, exp: ExperienceEntry) -> dict:
        """Convert an ExperienceEntry to a dictionary.

        Args:
            exp: ExperienceEntry to convert.

        Returns:
            Dictionary representation.
        """
        return {
            "company": exp.company,
            "title": exp.title,
            "dates": exp.dates,
            "bullets": [
                {
                    "id": b.id,
                    "text": b.text,
                    "role_lens": b.role_lens,
                    "skills_demonstrated": b.skills_demonstrated,
                    "themes": b.themes,
                    "source_jobs": b.source_jobs,
                    "usage_count": b.usage_count,
                }
                for b in exp.bullets
            ],
        }
