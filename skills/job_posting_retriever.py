"""Job Posting Retriever Skill - fetches and parses job postings from URLs or markdown."""

import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

try:
    from firecrawl import Firecrawl as FirecrawlClient
    _FIRECRAWL_AVAILABLE = True
except ImportError:
    _FIRECRAWL_AVAILABLE = False

# Configure error logger to write to error.log in project root
_error_logger = logging.getLogger("talent_scout.job_retriever")
_error_logger.setLevel(logging.DEBUG)
if not _error_logger.handlers:
    _log_path = Path(__file__).resolve().parent.parent / "error.log"
    _file_handler = logging.FileHandler(_log_path)
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    _error_logger.addHandler(_file_handler)

# JS shell / bot-protection challenge signatures (case-insensitive substrings)
_CHALLENGE_SIGNATURES = [
    "just a moment",
    "checking your browser",
    "access denied",
    "cf-browser-verification",
    "pardon our interruption",
    "please enable javascript",
    "enable cookies",
    "ray id",
]


def _strip_html_to_text(html: str) -> str:
    """Strip scripts, styles, comments, and HTML tags to extract visible text."""
    text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_js_shell(html: str) -> bool:
    """Detect if HTML is a JS shell, bot challenge, or otherwise unusable.

    Returns True when content should be escalated to Firecrawl.
    """
    if not html:
        _error_logger.debug("JS shell detection: empty content")
        return True

    html_lower = html.lower()

    # Check for challenge/bot-protection signatures in raw HTML
    for sig in _CHALLENGE_SIGNATURES:
        if sig in html_lower:
            _error_logger.debug("JS shell detection: challenge signature '%s'", sig)
            return True

    visible = _strip_html_to_text(html)

    # Visible text too short to be a real job posting
    if len(visible) < 200:
        _error_logger.debug(
            "JS shell detection: visible text too short (%d chars)", len(visible)
        )
        return True

    # Text-to-HTML ratio too low (SPA shell with huge JS bundles)
    if len(html) > 5000 and len(visible) / len(html) < 0.02:
        _error_logger.debug(
            "JS shell detection: low text ratio (%.4f, html=%d, text=%d)",
            len(visible) / len(html),
            len(html),
            len(visible),
        )
        return True

    return False


from config_loader import (
    get_location_slug,
    classify_job_location,
    build_target_roles_text,
    build_location_type_rules,
)
from .base_skill import BaseSkill, SkillContext, SkillResult, _load_reference

JOB_URL_PARSE_PROMPT_TEMPLATE = _load_reference("job-url-parse-prompt.md")


@dataclass
class JobPostingResult:
    """Result of job posting retrieval."""

    job: dict
    """Parsed job dictionary with ID and metadata."""

    source_url: str | None
    """Source URL if imported from URL."""

    source_file: str | None
    """Source filename if imported from markdown."""


class JobPostingRetrieverSkill(BaseSkill):
    """Skill that fetches and parses job postings from URLs or markdown content."""

    def execute(
        self,
        context: SkillContext,
        url: str | None = None,
        content: str | None = None,
        filename: str | None = None,
    ) -> SkillResult:
        """Fetch and parse a job posting.

        Args:
            context: Execution context with config and learned preferences.
            url: URL to fetch job posting from.
            content: Markdown/text content to parse (alternative to URL).
            filename: Source filename when using content.

        Returns:
            SkillResult with JobPostingResult data.
        """
        if url:
            return self._import_from_url(url, context)
        elif content:
            return self._import_from_markdown(content, filename or "manual", context)
        else:
            return SkillResult.fail("Either url or content must be provided")

    def _import_from_url(self, url: str, context: SkillContext) -> SkillResult:
        """Import a job posting from a URL."""
        # Fetch the URL
        content = self._fetch_url_content(url)
        if not content:
            msg = f"Could not fetch job posting from URL: {url} (see error.log for details)"
            _error_logger.error("Job import failed at fetch stage for URL: %s", url)
            return SkillResult.fail(msg)

        # Parse with Claude
        job = self._parse_job_posting(url, content, context)
        if not job:
            msg = f"Could not parse job posting from URL: {url} (see error.log for details)"
            _error_logger.error(
                "Job import failed at parse stage for URL: %s — content length: %d, first 200 chars: %s",
                url,
                len(content),
                content[:200],
            )
            return SkillResult.fail(msg)

        # Add ID, URL, and source tracking
        company_name = job.get("company") or "unknown"
        company_slug = get_location_slug(company_name)
        job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        job["url"] = url
        job["source"] = "imported"
        job["imported_at"] = datetime.now(timezone.utc).isoformat()
        job["company"] = company_name

        result = JobPostingResult(
            job=job,
            source_url=url,
            source_file=None,
        )

        return SkillResult.ok(result)

    def _import_from_markdown(
        self, content: str, filename: str, context: SkillContext
    ) -> SkillResult:
        """Import a job posting from markdown content."""
        # Parse with Claude
        job = self._parse_job_posting(f"manual import from {filename}", content, context)
        if not job:
            return SkillResult.fail(f"Could not parse job from {filename}")

        # Add ID and source tracking
        company_name = job.get("company") or "unknown"
        company_slug = get_location_slug(company_name)
        job["id"] = f"JOB-{company_slug.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        job["url"] = None
        job["source"] = "imported"
        job["imported_at"] = datetime.now(timezone.utc).isoformat()
        job["source_file"] = filename
        job["company"] = company_name

        result = JobPostingResult(
            job=job,
            source_url=None,
            source_file=filename,
        )

        return SkillResult.ok(result)

    def _fetch_url_content(self, url: str) -> str | None:
        """Fetch content from a URL with Firecrawl fallback.

        Tier 1: httpx GET — fast, works for server-rendered pages.
        Tier 2: Firecrawl /scrape — handles JS SPAs and bot-protected sites.
        """
        httpx_html = None
        escalation_reason = None

        # Tier 1: httpx
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                if response.status_code == 200:
                    if not _is_js_shell(response.text):
                        return response.text
                    httpx_html = response.text
                    escalation_reason = "JS shell detected"
                else:
                    _error_logger.error(
                        "HTTP %d fetching %s — response: %s",
                        response.status_code,
                        url,
                        response.text[:500],
                    )
                    escalation_reason = f"HTTP {response.status_code}"
        except httpx.TimeoutException as e:
            _error_logger.error("Timeout fetching %s: %s", url, e)
            escalation_reason = "timeout"
        except httpx.ConnectError as e:
            _error_logger.error("Connection error fetching %s: %s", url, e)
            escalation_reason = "connection error"
        except Exception as e:
            _error_logger.error(
                "Unexpected error fetching %s: %s: %s", url, type(e).__name__, e
            )
            escalation_reason = f"{type(e).__name__}"

        # Tier 2: Firecrawl fallback
        _error_logger.info(
            "Escalating to Firecrawl for %s (reason: %s)", url, escalation_reason
        )
        firecrawl_md = self._fetch_with_firecrawl(url)
        if firecrawl_md:
            return firecrawl_md

        # Last resort: return httpx HTML if we got any (even a JS shell)
        if httpx_html:
            _error_logger.info(
                "Returning httpx HTML as last resort for %s (%d chars)",
                url,
                len(httpx_html),
            )
            return httpx_html

        return None

    def _fetch_with_firecrawl(self, url: str) -> str | None:
        """Fetch content via Firecrawl scrape API. Returns markdown or None."""
        if not _FIRECRAWL_AVAILABLE:
            _error_logger.info(
                "Firecrawl not available (firecrawl-py not installed). "
                "Install with: pip install talent-scout[firecrawl]"
            )
            return None

        api_key = os.environ.get("FIRECRAWL_API_KEY")
        if not api_key:
            _error_logger.info(
                "Firecrawl API key not set. "
                "Set FIRECRAWL_API_KEY env var to enable fallback scraping."
            )
            return None

        try:
            client = FirecrawlClient(api_key=api_key)
            result = client.scrape(url, formats=["markdown"])
            markdown = result.markdown if result else None

            if not markdown or len(markdown) < 100:
                _error_logger.warning(
                    "Firecrawl returned insufficient content for %s (length=%d)",
                    url,
                    len(markdown) if markdown else 0,
                )
                return None

            _error_logger.info(
                "Firecrawl successfully scraped %s (%d chars markdown)",
                url,
                len(markdown),
            )
            return markdown

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            error_lower = f"{error_type} {error_msg}".lower()

            if "429" in error_msg or "rate" in error_lower:
                _error_logger.warning(
                    "Firecrawl rate limited for %s: %s", url, e
                )
            elif "401" in error_msg or "403" in error_msg or "auth" in error_lower:
                _error_logger.warning(
                    "Firecrawl authentication failed for %s. Check FIRECRAWL_API_KEY.",
                    url,
                )
            else:
                _error_logger.warning(
                    "Firecrawl error for %s: %s: %s", url, error_type, e
                )
            return None

    def _parse_job_posting(
        self, source: str, content: str, context: SkillContext
    ) -> dict | None:
        """Parse job posting content with Claude."""
        # Truncate content if too long
        if len(content) > 50000:
            content = content[:50000] + "\n... [truncated]"

        # Build system prompt with learned preferences for scoring
        system_prompt = self._get_url_parse_prompt()
        if context.learned_context:
            system_prompt += context.learned_context

        try:
            job = self.client.complete_json(
                system=system_prompt,
                user=f"Parse this job posting from {source}:\n\n{content}",
                max_tokens=2048,
            )

            # Validate and correct location_type using classifier
            if job:
                job_location = job.get("location", "")
                job["location_type"] = classify_job_location(job_location, self.config)

            return job
        except ValueError as e:
            _error_logger.error(
                "Failed to parse Claude response for %s: %s", source, e
            )
            return None

    def _get_url_parse_prompt(self) -> str:
        """Build the URL parse system prompt with config-based locations."""
        return JOB_URL_PARSE_PROMPT_TEMPLATE.format(
            target_roles=build_target_roles_text(self.config),
            location_type_rules=build_location_type_rules(self.config),
        )
