"""ChatOperation: the only way the LLM changes a project.

Every operation is validated (structurally here, referentially in the
applier) before it touches the SongProject.

OP_REGISTRY is the capability registry (docs/song-quality.md 0.4): the
single source of truth for what each operation does and takes. The planner
prompt is GENERATED from it, so the model's knowledge of the studio can
never drift from the code again — a test asserts full coverage both ways.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .song import EffectType

OperationType = Literal[
    "create_song", "add_section", "update_section", "add_track", "update_track",
    "remove_track", "split_clip", "duplicate_clip", "delete_clip",
    "set_clip_fades",
    "assign_soundfont", "assign_synth", "select_sample",
    "generate_chords", "generate_melody",
    "generate_drums", "generate_bassline", "write_notes", "rewrite_lyrics",
    "change_key",
    "change_tempo", "import_score", "arrange_from_score", "add_effect",
    "update_effect", "update_mix", "auto_mix", "finalize_ending",
    "create_vocal_track",
    "assign_voice_profile",
    "render_stems", "render_mix",
]

_EFFECTS = "|".join(EffectType.__args__)  # type: ignore[attr-defined]

# op → {params: call signature, use: when/why}. Keep entries short; the
# planner prompt renders one line per op from this table.
OP_REGISTRY: dict[str, dict[str, str]] = {
    "create_song": {
        "params": "title, style, genre? (canonical family; auto-derived from "
                  "style when omitted), bpm, key, time_signature",
        "use": "set up or restyle the song. A tempo the user names always "
               "wins; only pick from the genre's typical range (see TEMPO "
               "table) when they did not ask for one"},
    "add_section": {
        "params": "name, start_bar?, length_bars, energy (0-1), description?",
        "use": "energy shapes density AND which instruments play — quiet "
               "verses ~0.4, big choruses ~0.9"},
    "update_section": {
        "params": "section (name or id), name?, length_bars?, start_bar?, "
                  "energy?, description?",
        "use": "reshape an existing section"},
    "add_track": {
        "params": "name, track_type (drums|bass|guitar|keys|synth|strings|"
                  "brass|sample|lead_vocal|backing_vocal|fx), "
                  "soundfont_asset_id?, program?, synth_patch? (built-in id)",
        "use": ""},
    "update_track": {
        "params": "track (name or id), name? (rename), volume? (0-2), "
                  "pan? (-1..1), mute?, solo?",
        "use": "balance the mix: keep lead vocal on top, pan doubled parts "
               "apart, duck pads under vocals"},
    "remove_track": {
        "params": "track (name or id)",
        "use": "delete a track the user no longer wants"},
    "split_clip": {
        "params": "track, at_bar (1-based bar where the cut falls)", "use": ""},
    "duplicate_clip": {
        "params": "track, at_bar? (clip covering that bar; omit = last clip)",
        "use": ""},
    "delete_clip": {
        "params": "track, at_bar? (omit = last clip)", "use": ""},
    "set_clip_fades": {
        "params": "track, at_bar? (clip covering that bar; omit = last clip), "
                  "fade_in_seconds?, fade_out_seconds?",
        "use": "fade the song's intro in / outro out, or smooth a sample "
               "edit — only where it serves the song"},
    "assign_soundfont": {
        "params": "track (name or id), soundfont_asset_id, bank, program, "
                  "preset (label, for the summary)",
        "use": "copy bank/program EXACTLY from the instruments list"},
    "assign_synth": {
        "params": "track (name or id), synth_patch (built-in synth id from "
                  "the instruments list, e.g. \"synth_saw_lead\", "
                  "\"bass_pluck\", \"drum_kit\")",
        "use": "built-in synths always work, zero setup"},
    "select_sample": {
        "params": "sample_asset_id, track?, section?, start_beat?, "
                  "duration_beats?, loop?", "use": ""},
    "generate_drums": {
        "params": "section (name, id, or \"all\"), track? (created if missing)",
        "use": "genre-true groove from the project's style/genre"},
    "generate_bassline": {
        "params": "section (name, id, or \"all\"), track?", "use": ""},
    "generate_chords": {
        "params": "section (name, id, or \"all\"), track?, track_type? "
                  "(guitar|keys|strings|brass)", "use": ""},
    "generate_melody": {
        "params": "section (name, id, or \"all\"), track?, track_type?, "
                  "style? (\"rap\" for rap flow)",
        "use": "with track_type lead_vocal it sings the section's lyrics"},
    "write_notes": {
        "params": "section (name/id, one section per op), track, track_type, "
                  "notes: [{midi_note, start_beat, duration_beats, "
                  "velocity}, …]",
        "use": "COMPOSE the part yourself, note by note. start_beat is "
               "RELATIVE to the section start; keep notes inside the section "
               "(length_bars × beats/bar). Use when you can write something "
               "more fitting than generate_* (a genre-true drum groove, a "
               "signature riff, a specific bass line); GM drums on midi "
               "35-59 (36 kick, 38 snare, 42 closed hat, 46 open hat, 49 "
               "crash). Stay in the song's key for pitched parts"},
    "rewrite_lyrics": {
        "params": "lines (list of strings), section?, language?", "use": ""},
    "change_key": {"params": "key", "use": ""},
    "change_tempo": {
        "params": "bpm (number, or \"+10\"/\"-10\")",
        "use": "use the exact tempo the user asks for"},
    "import_score": {
        "params": "score_asset_id",
        "use": "parse a score/PDF asset into chords, lyrics and sections"},
    "arrange_from_score": {
        "params": "score_asset_id",
        "use": "build tracks + sections from an imported score in one step"},
    "add_effect": {
        "params": f"track, effect_type ({_EFFECTS}), params",
        "use": "every effect must EARN its place — reverb/delay for space on "
               "vocals or leads, compressor to steady bass/vocals, eq to "
               "unmask; never stack effects a listener would not notice"},
    "update_effect": {
        "params": "track, effect_id or effect_type, enabled?, params?",
        "use": "tweak or disable an effect already on the track"},
    "update_mix": {
        "params": "master_volume? (0-2), normalize?, limiter?",
        "use": "master output settings for the final mix"},
    "auto_mix": {
        "params": "(none)",
        "use": "balance the whole song in one step — role-appropriate levels "
               "and pan per track plus the few effects that earn their place "
               "(vocal compression/reverb, bass compression). Use this "
               "instead of hand-setting a level on every track"},
    "finalize_ending": {
        "params": "(none)",
        "use": "give the song a real ending: fades the intro in and the "
               "final section out so it resolves instead of stopping "
               "abruptly mid-bar"},
    "create_vocal_track": {
        "params": "name?, track_type, voice_profile_id?, vocal_style? "
                  "(sing|rap|soft|powerful)", "use": ""},
    "assign_voice_profile": {
        "params": "track, voice_profile_id", "use": ""},
    "render_stems": {
        "params": "(none)",
        "use": "rarely needed — rendering happens automatically on play"},
    "render_mix": {
        "params": "(none)",
        "use": "rarely needed — use for an explicit export request"},
}


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
    # background work started for this request (e.g. the full-song
    # pipeline): {"kind": "generate_song", "job_id": ...} — the chat panel
    # polls the job and shows live progress
    job: dict | None = None
