"""Tests for JobPostingRetrieverSkill Firecrawl fallback."""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from skills.job_posting_retriever import (
    JobPostingRetrieverSkill,
    _is_js_shell,
    _strip_html_to_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REAL_JOB_HTML = """
<html><head><title>Engineering Manager - TestCo</title></head>
<body>
<h1>Engineering Manager</h1>
<p>TestCo is looking for an Engineering Manager to lead our platform team.
You will be responsible for hiring, mentoring, and growing a team of 8-12 engineers.
We need someone with 5+ years of engineering management experience and a strong
technical background in distributed systems. You'll work closely with product and
design to ship features that serve millions of users. Competitive salary and equity.</p>
<h2>Requirements</h2>
<ul>
<li>5+ years engineering management</li>
<li>Experience with Python, Go, or Java</li>
<li>Track record of building high-performing teams</li>
</ul>
</body></html>
"""

CLOUDFLARE_CHALLENGE = """
<html><head><title>Just a moment...</title></head>
<body>
<div id="cf-browser-verification">
<p>Checking your browser before accessing the site.</p>
</div>
</body></html>
"""

ACCESS_DENIED_HTML = """
<html><head><title>Access Denied</title></head>
<body><h1>Access Denied</h1><p>You don't have permission.</p></body></html>
"""

SPA_SHELL_HTML = (
    "<html><head>"
    + '<script src="/bundle.js">' + "x" * 10000 + "</script>"
    + "</head><body><div id='root'></div></body></html>"
)

SHORT_TEXT_HTML = """
<html><head><title>Loading</title></head>
<body><div id="app"></div></body></html>
"""

FIRECRAWL_MARKDOWN = """
# Engineering Manager - TestCo

TestCo is looking for an Engineering Manager to lead our platform team.
You will be responsible for hiring, mentoring, and growing a team of 8-12 engineers.
We need someone with 5+ years of engineering management experience.

## Requirements
- 5+ years engineering management
- Experience with Python, Go, or Java
- Track record of building high-performing teams
"""


@pytest.fixture
def skill(mock_claude_client, data_store, test_config):
    """Create a JobPostingRetrieverSkill instance."""
    return JobPostingRetrieverSkill(mock_claude_client, data_store, test_config)


# ---------------------------------------------------------------------------
# TestIsJsShell
# ---------------------------------------------------------------------------


class TestIsJsShell:
    def test_real_job_html_returns_false(self):
        assert _is_js_shell(REAL_JOB_HTML) is False

    def test_cloudflare_challenge_returns_true(self):
        assert _is_js_shell(CLOUDFLARE_CHALLENGE) is True

    def test_empty_string_returns_true(self):
        assert _is_js_shell("") is True

    def test_spa_shell_low_text_ratio_returns_true(self):
        assert _is_js_shell(SPA_SHELL_HTML) is True

    def test_short_visible_text_returns_true(self):
        assert _is_js_shell(SHORT_TEXT_HTML) is True

    def test_access_denied_returns_true(self):
        assert _is_js_shell(ACCESS_DENIED_HTML) is True


# ---------------------------------------------------------------------------
# TestFetchWithFirecrawl
# ---------------------------------------------------------------------------


class TestFetchWithFirecrawl:
    def test_success_returns_markdown(self, skill, monkeypatch):
        monkeypatch.setattr(
            "skills.job_posting_retriever._FIRECRAWL_AVAILABLE", True
        )
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")

        mock_doc = MagicMock()
        mock_doc.markdown = FIRECRAWL_MARKDOWN

        mock_client_instance = MagicMock()
        mock_client_instance.scrape.return_value = mock_doc

        with patch(
            "skills.job_posting_retriever.FirecrawlClient",
            return_value=mock_client_instance,
        ):
            result = skill._fetch_with_firecrawl("https://example.com/job")

        assert result == FIRECRAWL_MARKDOWN
        mock_client_instance.scrape.assert_called_once_with(
            "https://example.com/job", formats=["markdown"]
        )

    def test_not_installed_returns_none(self, skill, monkeypatch):
        monkeypatch.setattr(
            "skills.job_posting_retriever._FIRECRAWL_AVAILABLE", False
        )
        result = skill._fetch_with_firecrawl("https://example.com/job")
        assert result is None

    def test_no_api_key_returns_none(self, skill, monkeypatch):
        monkeypatch.setattr(
            "skills.job_posting_retriever._FIRECRAWL_AVAILABLE", True
        )
        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        result = skill._fetch_with_firecrawl("https://example.com/job")
        assert result is None

    def test_rate_limit_returns_none(self, skill, monkeypatch):
        monkeypatch.setattr(
            "skills.job_posting_retriever._FIRECRAWL_AVAILABLE", True
        )
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")

        mock_client_instance = MagicMock()
        mock_client_instance.scrape.side_effect = Exception(
            "429 Too Many Requests"
        )

        with patch(
            "skills.job_posting_retriever.FirecrawlClient",
            return_value=mock_client_instance,
        ):
            result = skill._fetch_with_firecrawl("https://example.com/job")

        assert result is None

    def test_auth_error_returns_none(self, skill, monkeypatch):
        monkeypatch.setattr(
            "skills.job_posting_retriever._FIRECRAWL_AVAILABLE", True
        )
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-bad-key")

        mock_client_instance = MagicMock()
        mock_client_instance.scrape.side_effect = Exception(
            "401 Unauthorized"
        )

        with patch(
            "skills.job_posting_retriever.FirecrawlClient",
            return_value=mock_client_instance,
        ):
            result = skill._fetch_with_firecrawl("https://example.com/job")

        assert result is None

    def test_empty_response_returns_none(self, skill, monkeypatch):
        monkeypatch.setattr(
            "skills.job_posting_retriever._FIRECRAWL_AVAILABLE", True
        )
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")

        mock_doc = MagicMock()
        mock_doc.markdown = "short"

        mock_client_instance = MagicMock()
        mock_client_instance.scrape.return_value = mock_doc

        with patch(
            "skills.job_posting_retriever.FirecrawlClient",
            return_value=mock_client_instance,
        ):
            result = skill._fetch_with_firecrawl("https://example.com/job")

        assert result is None


# ---------------------------------------------------------------------------
# TestFetchUrlContent
# ---------------------------------------------------------------------------


class TestFetchUrlContent:
    def test_httpx_success_real_content_no_firecrawl(self, skill):
        """httpx returns real HTML — should return it without calling Firecrawl."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = REAL_JOB_HTML

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch.object(skill, "_fetch_with_firecrawl") as mock_fc:
                result = skill._fetch_url_content("https://example.com/job")

            mock_fc.assert_not_called()

        assert result == REAL_JOB_HTML

    def test_httpx_js_shell_calls_firecrawl(self, skill):
        """httpx returns JS shell — should escalate to Firecrawl."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = CLOUDFLARE_CHALLENGE

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch.object(
                skill, "_fetch_with_firecrawl", return_value=FIRECRAWL_MARKDOWN
            ) as mock_fc:
                result = skill._fetch_url_content("https://workday.com/job")

            mock_fc.assert_called_once_with("https://workday.com/job")

        assert result == FIRECRAWL_MARKDOWN

    def test_httpx_timeout_calls_firecrawl(self, skill):
        """httpx times out — should escalate to Firecrawl."""
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch.object(
                skill, "_fetch_with_firecrawl", return_value=FIRECRAWL_MARKDOWN
            ) as mock_fc:
                result = skill._fetch_url_content("https://slow-site.com/job")

            mock_fc.assert_called_once_with("https://slow-site.com/job")

        assert result == FIRECRAWL_MARKDOWN

    def test_httpx_403_calls_firecrawl(self, skill):
        """httpx gets 403 — should escalate to Firecrawl."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch.object(
                skill, "_fetch_with_firecrawl", return_value=FIRECRAWL_MARKDOWN
            ) as mock_fc:
                result = skill._fetch_url_content("https://protected.com/job")

            mock_fc.assert_called_once_with("https://protected.com/job")

        assert result == FIRECRAWL_MARKDOWN

    def test_both_fail_returns_none(self, skill):
        """Both httpx and Firecrawl fail — returns None."""
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch.object(
                skill, "_fetch_with_firecrawl", return_value=None
            ):
                result = skill._fetch_url_content("https://down.com/job")

        assert result is None

    def test_firecrawl_unavailable_returns_js_shell_html(self, skill):
        """Firecrawl unavailable, httpx got JS shell — returns HTML as last resort."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = CLOUDFLARE_CHALLENGE

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch.object(
                skill, "_fetch_with_firecrawl", return_value=None
            ):
                result = skill._fetch_url_content("https://spa-site.com/job")

        assert result == CLOUDFLARE_CHALLENGE
