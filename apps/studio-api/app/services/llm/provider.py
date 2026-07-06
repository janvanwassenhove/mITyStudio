"""LlmProvider interface + MockLlmProvider + Anthropic adapter.

Providers receive a planning prompt (with the available-asset context) and
must return a JSON payload with a reply and a list of structured operations.
Providers never touch files or audio.
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod

from .settings import LlmSettings, get_api_key

log = logging.getLogger(__name__)


class LlmProviderError(Exception):
    pass


class LlmProvider(ABC):
    @abstractmethod
    def plan(self, system_prompt: str, user_message: str) -> dict:
        """Returns {"reply": str, "operations": [dict, ...]}."""

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Returns (ok, message)."""


class MockLlmProvider(LlmProvider):
    """Deterministic keyword-based planner. Keeps the whole studio usable
    without an API key and gives tests a stable target."""

    def plan(self, system_prompt: str, user_message: str) -> dict:
        from .mock_planner import plan_from_message
        return plan_from_message(system_prompt, user_message)

    def test_connection(self) -> tuple[bool, str]:
        return True, "mock provider is always available"


class AnthropicProvider(LlmProvider):
    def __init__(self, settings: LlmSettings) -> None:
        self.settings = settings

    def _client(self):
        try:
            import anthropic
        except ImportError as e:
            raise LlmProviderError(
                "the 'anthropic' package is not installed "
                "(pip install anthropic)") from e
        key = get_api_key()
        if not key:
            raise LlmProviderError(
                "no API key configured (Settings → LLM, or ANTHROPIC_API_KEY)")
        return anthropic.Anthropic(api_key=key)

    def plan(self, system_prompt: str, user_message: str) -> dict:
        client = self._client()
        try:
            resp = client.messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as e:
            raise LlmProviderError(f"LLM request failed: {e}") from e
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return _extract_json(text)

    def test_connection(self) -> tuple[bool, str]:
        try:
            client = self._client()
            client.messages.create(
                model=self.settings.model, max_tokens=16,
                messages=[{"role": "user", "content": "Reply with OK"}])
            return True, f"connected to Anthropic ({self.settings.model})"
        except LlmProviderError as e:
            return False, str(e)
        except Exception as e:
            return False, f"connection failed: {e}"


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from an LLM response."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start:end + 1]
    if candidate is None:
        raise LlmProviderError("LLM response contained no JSON object")
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise LlmProviderError(f"LLM returned invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise LlmProviderError("LLM JSON must be an object")
    data.setdefault("reply", "")
    data.setdefault("operations", [])
    if not isinstance(data["operations"], list):
        raise LlmProviderError("'operations' must be a list")
    return data


def get_provider(settings: LlmSettings) -> LlmProvider:
    if settings.provider == "anthropic":
        return AnthropicProvider(settings)
    return MockLlmProvider()
