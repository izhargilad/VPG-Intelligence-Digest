"""Anthropic API client wrapper for VPG Intelligence Digest.

Provides a managed client with retry logic, error handling,
and structured JSON response parsing for signal analysis.
"""

import json
import logging
import time

import anthropic

from src.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    ANTHROPIC_TEMPERATURE,
)

logger = logging.getLogger(__name__)


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

        if not self.api_key:
            logger.warning("No Anthropic API key configured — AI analysis unavailable")
            self._client = None
        else:
            self._client = anthropic.Anthropic(api_key=self.api_key)

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
