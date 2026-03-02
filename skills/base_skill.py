"""Base skill class and common data structures for stateless skills."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_client import ClaudeClient
from data_store import DataStore

_REFERENCES_DIR = Path(__file__).resolve().parent.parent / "openclaw" / "shared" / "references"


def _load_reference(filename: str) -> str:
    """Load a prompt/reference file from shared references directory."""
    return (_REFERENCES_DIR / filename).read_text().strip()


def _load_role_archetypes() -> dict[str, str]:
    """Load role archetypes from reference file into {key: description} dict."""
    text = _load_reference("role-archetypes.md")
    archetypes = {}
    for line in text.splitlines():
        # Parse table rows: | `key` | Description |
        if line.startswith("| `"):
            parts = line.split("|")
            key = parts[1].strip().strip("`")
            desc = parts[2].strip()
            archetypes[key] = desc
    return archetypes


def _load_role_lens_guidance() -> dict[str, dict[str, str]]:
    """Load role-lens guidance from reference file into nested dict.

    Returns:
        {"engineering": {"resume": "...", "cover_letter": "..."}, ...}
    """
    text = _load_reference("role-lens-guidance.md")
    guidance: dict[str, dict[str, str]] = {}
    current_role = None
    current_doc_type = None
    current_lines: list[str] = []

    def _flush():
        if current_role and current_doc_type and current_lines:
            guidance.setdefault(current_role, {})[current_doc_type] = "\n".join(current_lines).strip()

    for line in text.splitlines():
        if line.startswith("## ") and not line.startswith("###"):
            _flush()
            current_role = line[3:].strip().lower()
            current_doc_type = None
            current_lines = []
        elif line.startswith("### "):
            _flush()
            raw = line[4:].strip().lower()
            current_doc_type = "cover_letter" if raw == "cover letter" else raw
            current_lines = []
        elif current_doc_type is not None:
            current_lines.append(line)

    _flush()
    return guidance


@dataclass
class SkillContext:
    """Context passed to skill execution.

    Skills are stateless - they receive all needed context through this object.
    """

    config: dict
    """Application configuration."""

    learned_context: str | None = None
    """Pre-built learned preferences context string for prompt injection."""

    candidate_profile: dict | None = None
    """Candidate profile data if available."""

    extra: dict = field(default_factory=dict)
    """Additional context specific to the skill."""


@dataclass
class SkillResult:
    """Result returned from skill execution."""

    success: bool
    """Whether the skill executed successfully."""

    data: Any = None
    """The primary result data (type varies by skill)."""

    error: str | None = None
    """Error message if success is False."""

    metadata: dict = field(default_factory=dict)
    """Additional metadata about the execution."""

    @classmethod
    def ok(cls, data: Any, **metadata) -> "SkillResult":
        """Create a successful result."""
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata) -> "SkillResult":
        """Create a failed result."""
        return cls(success=False, error=error, metadata=metadata)


class BaseSkill:
    """Base class for all skills.

    Skills are stateless tools that:
    - Receive context and inputs
    - Perform a focused operation (often involving Claude API)
    - Return structured results
    - Use DataStore for persistence only when needed

    Skills should NOT:
    - Maintain state between calls
    - Make decisions about workflow
    - Print to console (that's the agent's job)
    """

    def __init__(self, client: ClaudeClient, data_store: DataStore, config: dict):
        """Initialize the skill.

        Args:
            client: ClaudeClient instance for API calls.
            data_store: DataStore instance for data persistence.
            config: Application configuration dictionary.
        """
        self.client = client
        self.data_store = data_store
        self.config = config

    def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        """Execute the skill.

        Args:
            context: Execution context with config and learned preferences.
            **kwargs: Skill-specific arguments.

        Returns:
            SkillResult with success/failure and data.
        """
        raise NotImplementedError("Subclasses must implement execute()")
