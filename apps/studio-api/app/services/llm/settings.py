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
    "anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "custom": ("MITY_LLM_API_KEY",),
}

# for the custom provider: base_url substring → conventional env var name
_DOMAIN_ENV_KEYS = (
    ("openrouter", "OPENROUTER_API_KEY"),
    ("groq", "GROQ_API_KEY"),
    ("mistral", "MISTRAL_API_KEY"),
    ("deepseek", "DEEPSEEK_API_KEY"),
    ("together", "TOGETHER_API_KEY"),
    ("generativelanguage", "GEMINI_API_KEY"),
    ("googleapis", "GEMINI_API_KEY"),
    ("cerebras", "CEREBRAS_API_KEY"),
    ("x.ai", "XAI_API_KEY"),
    ("perplexity", "PERPLEXITY_API_KEY"),
    ("fireworks", "FIREWORKS_API_KEY"),
)

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


def _domain_env_var(base_url: str) -> str | None:
    url = base_url.lower()
    if not url:
        return None
    for needle, env in _DOMAIN_ENV_KEYS:
        if needle in url:
            return env
    return None


def key_source(provider: str, base_url: str = "") -> str | None:
    """Where the key for a provider comes from:
    'stored', an environment variable name, or None."""
    secrets = _local_secrets()
    if secrets.get("llm_api_keys", {}).get(provider):
        return "stored"
    if secrets.get("llm_api_key"):   # legacy single-key field
        return "stored"
    for env in _ENV_KEYS.get(provider, ()):
        if os.environ.get(env):
            return env
    if provider == "custom":
        env = _domain_env_var(base_url)
        if env and os.environ.get(env):
            return env
    if os.environ.get("MITY_LLM_API_KEY"):
        return "MITY_LLM_API_KEY"
    return None


def get_api_key(provider: str, base_url: str = "") -> str | None:
    if not base_url and provider == "custom":
        base_url = load_settings().base_url
    source = key_source(provider, base_url)
    if source is None:
        return None
    if source == "stored":
        secrets = _local_secrets()
        return (secrets.get("llm_api_keys", {}).get(provider)
                or secrets.get("llm_api_key"))
    return os.environ.get(source)


def api_keys_set(base_url: str = "") -> dict[str, bool]:
    return {p: key_source(p, base_url) is not None
            for p in PROVIDERS if p != "mock"}


def api_key_sources(base_url: str = "") -> dict[str, str | None]:
    return {p: key_source(p, base_url) for p in PROVIDERS if p != "mock"}


def api_key_is_set(provider: str | None = None) -> bool:
    if provider is None:
        provider = load_settings().provider
    if provider == "mock":
        return True
    return key_source(provider, load_settings().base_url) is not None
