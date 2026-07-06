from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AssetType = Literal[
    "score", "soundfont", "sample", "voice_recording", "voice_profile",
    "rendered_stem", "vocal_stem", "exported_mix",
]

SCORE_EXTENSIONS = {".mid", ".midi", ".musicxml", ".xml", ".gp3", ".gp4",
                    ".gp5", ".gpx", ".mscz", ".pdf"}
SOUNDFONT_EXTENSIONS = {".sf2", ".sf3", ".sfz"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif", ".m4a"}


class Asset(BaseModel):
    id: str
    asset_type: AssetType
    filename: str
    original_path: str
    relative_path: str
    extension: str
    file_size: int = 0
    content_hash: str = ""
    modified_at: str | None = None
    created_at: str | None = None
    analysis_status: Literal["pending", "analysed", "failed", "not_applicable"] = "pending"
    tags: list[str] = Field(default_factory=list)
    user_description: str = ""
    generated_description: str = ""
    license_notes: str = ""
    source: str = "scan"  # scan | upload | live_recording | render | export
    is_missing: bool = False


class AssetMetadataPatch(BaseModel):
    """User-editable metadata; survives rescans."""
    tags: list[str] | None = None
    user_description: str | None = None
    license_notes: str | None = None
