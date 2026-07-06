"""LLM settings. Non-secret settings live in SQLite; API keys live in
apps/studio-api/local_settings.json (git-ignored) — one key per provider —
or in environment variables. Keys are never returned to clients and never
committed.

Providers:
- mock       deterministic keyword planner, no key needed
- anthropic  Claude models (key: settings or ANTHROPIC_API_KEY)
- openai     OpenAI models (key: settings or OPENAI_API_KEY)
- custom     any OpenAI-compatible endpoint via base_url — OpenRouter, Groq,
             Mistral, DeepSeek, Ollama, LM Studio… (key optional for local
             servers; env fallback MITY_LLM_API_KEY)
"""
from __future__ import annotations

import json
import os

from pydantic import BaseModel, Field

from ...config import get_config
from ...db import get_db

PROVIDERS = ("mock", "anthropic", "openai", "custom")

_ENV_KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "custom": ("MITY_LLM_API_KEY",),
}

_DEFAULT_MODELS = {
    "mock": "mock",
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5.2",
    "custom": "",
}


class LlmSettings(BaseModel):
    provider: str = "mock"
    model: str = "claude-sonnet-5"
    base_url: str = ""           # used by the custom provider (and optionally openai)
    api_key_reference: str = "local_settings"   # where keys are looked up
    temperature: float = Field(default=0.4, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=256, le=64000)


def default_model(provider: str) -> str:
    return _DEFAULT_MODELS.get(provider, "")


def load_settings() -> LlmSettings:
    row = get_db().execute("SELECT value FROM settings WHERE key='llm'").fetchone()
    if row:
        data = json.loads(row["value"])
        data.setdefault("base_url", "")
        return LlmSettings(**data)
    return LlmSettings()


def save_settings(settings: LlmSettings) -> None:
    get_db().execute(
        "INSERT INTO settings (key, value) VALUES ('llm', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (settings.model_dump_json(),))
    get_db().commit()


def _local_secrets() -> dict:
    path = get_config().local_settings_path
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_secrets(secrets: dict) -> None:
    get_config().local_settings_path.write_text(
        json.dumps(secrets, indent=2), encoding="utf-8")


def store_api_key(provider: str, key: str) -> None:
    secrets = _local_secrets()
    keys = secrets.setdefault("llm_api_keys", {})
    if key:
        keys[provider] = key
    else:
        keys.pop(provider, None)   # empty string clears the stored key
    _save_secrets(secrets)


def get_api_key(provider: str) -> str | None:
    secrets = _local_secrets()
    keys = secrets.get("llm_api_keys", {})
    if keys.get(provider):
        return keys[provider]
    # legacy single-key field (pre multi-provider)
    if secrets.get("llm_api_key"):
        return secrets["llm_api_key"]
    for env in _ENV_KEYS.get(provider, ()):
        if os.environ.get(env):
            return os.environ[env]
    return os.environ.get("MITY_LLM_API_KEY")


def api_keys_set() -> dict[str, bool]:
    return {p: bool(get_api_key(p)) for p in PROVIDERS if p != "mock"}


def api_key_is_set(provider: str | None = None) -> bool:
    if provider is None:
        provider = load_settings().provider
    if provider == "mock":
        return True
    return bool(get_api_key(provider))
