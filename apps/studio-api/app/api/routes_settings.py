from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.llm import settings as llm_settings
from ..services.llm.provider import get_provider
from ..services.llm.settings import LlmSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LlmSettingsUpdate(BaseModel):
    provider: str = "mock"
    model: str = "claude-sonnet-5"
    temperature: float = Field(default=0.4, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=256, le=64000)
    api_key: str | None = None   # write-only; never returned


def _public(s: LlmSettings) -> dict:
    return {"provider": s.provider, "model": s.model,
            "temperature": s.temperature, "max_tokens": s.max_tokens,
            "api_key_set": llm_settings.api_key_is_set()}


@router.get("/llm")
def get_llm_settings() -> dict:
    return _public(llm_settings.load_settings())


@router.put("/llm")
def put_llm_settings(update: LlmSettingsUpdate) -> dict:
    s = LlmSettings(provider=update.provider, model=update.model,
                    temperature=update.temperature,
                    max_tokens=update.max_tokens)
    llm_settings.save_settings(s)
    if update.api_key:
        llm_settings.store_api_key(update.api_key)
    return _public(s)


@router.post("/llm/test")
def test_llm() -> dict:
    s = llm_settings.load_settings()
    ok, message = get_provider(s).test_connection()
    return {"ok": ok, "message": message}
