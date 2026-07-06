"""PlaybackManifest builder — the single timing source for the frontend."""
from __future__ import annotations

import json

from ..config import get_config
from ..models.song import SongProject
from . import timing


def _waveform_metadata(project: SongProject) -> list[dict]:
    """Per-stem waveform peak data, generated at render time (see
    stem_waveforms.py). Returns whatever has been cached for this project."""
    path = get_config().projects_dir / project.id / "waveforms.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def load_lyrics_alignment(project_id: str) -> list[dict]:
    path = get_config().projects_dir / project_id / "lyrics_alignment.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def build_manifest(project: SongProject) -> dict:
    sections = [timing.section_timing(project, s.id) for s in project.sections]
    tracks = []
    clips = []
    midi_notes = []
    for t in project.tracks:
        tracks.append({
            "track_id": t.id,
            "name": t.name,
            "track_type": t.track_type,
            "volume": t.volume,
            "pan": t.pan,
            "mute": t.mute,
            "solo": t.solo,
            "soundfont_asset_id": t.instrument_config.soundfont_asset_id,
            "voice_profile_id": t.voice_profile_id,
            "effects": [e.model_dump() for e in t.effects.effects],
        })
        for c in t.clips:
            ct = timing.clip_timing(project, c)
            ct["track_id"] = t.id
            clips.append(ct)
            for n in c.note_events:
                nt = timing.note_timing(project, c, n)
                nt["track_id"] = t.id
                nt["clip_id"] = c.id
                midi_notes.append(nt)

    return {
        "project_id": project.id,
        "title": project.title,
        "bpm": project.bpm,
        "time_signature": project.time_signature,
        "beats_per_bar": project.beats_per_bar,
        "total_bars": project.total_bars(),
        "duration_seconds": project.duration_seconds(),
        "sections": sections,
        "tracks": tracks,
        "clips": clips,
        "stems": [s.model_dump() for s in project.stems],
        "waveform_metadata": _waveform_metadata(project),
        "midi_note_metadata": midi_notes,
        "lyrics_alignment": load_lyrics_alignment(project.id),
        "markers": [{"bar": s["start_bar"], "seconds": s["start_seconds"],
                     "label": s["name"]} for s in sections if s],
        "mix_settings": project.mix_settings.model_dump(),
    }
