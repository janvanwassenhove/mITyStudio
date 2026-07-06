"""OperationPlanner: builds the LLM planning context and turns provider
output into validated ChatOperations."""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from ..models.operations import ChatOperation, OperationType
from ..models.song import SongProject
from . import asset_repo
from .llm.provider import LlmProviderError, get_provider
from .llm.settings import load_settings

log = logging.getLogger(__name__)

_OP_TYPES = list(OperationType.__args__)  # type: ignore[attr-defined]


def _asset_context() -> dict:
    """Available assets the LLM may reference. It must not invent others."""
    def brief(assets, limit=120):
        return [{"id": a.id, "filename": a.filename,
                 "tags": a.tags[:6]} for a in assets[:limit]]
    from . import voice_profiles
    return {
        "soundfonts": brief(asset_repo.list_assets("soundfont", include_missing=False)),
        "samples": brief(asset_repo.list_assets("sample", include_missing=False)),
        "scores": brief(asset_repo.list_assets("score", include_missing=False)),
        "voice_profiles": [{"id": p.id, "name": p.name}
                           for p in voice_profiles.list_profiles()
                           if p.consent_confirmed],
    }


def build_system_prompt(project: SongProject) -> str:
    ctx = _asset_context()
    return f"""You are the song-planning engine of mITyStudio, a local music studio.
You NEVER generate audio or files. You ONLY return JSON with structured operations
that the studio backend validates and applies to the current song project.

Return exactly one JSON object:
{{"reply": "<short human summary>", "operations": [{{"op_type": "...", "params": {{...}}}}]}}

Allowed op_type values: {json.dumps(_OP_TYPES)}

Key params per operation:
- create_song: title, style, bpm, key, time_signature
- add_section: name, start_bar?, length_bars, energy (0-1), description?
- add_track: name, track_type (drums|bass|guitar|keys|synth|strings|brass|sample|lead_vocal|backing_vocal|fx), soundfont_asset_id?, program?
- update_track: track (name or id), name? (rename), volume? (0-2), pan? (-1..1), mute?, solo?
- assign_soundfont: track (name or id), soundfont_asset_id
- select_sample: sample_asset_id, track?, section?, start_beat?, duration_beats?, loop?
- generate_drums/generate_bassline/generate_chords/generate_melody: section (name, id, or "all" for every section), track? (created if missing)
  → to create a FULL SONG: create_song, then add_section per section, then generate_* with section "all" (or per section) for each instrument, then rewrite_lyrics + generate_melody with track_type lead_vocal
- rewrite_lyrics: lines (list of strings), section?, language?
- change_key: key; change_tempo: bpm (number, or "+10"/"-10")
- add_effect: track, effect_type (gain|pan|eq|compressor|reverb|delay|distortion), params
- create_vocal_track: name?, track_type, voice_profile_id?
- assign_voice_profile: track, voice_profile_id

STRICT RULES:
- Only reference asset ids that appear in AVAILABLE ASSETS below. Never invent ids.
- Only reference voice profiles listed below (they have confirmed consent).
- Section references may use section names from the CURRENT PROJECT.
- Prefer generate_* operations for musical content; you may add explicit lyrics.

CURRENT PROJECT:
{json.dumps({"title": project.title, "style": project.style, "bpm": project.bpm,
             "key": project.key, "time_signature": project.time_signature,
             "sections": [{"id": s.id, "name": s.name, "start_bar": s.start_bar,
                           "length_bars": s.length_bars} for s in project.sections],
             "tracks": [{"id": t.id, "name": t.name, "track_type": t.track_type}
                        for t in project.tracks],
             "lyrics_lines": len(project.lyrics.lines)}, indent=1)}

AVAILABLE ASSETS (the ONLY assets you may reference):
{json.dumps(ctx, indent=1)}
"""


def plan(project: SongProject, message: str) -> tuple[str, list[ChatOperation], list[str]]:
    """Returns (reply, valid_operations, validation_warnings)."""
    settings = load_settings()
    provider = get_provider(settings)
    system_prompt = build_system_prompt(project)
    try:
        raw = provider.plan(system_prompt, message)
    except LlmProviderError as e:
        return f"LLM error: {e}", [], [str(e)]

    warnings: list[str] = []
    operations: list[ChatOperation] = []
    for i, op_data in enumerate(raw.get("operations", [])):
        try:
            operations.append(ChatOperation.model_validate(op_data))
        except ValidationError as e:
            warnings.append(f"operation {i} rejected: {e.errors()[0]['msg']}")
    reply = str(raw.get("reply", "")) or "Done."
    return reply, operations, warnings
