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


def classify_llm_error(message: str) -> str:
    """'rate_limit' | 'quota' | 'auth' | 'error' — the UI explains each."""
    m = message.lower()
    if "429" in m or "rate limit" in m or "rate_limit" in m:
        return "rate_limit"
    if "quota" in m or "insufficient" in m or "billing" in m or "credit" in m:
        return "quota"
    if "401" in m or "403" in m or "api key" in m or "auth" in m:
        return "auth"
    return "error"


class LlmProvider(ABC):
    # token usage of the most recent plan() call, for cost visibility
    last_usage: dict | None = None

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
        self.last_usage = {"model": "mock", "input_tokens": 0,
                           "output_tokens": 0}
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
        key = get_api_key("anthropic")
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
        usage = getattr(resp, "usage", None)
        self.last_usage = {
            "model": self.settings.model,
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        }
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


class OpenAIProvider(LlmProvider):
    """OpenAI — and, with a base_url, ANY OpenAI-compatible endpoint
    (OpenRouter, Groq, Mistral, DeepSeek, Ollama, LM Studio, …)."""

    def __init__(self, settings: LlmSettings, provider_key: str = "openai") -> None:
        self.settings = settings
        self.provider_key = provider_key   # "openai" | "custom"

    def _client(self):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise LlmProviderError(
                "the 'openai' package is not installed (pip install openai)") from e
        base_url = self.settings.base_url.strip() or None
        key = get_api_key(self.provider_key, base_url or "")
        if self.provider_key == "custom" and not base_url:
            raise LlmProviderError(
                "the custom provider needs a base URL "
                "(e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1)")
        if not key:
            if base_url:
                # local/keyless servers (e.g. Ollama) accept any token
                key = "not-needed"
            else:
                raise LlmProviderError(
                    "no API key configured (Settings → LLM, or OPENAI_API_KEY)")
        return OpenAI(api_key=key, base_url=base_url)

    def _model(self) -> str:
        model = self.settings.model.strip()
        if not model:
            raise LlmProviderError("no model configured for this provider")
        return model

    def _create(self, client, messages: list, max_tokens: int,
                want_json: bool):
        """chat.completions.create with parameter negotiation: newer OpenAI
        models want max_completion_tokens and reject custom temperature;
        older/compatible servers want max_tokens and may lack
        response_format. Try the strictest form first, degrade gracefully."""
        base = {"model": self._model(), "messages": messages}
        variants: list[dict] = []
        for tokens_kw in ("max_completion_tokens", "max_tokens"):
            for extra in ((
                {"response_format": {"type": "json_object"},
                 "temperature": self.settings.temperature},
                {"temperature": self.settings.temperature},
                {},
            ) if want_json else ({"temperature": self.settings.temperature}, {})):
                variants.append({tokens_kw: max_tokens, **extra})
        last: Exception | None = None
        for extra in variants:
            try:
                return client.chat.completions.create(**base, **extra)
            except Exception as e:
                msg = str(e).lower()
                last = e
                # only keep negotiating on parameter complaints; real errors
                # (auth, model not found, network) fail fast
                if not any(k in msg for k in ("max_tokens", "max_completion",
                                              "temperature", "response_format",
                                              "unsupported", "unexpected keyword")):
                    break
        raise LlmProviderError(f"LLM request failed: {last}") from last

    def plan(self, system_prompt: str, user_message: str) -> dict:
        client = self._client()
        resp = self._create(
            client,
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": user_message}],
            self.settings.max_tokens, want_json=True)
        usage = getattr(resp, "usage", None)
        self.last_usage = {
            "model": self.settings.model,
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        }
        text = resp.choices[0].message.content or ""
        return _extract_json(text)

    def test_connection(self) -> tuple[bool, str]:
        try:
            client = self._client()
            self._create(client,
                         [{"role": "user", "content": "Reply with OK"}],
                         16, want_json=False)
            where = self.settings.base_url.strip() or "api.openai.com"
            return True, f"connected to {where} ({self.settings.model})"
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
    if settings.provider == "openai":
        return OpenAIProvider(settings, "openai")
    if settings.provider == "custom":
        return OpenAIProvider(settings, "custom")
    return MockLlmProvider()
