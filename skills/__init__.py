"""Talent Scout skills - stateless tools for specific operations."""

from .base_skill import BaseSkill, SkillContext, SkillResult
from .company_researcher import CompanyResearcherSkill
from .job_posting_retriever import JobPostingRetrieverSkill
from .job_description_analyzer import JobDescriptionAnalyzerSkill, ROLE_ARCHETYPES
from .resume_generator import ResumeGeneratorSkill
from .cover_letter_generator import CoverLetterGeneratorSkill
from .corpus_builder import CorpusBuilderSkill
from .interview_prep import InterviewPrepSkill

__all__ = [
    # Base
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    # Skills
    "CompanyResearcherSkill",
    "JobPostingRetrieverSkill",
    "JobDescriptionAnalyzerSkill",
    "ROLE_ARCHETYPES",
    "ResumeGeneratorSkill",
    "CoverLetterGeneratorSkill",
    "CorpusBuilderSkill",
    "InterviewPrepSkill",
]
