"""Arrangement dynamics + completeness (docs/song-quality.md 0.6/0.7).

Two jobs:

1. `plays_in_section` — the arrangement template: which instrument types
   play in a section, driven by Section.energy and the genre profile. This
   is what makes a verse breathe and a chorus land ("strip back verse 1,
   build into the chorus") — the single largest "sounds professional" lever,
   and it costs no LLM.

2. `fill_new_sections` — the completeness pass (mirrors
   vocal_autofill.ensure_vocal_melodies): when a chat turn ADDS sections,
   every content-bearing instrument track is extended into them per the
   template. Strictly additive — existing clips are never touched, and only
   sections created in the current turn are filled, so a clip the user
   deleted stays deleted (R1: never clobber user edits).
"""
from __future__ import annotations

import logging

from ..models.song import Section, SongProject, Track

log = logging.getLogger(__name__)

# track types governed by the template; vocals are owned by vocal_autofill
# and sample lanes are placed by hand
_CORE = ("drums", "bass", "guitar", "keys")
_COLOUR = ("strings", "brass", "synth", "fx")


def plays_in_section(track_type: str, section: Section,
                     project: SongProject) -> bool:
    """Does this instrument type belong in this section? Core rhythm plays
    almost always; colour instruments earn their entry with energy."""
    from .genres import genre_profile
    e = section.energy
    fam = genre_profile(project).family
    if track_type == "drums":
        return e >= (0.5 if fam == "ambient" else 0.28)
    if track_type == "bass":
        return e >= (0.4 if fam in ("ballad", "ambient") else 0.35)
    if track_type in ("guitar", "keys"):
        return True                      # chordal backbone always plays
    if track_type == "strings":
        return e >= 0.5
    if track_type == "brass":
        return e >= (0.45 if fam in ("funk", "bossa", "soul", "jazz") else 0.6)
    if track_type == "synth":
        # dance/synthwave lead synths sit out only true breakdowns
        return e >= (0.35 if fam in ("dance", "synthwave") else 0.55)
    if track_type == "fx":
        return e >= 0.6
    return True                          # vocals/sample: not governed here


def _generator_for(track_type: str):
    from . import music_gen
    return {
        "drums": music_gen.generate_drums,
        "bass": music_gen.generate_bassline,
        "guitar": music_gen.generate_chords,
        "keys": music_gen.generate_chords,
        "strings": music_gen.generate_chords,
        "brass": music_gen.generate_chords,
        "synth": music_gen.generate_melody,
        "fx": music_gen.generate_melody,
    }.get(track_type)


def _covers(track: Track, section: Section, bpb: float) -> bool:
    start = section.start_bar * bpb
    end = start + section.length_bars * bpb
    for c in track.clips:
        if c.section_id == section.id:
            return True
        if c.start_beat < end and c.start_beat + c.duration_beats > start:
            return True
    return False


def fill_new_sections(project: SongProject,
                      new_section_ids: set[str]) -> list[str]:
    """Extend content-bearing instrument tracks into sections added this
    turn, template-gated. Returns human-readable log lines."""
    if not new_section_ids:
        return []
    bpb = project.beats_per_bar
    new_sections = [s for s in project.sections if s.id in new_section_ids]
    lines: list[str] = []
    for track in project.tracks:
        gen = _generator_for(track.track_type)
        if gen is None:
            continue
        # only tracks that already carry musical content — an empty track is
        # a deliberate choice, not a gap to fill
        if not any(c.clip_type == "midi" and c.note_events
                   for c in track.clips):
            continue
        for section in new_sections:
            if not plays_in_section(track.track_type, section, project):
                continue
            if _covers(track, section, bpb):
                continue
            clip = gen(project, section)
            if clip.note_events:
                track.clips.append(clip)
                lines.append(f"{track.name}: extended into {section.name!r}")
    return lines
