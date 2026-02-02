"""Claude API client wrapper with retry logic and JSON parsing."""

import json
import time
from typing import Any

from anthropic import Anthropic, APIError, RateLimitError, APIConnectionError
from rich.console import Console

from config_loader import get_anthropic_api_key

console = Console()

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClaudeClient:
    """Wrapper for Claude API with retry logic, JSON parsing, and token tracking."""

    def __init__(self, model: str | None = None):
        """Initialize the Claude client.

        Args:
            model: Optional model override. Defaults to DEFAULT_MODEL.
        """
        self.client = Anthropic(api_key=get_anthropic_api_key())
        self.model = model or DEFAULT_MODEL
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> str:
        """Make a Claude API call with retry logic.

        Args:
            system: System prompt
            user: User message content
            max_tokens: Maximum tokens in response
            retry_count: Number of retries on transient failures
            retry_delay: Initial delay between retries (doubles on each retry)

        Returns:
            The text content of Claude's response

        Raises:
            APIError: If all retries fail
        """
        last_error = None
        delay = retry_delay

        for attempt in range(retry_count):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )

                # Track token usage
                self.total_input_tokens += response.usage.input_tokens
                self.total_output_tokens += response.usage.output_tokens

                return response.content[0].text

            except RateLimitError as e:
                last_error = e
                if attempt < retry_count - 1:
                    console.print(f"[yellow]Rate limited, waiting {delay}s...[/yellow]")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff

            except APIConnectionError as e:
                last_error = e
                if attempt < retry_count - 1:
                    console.print(f"[yellow]Connection error, retrying in {delay}s...[/yellow]")
                    time.sleep(delay)
                    delay *= 2

            except APIError as e:
                # Don't retry on client errors (4xx except rate limit)
                if e.status_code and 400 <= e.status_code < 500 and e.status_code != 429:
                    raise
                last_error = e
                if attempt < retry_count - 1:
                    console.print(f"[yellow]API error, retrying in {delay}s...[/yellow]")
                    time.sleep(delay)
                    delay *= 2

        # All retries exhausted
        raise last_error

    def complete_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        **kwargs,
    ) -> dict[str, Any]:
        """Make a Claude API call and parse JSON from the response.

        Args:
            system: System prompt
            user: User message content
            max_tokens: Maximum tokens in response
            **kwargs: Additional arguments passed to complete()

        Returns:
            Parsed JSON as a dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        response_text = self.complete(system, user, max_tokens, **kwargs)
        return self.parse_json_response(response_text)

    @staticmethod
    def parse_json_response(text: str) -> dict[str, Any]:
        """Extract and parse JSON from Claude's response.

        Handles responses wrapped in markdown code blocks.

        Args:
            text: Raw response text from Claude

        Returns:
            Parsed JSON as a dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        try:
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}") from e

    def get_token_usage(self) -> dict[str, int]:
        """Get cumulative token usage for this client instance.

        Returns:
            Dictionary with input_tokens, output_tokens, and total_tokens
        """
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
        }

    def reset_token_usage(self) -> None:
        """Reset token usage counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
