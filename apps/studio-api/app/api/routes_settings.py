from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.llm import settings as llm_settings
from ..services.llm.provider import get_provider
from ..services.llm.settings import PROVIDERS, LlmSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LlmSettingsUpdate(BaseModel):
    provider: str = "mock"
    model: str = ""
    base_url: str = ""
    temperature: float = Field(default=0.4, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=256, le=64000)
    api_key: str | None = None   # write-only; stored per provider; "" clears


def _public(s: LlmSettings) -> dict:
    return {"provider": s.provider, "model": s.model, "base_url": s.base_url,
            "temperature": s.temperature, "max_tokens": s.max_tokens,
            "providers": list(PROVIDERS),
            "api_keys_set": llm_settings.api_keys_set(s.base_url),
            "api_key_sources": llm_settings.api_key_sources(s.base_url),
            "api_key_set": llm_settings.api_key_is_set(s.provider)}


@router.get("/llm")
def get_llm_settings() -> dict:
    return _public(llm_settings.load_settings())


@router.put("/llm")
def put_llm_settings(update: LlmSettingsUpdate) -> dict:
    if update.provider not in PROVIDERS:
        raise HTTPException(422, f"unknown provider {update.provider!r} "
                                 f"(available: {', '.join(PROVIDERS)})")
    model = update.model.strip() or llm_settings.default_model(update.provider)
    s = LlmSettings(provider=update.provider, model=model,
                    base_url=update.base_url.strip(),
                    temperature=update.temperature,
                    max_tokens=update.max_tokens)
    llm_settings.save_settings(s)
    if update.api_key is not None and update.provider != "mock":
        llm_settings.store_api_key(update.provider, update.api_key.strip())
    return _public(s)


@router.post("/llm/test")
def test_llm() -> dict:
    s = llm_settings.load_settings()
    ok, message = get_provider(s).test_connection()
    return {"ok": ok, "message": message}


_FALLBACK_MODELS = {
    "anthropic": ["claude-fable-5", "claude-sonnet-5", "claude-opus-4-8",
                  "claude-haiku-4-5-20251001"],
    "openai": ["gpt-5.2", "gpt-5.2-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini"],
    "custom": [],
}


@router.get("/llm/models")
def list_models(provider: str, base_url: str = "") -> dict:
    """Models for a provider: fetched live from the provider's models API
    when a key is available, curated fallback otherwise."""
    if provider not in PROVIDERS:
        raise HTTPException(422, f"unknown provider {provider!r}")
    if provider == "mock":
        return {"models": ["mock"], "source": "static"}

    key = llm_settings.get_api_key(provider, base_url)
    fallback = {"models": _FALLBACK_MODELS.get(provider, []),
                "source": "fallback"}
    if not key and not (provider == "custom" and base_url):
        return fallback
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            models = [m.id for m in client.models.list(limit=50)]
        else:
            from openai import OpenAI
            client = OpenAI(api_key=key or "not-needed",
                            base_url=base_url.strip() or None, timeout=15)
            models = [m.id for m in client.models.list()]
        if not models:
            return fallback
        # chat-capable first: filter obvious non-chat artifacts for openai
        if provider == "openai":
            models = [m for m in models
                      if not any(x in m for x in ("embedding", "whisper",
                                                  "tts", "dall-e", "audio",
                                                  "image", "moderation",
                                                  "realtime", "transcribe"))]
        return {"models": sorted(models), "source": "live"}
    except Exception as e:
        fallback["error"] = str(e)[:200]
        return fallback
