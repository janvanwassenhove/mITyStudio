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
            "api_keys_set": llm_settings.api_keys_set(),
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
