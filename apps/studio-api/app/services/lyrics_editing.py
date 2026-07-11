"""Lyrics editing: version history + melody re-sync.

Melody notes carry exactly one syllable each (generate_vocal_melody), so any
text change must redistribute syllables — we regenerate the section's vocal
melody from the new text (deterministic seed → stable result for the same
structure). The notes' lyric_syllable values are part of track_fingerprint,
so edited sections automatically re-render on the next play.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models.song import LyricsVersion, SongProject

_VOCAL_TYPES = ("lead_vocal", "backing_vocal")
HISTORY_CAP = 20


def snapshot(project: SongProject, label: str) -> None:
    """Save the current lines as a version — skipped when nothing changed."""
    doc = project.lyrics
    if doc.history and [l.model_dump() for l in doc.history[-1].lines] \
            == [l.model_dump() for l in doc.lines]:
        return
    doc.history.append(LyricsVersion(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        label=label,
        lines=[l.model_copy(deep=True) for l in doc.lines]))
    del doc.history[:-HISTORY_CAP]


def resync_section(project: SongProject, section_id: str) -> int:
    """Regenerate vocal melodies of one section from its current lyrics.
    Returns the number of clips re-synced."""
    from .music_gen import generate_vocal_melody

    section = next((s for s in project.sections if s.id == section_id), None)
    if section is None:
        return 0
    lines = [l.text for l in project.lyrics.lines
             if l.section_id == section_id and l.text.strip()]
    resynced = 0
    for track in project.tracks:
        if track.track_type not in _VOCAL_TYPES:
            continue
        for clip in track.clips:
            if (clip.section_id == section_id and clip.clip_type == "midi"
                    and clip.note_events):
                new = generate_vocal_melody(project, section, lines,
                                            rap=track.vocal_style == "rap")
                clip.note_events = new.note_events
                clip.start_beat = new.start_beat
                clip.duration_beats = new.duration_beats
                resynced += 1
    return resynced


def update_line(project: SongProject, line_id: str, text: str) -> dict:
    line = next((l for l in project.lyrics.lines if l.id == line_id), None)
    if line is None:
        raise KeyError(f"lyric line {line_id} not found")
    if line.text == text:
        return {"changed": False, "resynced_clips": 0}
    snapshot(project, "edit")
    line.text = text
    resynced = resync_section(project, line.section_id) if line.section_id else 0
    return {"changed": True, "resynced_clips": resynced,
            "needs_render": resynced > 0}


def restore_version(project: SongProject, version_id: str) -> dict:
    version = next((v for v in project.lyrics.history if v.id == version_id),
                   None)
    if version is None:
        raise KeyError(f"lyrics version {version_id} not found")
    snapshot(project, "restore")
    project.lyrics.lines = [l.model_copy(deep=True) for l in version.lines]
    resynced = 0
    for sid in {l.section_id for l in project.lyrics.lines if l.section_id}:
        resynced += resync_section(project, sid)
    return {"restored": version.timestamp, "lines": len(version.lines),
            "resynced_clips": resynced, "needs_render": resynced > 0}
