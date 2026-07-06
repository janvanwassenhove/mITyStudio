"""LLM settings. Non-secret settings live in SQLite; the API key lives in
apps/studio-api/local_settings.json (git-ignored) or the ANTHROPIC_API_KEY /
MITY_LLM_API_KEY environment variables. Keys are never returned to clients
and never committed.
"""
from __future__ import annotations

import json
import os

from pydantic import BaseModel, Field

from ...config import get_config
from ...db import get_db

DEFAULTS = {"provider": "mock", "model": "claude-sonnet-5",
            "temperature": 0.4, "max_tokens": 4096}


class LlmSettings(BaseModel):
    provider: str = "mock"
    model: str = "claude-sonnet-5"
    api_key_reference: str = "local_settings"   # where the key is looked up
    temperature: float = Field(default=0.4, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=256, le=64000)


def load_settings() -> LlmSettings:
    row = get_db().execute("SELECT value FROM settings WHERE key='llm'").fetchone()
    if row:
        return LlmSettings(**json.loads(row["value"]))
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


def store_api_key(key: str) -> None:
    path = get_config().local_settings_path
    secrets = _local_secrets()
    secrets["llm_api_key"] = key
    path.write_text(json.dumps(secrets, indent=2), encoding="utf-8")


def get_api_key() -> str | None:
    key = _local_secrets().get("llm_api_key")
    if key:
        return key
    return os.environ.get("MITY_LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")


def api_key_is_set() -> bool:
    return bool(get_api_key())
