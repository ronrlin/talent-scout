"""Talent Scout skills - stateless tools for specific operations."""

from .base_skill import BaseSkill, SkillContext, SkillResult
from .company_researcher import CompanyResearcherSkill
from .job_posting_retriever import JobPostingRetrieverSkill
from .job_description_analyzer import JobDescriptionAnalyzerSkill
from .resume_generator import ResumeGeneratorSkill
from .cover_letter_generator import CoverLetterGeneratorSkill

__all__ = [
    # Base
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    # Skills
    "CompanyResearcherSkill",
    "JobPostingRetrieverSkill",
    "JobDescriptionAnalyzerSkill",
    "ResumeGeneratorSkill",
    "CoverLetterGeneratorSkill",
]
