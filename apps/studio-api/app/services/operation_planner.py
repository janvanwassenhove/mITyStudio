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
    """Available assets the LLM may reference. It must not invent others.
    Composition-aware: real instrument presets (bank/program), analysed
    sample metadata (bpm/key/type), voice readiness."""
    from . import sample_analysis, voice_profiles
    from .rvc_convert import rvc_model_ready
    from .sf2_parser import instrument_catalog

    # instruments: a curated slice of the categorized preset catalog
    instruments: list[dict] = []
    for cat in instrument_catalog():
        for p in cat["presets"][:8]:
            instruments.append({"category": cat["category"],
                                "preset": p["label"],
                                "soundfont_asset_id": p["asset_id"],
                                "bank": p["bank"], "program": p["program"]})

    # samples: analysed ones first, with the data that matters for fit
    samples: list[dict] = []
    analysed_first = sorted(
        asset_repo.list_assets("sample", include_missing=False),
        key=lambda a: a.analysis_status != "analysed")
    for a in analysed_first[:80]:
        entry: dict = {"id": a.id, "filename": a.filename, "tags": a.tags[:4]}
        analysis = sample_analysis.get_analysis(a.id) or {}
        for k_src, k_dst in (("estimated_bpm", "bpm"), ("estimated_key", "key"),
                             ("sound_type_guess", "type"),
                             ("loopability_estimate", "loopable")):
            if analysis.get(k_src) is not None:
                entry[k_dst] = analysis[k_src]
        samples.append(entry)

    def brief(assets, limit=40):
        return [{"id": a.id, "filename": a.filename} for a in assets[:limit]]

    return {
        "instruments": instruments,
        "samples": samples,
        "scores": brief(asset_repo.list_assets("score", include_missing=False)),
        "voice_profiles": [
            {"id": p.id, "name": p.name,
             "high_fidelity_model_trained": rvc_model_ready(p)}
            for p in voice_profiles.list_profiles() if p.consent_confirmed],
    }


_LANG_NAMES = {"en": "English", "nl": "Dutch (Nederlands)",
               "fr": "French (Français)", "de": "German (Deutsch)"}


def build_system_prompt(project: SongProject, language: str = "en") -> str:
    ctx = _asset_context()
    lang_name = _LANG_NAMES.get(language, "English")
    return f"""You are the song-planning engine of mITyStudio, a local music studio.
Write the "reply" field in {lang_name} — unless the user writes in a
different language, then match theirs. Operation params stay as specified.
When you write lyrics (rewrite_lyrics), also set its "language" param to the
lyrics' ISO code (en/nl/fr/de) so the singing engine pronounces them right.
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
- split_clip: track, at_bar (1-based bar where the cut falls)
- duplicate_clip: track, at_bar? (clip covering that bar; omit = last clip)
- delete_clip: track, at_bar? (omit = last clip)
- assign_soundfont: track (name or id), soundfont_asset_id, bank, program, preset (label, for the summary)
- select_sample: sample_asset_id, track?, section?, start_beat?, duration_beats?, loop?
- generate_drums/generate_bassline/generate_chords/generate_melody: section (name, id, or "all" for every section), track? (created if missing)
  → to create a FULL SONG: create_song, then add_section per section, then generate_* with section "all" (or per section) for each instrument, then rewrite_lyrics + generate_melody with track_type lead_vocal
- rewrite_lyrics: lines (list of strings), section?, language?
- change_key: key; change_tempo: bpm (number, or "+10"/"-10")
- add_effect: track, effect_type (gain|pan|eq|compressor|reverb|delay|distortion), params
- create_vocal_track: name?, track_type, voice_profile_id?, vocal_style? (sing|rap)
- generate_melody with style: "rap" produces a rap flow instead of a sung melody
- assign_voice_profile: track, voice_profile_id

STRICT RULES:
- Only reference asset ids that appear in AVAILABLE ASSETS below. Never invent ids.
- Only reference voice profiles listed below (they have confirmed consent).
- Section references may use section names from the CURRENT PROJECT.
- Prefer generate_* operations for musical content; you may add explicit lyrics.

COMPOSE LIKE A PRODUCER (use the asset data):
- INSTRUMENTS: after add_track/generate_*, pick a fitting preset from the
  instruments list and assign it with assign_soundfont (soundfont_asset_id +
  bank + program + preset). Match genre: punk → overdriven guitar, jazz →
  upright bass + ride-friendly kit, pop → clean keys/pads. Drums need a
  "Drum Kits" preset.
- SAMPLES: when a sample fits the vibe, place it with select_sample — but
  ONLY if its bpm is within ±3 of the song bpm (or it's a one-shot) and its
  key is compatible (same key, relative major/minor, or unpitched type like
  kick/snare/fx). Never place a mismatched-bpm loop.
- VOICE: give vocal tracks a voice profile (assign_voice_profile). Prefer
  profiles with high_fidelity_model_trained=true. Use vocal_style "rap" when
  the user wants rap/hip-hop flow.

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


def plan(project: SongProject, message: str,
         language: str = "en") -> tuple[str, list[ChatOperation], list[str]]:
    """Returns (reply, valid_operations, validation_warnings)."""
    settings = load_settings()
    provider = get_provider(settings)
    system_prompt = build_system_prompt(project, language)
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
