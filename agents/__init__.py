"""Talent Scout agents and skills."""

# Base
from .base_agent import BaseAgent

# New Agents (3-agent architecture)
from .candidate_profiler import CandidateProfilerAgent
from .opportunity_scout import OpportunityScoutAgent
from .application_composer import ApplicationComposerAgent

# Re-export skills for convenience
from skills import (
    BaseSkill,
    SkillContext,
    SkillResult,
    CompanyResearcherSkill,
    JobPostingRetrieverSkill,
    JobDescriptionAnalyzerSkill,
    ResumeGeneratorSkill,
    CoverLetterGeneratorSkill,
)

__all__ = [
    # Agents
    "BaseAgent",
    "CandidateProfilerAgent",
    "OpportunityScoutAgent",
    "ApplicationComposerAgent",
    # Skills
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    "CompanyResearcherSkill",
    "JobPostingRetrieverSkill",
    "JobDescriptionAnalyzerSkill",
    "ResumeGeneratorSkill",
    "CoverLetterGeneratorSkill",
]
