"""Auto-sing: after chat planning, every vocal track that has lyrics but no
melody gets one — a generated song with voice + lyrics must come out SINGING
without the user having to ask for melodies per section."""
from __future__ import annotations

import logging

from ..models.song import SongProject

log = logging.getLogger(__name__)

_VOCAL = ("lead_vocal", "backing_vocal")


def ensure_vocal_melodies(project: SongProject) -> list[str]:
    """For each vocal track: any section that has lyric lines but no midi
    clip on that track gets a generated melody (harmony for backing vocals).
    Returns human-readable log lines."""
    from .music_gen import generate_vocal_melody

    lines_by_section: dict[str, list[str]] = {}
    for line in project.lyrics.lines:
        if line.section_id and line.text.strip():
            lines_by_section.setdefault(line.section_id, []).append(line.text)
    if not lines_by_section:
        return []

    out: list[str] = []
    for track in project.tracks:
        if track.track_type not in _VOCAL:
            continue
        covered = {c.section_id for c in track.clips
                   if c.clip_type == "midi" and c.note_events}
        missing = [s for s in project.sections
                   if s.id in lines_by_section and s.id not in covered]
        for section in missing:
            clip = generate_vocal_melody(
                project, section, lines_by_section[section.id],
                rap=track.vocal_style == "rap",
                harmony=track.track_type == "backing_vocal")
            if clip.note_events:
                track.clips.append(clip)
                out.append(f"{track.name}: melody written for "
                           f"section {section.name!r}")
    return out
