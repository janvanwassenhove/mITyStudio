"""OperationPlanner: builds the LLM planning context and turns provider
output into validated ChatOperations."""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from ..models.operations import ChatOperation, OperationType
from ..models.song import SongProject
from . import asset_repo
from .llm.provider import LlmProviderError, classify_llm_error, get_provider
from .llm.settings import load_settings

log = logging.getLogger(__name__)

_OP_TYPES = list(OperationType.__args__)  # type: ignore[attr-defined]


def _asset_context(message: str, project: SongProject) -> dict:
    """Available assets the LLM may reference. It must not invent others.
    Retrieval-based (deterministic RAG over the asset registry): the
    instruments/samples listed are the ones RELEVANT to this request and
    project (keyword + bpm/key scoring), plus a library summary so the model
    knows the full inventory's shape beyond the retrieved slice."""
    from . import asset_retrieval, voice_profiles
    from .rvc_convert import rvc_model_ready

    def brief(assets, limit=40):
        return [{"id": a.id, "filename": a.filename} for a in assets[:limit]]

    return {
        "library_summary": asset_retrieval.summary(),
        "instruments": asset_retrieval.retrieve_instruments(message, project),
        "samples": asset_retrieval.retrieve_samples(message, project),
        "scores": brief(asset_repo.list_assets("score", include_missing=False)),
        "voice_profiles": [
            {"id": p.id, "name": p.name,
             "high_fidelity_model_trained": rvc_model_ready(p)}
            for p in voice_profiles.list_profiles() if p.consent_confirmed],
    }


_LANG_NAMES = {"en": "English", "nl": "Dutch (Nederlands)",
               "fr": "French (Français)", "de": "German (Deutsch)"}


def build_system_prompt(project: SongProject, language: str = "en",
                        message: str = "") -> str:
    ctx = _asset_context(message, project)
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
- add_track: name, track_type (drums|bass|guitar|keys|synth|strings|brass|sample|lead_vocal|backing_vocal|fx), soundfont_asset_id?, program?, synth_patch? (built-in synth id)
- update_track: track (name or id), name? (rename), volume? (0-2), pan? (-1..1), mute?, solo?
- split_clip: track, at_bar (1-based bar where the cut falls)
- duplicate_clip: track, at_bar? (clip covering that bar; omit = last clip)
- delete_clip: track, at_bar? (omit = last clip)
- assign_soundfont: track (name or id), soundfont_asset_id, bank, program, preset (label, for the summary)
- assign_synth: track (name or id), synth_patch (a built-in synth id from the instruments list, e.g. "synth_saw_lead", "bass_pluck", "drum_kit")
- select_sample: sample_asset_id, track?, section?, start_beat?, duration_beats?, loop?
- generate_drums/generate_bassline/generate_chords/generate_melody: section (name, id, or "all" for every section), track? (created if missing)
  → to create a FULL SONG: create_song, then add_section per section, then generate_* with section "all" (or per section) for each instrument, then rewrite_lyrics + generate_melody with track_type lead_vocal
- write_notes: COMPOSE the part yourself, note by note — section (name/id, one section per op), track, track_type, notes: [{{"midi_note": 36, "start_beat": 0, "duration_beats": 0.5, "velocity": 100}}, …]. start_beat is RELATIVE to the section start; keep notes inside the section (length_bars × beats/bar). Use this when you can write something more fitting than generate_* (a genre-true drum groove, a signature riff, a specific bass line); GM drums on midi 35-59 (36 kick, 38 snare, 42 closed hat, 46 open hat, 49 crash). Stay in the song's key for pitched parts.
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
- INSTRUMENTS: after add_track/generate_*, give every instrument track a sound.
  Two kinds appear in the instruments list:
  • SoundFont presets (richer, sampled) — assign with assign_soundfont, copying
    soundfont_asset_id + bank + program + preset EXACTLY from the list. Do NOT
    invent bank/program numbers or preset names.
  • Built-in synth patches (carry a "synth_patch" field, soundfont "Built-in
    synth") — assign with assign_synth using that synth_patch id. These ALWAYS
    work, with zero setup, even when the user has no SoundFonts installed.
  Prefer a fitting SoundFont preset when one is listed; use a synth patch when
  no preset fits, for a deliberately synthy sound, or when the instruments list
  has only built-in synths. The backend verifies SoundFont bank/program and
  swaps in a fitting real preset if you guess wrong. Match genre: punk →
  overdriven guitar, jazz/bossa → nylon or clean guitar + upright bass + soft
  kit, pop → clean keys/pads. Drums need a "Drum Kits" preset (or the
  "drum_kit" synth patch).
- SAMPLES: when a sample fits the vibe, place it with select_sample — but
  ONLY if its bpm is within ±3 of the song bpm (or it's a one-shot) and its
  key is compatible (same key, relative major/minor, or unpitched type like
  kick/snare/fx). Never place a mismatched-bpm loop. sample_asset_id MUST be
  copied EXACTLY from the samples list — if no listed sample fits, simply
  OMIT select_sample (use generate_* instead); never invent or alter an id.
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
library_summary describes the user's FULL library; the instruments/samples
lists below it are the subset retrieved as most relevant to this request —
already filtered for bpm/key fit. If nothing listed fits, use generate_*
instead; never invent ids.
{json.dumps(ctx, indent=1)}
"""


def plan(project: SongProject, message: str,
         language: str = "en"
         ) -> tuple[str, list[ChatOperation], list[str], dict | None]:
    """Returns (reply, valid_operations, validation_warnings, llm_usage)."""
    settings = load_settings()
    provider = get_provider(settings)
    system_prompt = build_system_prompt(project, language, message)
    try:
        raw = provider.plan(system_prompt, message)
    except LlmProviderError as e:
        usage = {"model": settings.model, "input_tokens": 0,
                 "output_tokens": 0, "error_kind": classify_llm_error(str(e))}
        return f"LLM error: {e}", [], [str(e)], usage

    warnings: list[str] = []
    operations: list[ChatOperation] = []
    for i, op_data in enumerate(raw.get("operations", [])):
        try:
            operations.append(ChatOperation.model_validate(op_data))
        except ValidationError as e:
            warnings.append(f"operation {i} rejected: {e.errors()[0]['msg']}")
    reply = str(raw.get("reply", "")) or "Done."
    return reply, operations, warnings, provider.last_usage
