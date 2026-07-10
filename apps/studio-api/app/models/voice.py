from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .song import new_id, now_iso


class VoiceProfile(BaseModel):
    """A reusable singing voice. Creation requires explicit consent; a profile
    is only ever used when the user assigns it to a vocal track."""
    id: str = Field(default_factory=new_id)
    name: str
    source_recording_ids: list[str] = Field(default_factory=list)
    consent_confirmed: bool = False
    consent_notes: str = ""
    # persistent consent audit record: when consent was given and, when the
    # wizard was used, the recorded verbal consent clip
    consent_recorded_at: str = ""
    consent_recording_id: str | None = None
    performer_alias: str = ""
    vocal_range: str = ""
    language_notes: str = ""
    quality_score: float | None = None
    status: Literal["draft", "ready", "disabled"] = "ready"
    usage_restrictions: str = ""
    created_at: str = Field(default_factory=now_iso)


class CreateVoiceProfileRequest(BaseModel):
    name: str = Field(min_length=1)
    source_recording_ids: list[str] = Field(min_length=1)
    consent_confirmed: bool
    consent_notes: str = ""
    consent_recording_id: str | None = None   # verbal consent clip (wizard)
    performer_alias: str = ""
    vocal_range: str = ""
    language_notes: str = ""
    usage_restrictions: str = ""
