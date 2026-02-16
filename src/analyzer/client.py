"""Anthropic API client wrapper for VPG Intelligence Digest.

Provides a managed client with retry logic, error handling,
and structured JSON response parsing for signal analysis.
"""

import json
import logging
import os
import time

import anthropic

from src.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    ANTHROPIC_TEMPERATURE,
)

logger = logging.getLogger(__name__)


def _read_auth_token() -> str | None:
    """Read a Bearer auth token from CLAUDE_SESSION_INGRESS_TOKEN_FILE if available."""
    token_file = os.getenv("CLAUDE_SESSION_INGRESS_TOKEN_FILE", "")
    if not token_file:
        return None
    try:
        with open(token_file) as f:
            return f.read().strip() or None
    except OSError:
        return None


class AnalysisClient:
    """Wrapper around the Anthropic API for signal analysis."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = model or ANTHROPIC_MODEL
        self.temperature = temperature if temperature is not None else ANTHROPIC_TEMPERATURE
        self.max_tokens = max_tokens or ANTHROPIC_MAX_TOKENS

        self._client = None
        if self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        else:
            # Fall back to Bearer auth token (e.g. managed environments)
            auth_token = _read_auth_token()
            if auth_token:
                self._client = anthropic.Anthropic(auth_token=auth_token)
            else:
                logger.warning("No Anthropic API key configured — AI analysis unavailable")

    @property
    def available(self) -> bool:
        """Check if the API client is configured and ready."""
        return self._client is not None

    def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
    ) -> dict | None:
        """Send a prompt to the Anthropic API and parse JSON response.

        Args:
            system_prompt: System-level context for the model.
            user_prompt: The signal analysis request.
            max_retries: Number of retry attempts on failure.

        Returns:
            Parsed JSON dict from the model response, or None on failure.
        """
        if not self.available:
            logger.error("Anthropic API client not configured")
            return None

        for attempt in range(max_retries):
            try:
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                text = response.content[0].text
                return self._parse_json_response(text)

            except anthropic.RateLimitError as e:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Rate limited (attempt %d/%d), waiting %ds: %s",
                    attempt + 1, max_retries, wait, e,
                )
                time.sleep(wait)

            except anthropic.APIError as e:
                wait = 2 ** (attempt + 1)
                logger.error(
                    "API error (attempt %d/%d), waiting %ds: %s",
                    attempt + 1, max_retries, wait, e,
                )
                if attempt < max_retries - 1:
                    time.sleep(wait)

            except Exception as e:
                logger.error("Unexpected error during analysis: %s", e, exc_info=True)
                return None

        logger.error("All %d retry attempts exhausted", max_retries)
        return None

    @staticmethod
    def _parse_json_response(text: str) -> dict | None:
        """Extract and parse JSON from the model response text.

        Handles responses that may include markdown code fences.
        """
        cleaned = text.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json) and last line (```)
            start = 1
            end = len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip() == "```":
                    end = i
                    break
            cleaned = "\n".join(lines[start:end]).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s\nText: %s", e, cleaned[:500])
            return None
