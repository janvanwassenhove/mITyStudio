"""Timing service: all bar/beat/second math lives here.

The frontend never guesses timing — it consumes the PlaybackManifest built
from these conversions.
"""
from __future__ import annotations

from ..models.song import SongProject


def beats_per_bar(project: SongProject) -> float:
    return project.beats_per_bar


def bars_to_beats(project: SongProject, bars: float) -> float:
    return bars * project.beats_per_bar


def beats_to_seconds(project: SongProject, beats: float) -> float:
    return beats * 60.0 / project.bpm


def seconds_to_beats(project: SongProject, seconds: float) -> float:
    return seconds * project.bpm / 60.0


def section_timing(project: SongProject, section_id: str) -> dict | None:
    s = project.get_section(section_id)
    if s is None:
        return None
    start_beat = bars_to_beats(project, s.start_bar)
    duration_beats = bars_to_beats(project, s.length_bars)
    return {
        "section_id": s.id,
        "name": s.name,
        "start_bar": s.start_bar,
        "length_bars": s.length_bars,
        "start_beat": start_beat,
        "end_beat": start_beat + duration_beats,
        "start_seconds": beats_to_seconds(project, start_beat),
        "end_seconds": beats_to_seconds(project, start_beat + duration_beats),
        "energy": s.energy,
        "description": s.description,
    }


def clip_timing(project: SongProject, clip) -> dict:
    return {
        "clip_id": clip.id,
        "section_id": clip.section_id,
        "clip_type": clip.clip_type,
        "start_beat": clip.start_beat,
        "end_beat": clip.start_beat + clip.duration_beats,
        "start_seconds": beats_to_seconds(project, clip.start_beat),
        "end_seconds": beats_to_seconds(project, clip.start_beat + clip.duration_beats),
        "source_asset_id": clip.source_asset_id,
    }


def note_timing(project: SongProject, clip, note) -> dict:
    abs_start = clip.start_beat + note.start_beat
    return {
        "note_id": note.id,
        "midi_note": note.midi_note,
        "pitch": note.pitch,
        "velocity": note.velocity,
        "start_beat": abs_start,
        "end_beat": abs_start + note.duration_beats,
        "start_seconds": beats_to_seconds(project, abs_start),
        "end_seconds": beats_to_seconds(project, abs_start + note.duration_beats),
        "lyric_syllable": note.lyric_syllable,
    }
