"""ChatOperation: the only way the LLM changes a project.

Every operation is validated (structurally here, referentially in the
applier) before it touches the SongProject.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

OperationType = Literal[
    "create_song", "add_section", "update_section", "add_track", "update_track",
    "remove_track", "split_clip", "duplicate_clip", "delete_clip",
    "assign_soundfont", "select_sample", "generate_chords", "generate_melody",
    "generate_drums", "generate_bassline", "write_notes", "rewrite_lyrics",
    "change_key",
    "change_tempo", "import_score", "arrange_from_score", "add_effect",
    "update_effect", "create_vocal_track", "assign_voice_profile",
    "render_stems", "render_mix",
]


class ChatOperation(BaseModel):
    op_type: OperationType
    params: dict[str, Any] = Field(default_factory=dict)


class OperationResult(BaseModel):
    op_type: str
    summary: str
    applied: bool
    error: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    language: str = "en"   # UI language — the assistant replies in it


class ChatResponse(BaseModel):
    reply: str
    operations: list[OperationResult]
    project: dict
    # token usage of this turn (model, input_tokens, output_tokens,
    # error_kind?) — cost/rate-limit visibility in the chat panel
    usage: dict | None = None
