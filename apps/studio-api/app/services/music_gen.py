"""Deterministic algorithmic music generators.

These implement the generate_* operations: the LLM (or mock planner) decides
WHAT to generate (style, section, track); these functions decide the actual
notes. Seeded randomness keeps results reproducible per (project, section).
"""
from __future__ import annotations

import random
import re

from ..models.song import Clip, NoteEvent, Section, SongProject

_NOTE_OFFSETS = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
                 "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
                 "A#": 10, "Bb": 10, "B": 11}

MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

# GM drum notes
KICK, SNARE, HAT_CLOSED, HAT_OPEN, CRASH, RIDE = 36, 38, 42, 46, 49, 51


def parse_key(key: str) -> tuple[int, bool]:
    """Returns (root pitch class, is_minor)."""
    m = re.match(r"\s*([A-G][#b]?)\s*(minor|min|m)?", key.strip(), re.IGNORECASE)
    if not m:
        return 0, False
    root = _NOTE_OFFSETS.get(m.group(1)[0].upper() + m.group(1)[1:], 0)
    is_minor = bool(m.group(2))
    return root, is_minor


def scale_notes(key: str) -> list[int]:
    root, minor = parse_key(key)
    return [(root + off) % 12 for off in (MINOR_SCALE if minor else MAJOR_SCALE)]


def chord_progression(key: str, style: str, bars: int) -> list[list[int]]:
    """Returns one chord (list of pitch classes) per bar."""
    root, minor = parse_key(key)
    scale = MINOR_SCALE if minor else MAJOR_SCALE

    def triad(degree: int) -> list[int]:
        return [(root + scale[degree % 7]) % 12,
                (root + scale[(degree + 2) % 7]) % 12,
                (root + scale[(degree + 4) % 7]) % 12]

    if minor:
        degrees = [0, 5, 2, 6]           # i VI III VII
    elif style in ("punk", "rock"):
        degrees = [0, 4, 5, 3]           # I V vi IV
    elif style in ("pop", "edm", "dance"):
        degrees = [5, 3, 0, 4]           # vi IV I V
    elif style in ("jazz", "blues"):
        degrees = [1, 4, 0, 0]           # ii V I I
    else:
        degrees = [0, 3, 4, 0]           # I IV V I
    return [triad(degrees[i % len(degrees)]) for i in range(bars)]


def _rng(project: SongProject, section: Section, salt: str) -> random.Random:
    return random.Random(f"{project.id}:{section.id}:{salt}")


def generate_drums(project: SongProject, section: Section) -> Clip:
    bpb = project.beats_per_bar
    length_beats = section.length_bars * bpb
    style = project.style.lower()
    energy = section.energy
    notes: list[NoteEvent] = []

    def hit(note: int, beat: float, vel: int, dur: float = 0.25) -> None:
        if beat < length_beats:
            notes.append(NoteEvent(midi_note=note, start_beat=beat,
                                   duration_beats=dur, velocity=vel))

    for bar in range(section.length_bars):
        base = bar * bpb
        if style in ("punk", "rock", "metal"):
            for b in range(int(bpb)):
                hit(KICK, base + b, 110)
                hit(HAT_CLOSED, base + b, 80)
                hit(HAT_CLOSED, base + b + 0.5, 60)
            hit(SNARE, base + 1, 115)
            hit(SNARE, base + 3, 115)
        elif style in ("edm", "dance", "house", "techno"):
            for b in range(int(bpb)):
                hit(KICK, base + b, 120)
                hit(HAT_OPEN, base + b + 0.5, 70)
            hit(SNARE, base + 1, 100)
            hit(SNARE, base + 3, 100)
        else:  # pop / default backbeat
            hit(KICK, base + 0, 110)
            hit(KICK, base + 2.5, 90)
            hit(SNARE, base + 1, 105)
            hit(SNARE, base + 3, 105)
            for b in range(int(bpb * 2)):
                hit(HAT_CLOSED, base + b * 0.5, 55 + int(25 * energy))
        if bar % 4 == 0 and energy > 0.6:
            hit(CRASH, base, 100, 1.0)

    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length_beats, note_events=notes)


def generate_bassline(project: SongProject, section: Section) -> Clip:
    bpb = project.beats_per_bar
    length_beats = section.length_bars * bpb
    chords = chord_progression(project.key, project.style.lower(),
                               section.length_bars)
    rng = _rng(project, section, "bass")
    notes: list[NoteEvent] = []
    for bar, chord in enumerate(chords):
        root = 36 + chord[0]  # around C2
        base = bar * bpb
        if project.style.lower() in ("punk", "rock", "metal"):
            for i in range(int(bpb * 2)):  # driving eighths
                notes.append(NoteEvent(midi_note=root, start_beat=base + i * 0.5,
                                       duration_beats=0.45, velocity=105))
        else:
            pattern = [0, 2, 3] if bpb >= 4 else [0, 1]
            for i in pattern:
                pitch = root if i == 0 else root + rng.choice([0, 7, 12, 5])
                notes.append(NoteEvent(midi_note=pitch, start_beat=base + i,
                                       duration_beats=0.9, velocity=95))
    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length_beats, note_events=notes)


def generate_chords(project: SongProject, section: Section) -> Clip:
    bpb = project.beats_per_bar
    length_beats = section.length_bars * bpb
    chords = chord_progression(project.key, project.style.lower(),
                               section.length_bars)
    notes: list[NoteEvent] = []
    for bar, chord in enumerate(chords):
        base = bar * bpb
        hits = ([0, 1, 2, 3] if project.style.lower() in ("punk", "rock")
                else [0, 2.5])
        for h in hits:
            if h >= bpb:
                continue
            for pc in chord:
                notes.append(NoteEvent(
                    midi_note=60 + pc, start_beat=base + h,
                    duration_beats=min(bpb - h, 1.5 if len(hits) > 2 else 2.4),
                    velocity=88))
    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length_beats, note_events=notes)


def generate_melody(project: SongProject, section: Section,
                    lyrics_lines: list[str] | None = None) -> Clip:
    """Melody generator; if lyrics are given, one syllable per note."""
    bpb = project.beats_per_bar
    length_beats = section.length_bars * bpb
    scale = scale_notes(project.key)
    chords = chord_progression(project.key, project.style.lower(),
                               section.length_bars)
    rng = _rng(project, section, "melody")
    syllables: list[str] = []
    for line in (lyrics_lines or []):
        syllables.extend(_syllables(line))

    notes: list[NoteEvent] = []
    syl_i = 0
    degree = scale.index(chords[0][0]) if chords[0][0] in scale else 0
    for bar in range(section.length_bars):
        base = bar * bpb
        chord = chords[bar % len(chords)]
        beat = 0.0
        while beat < bpb - 0.01:
            dur = rng.choice([0.5, 0.5, 1.0, 1.0, 1.5])
            dur = min(dur, bpb - beat)
            if rng.random() < 0.18:  # rest
                beat += dur
                continue
            if rng.random() < 0.5:  # chord tone
                pc = rng.choice(chord)
            else:                    # step in scale
                degree = max(0, min(len(scale) - 1,
                                    degree + rng.choice([-1, -1, 1, 1, 2, -2])))
                pc = scale[degree]
            pitch = 60 + pc + (12 if section.energy > 0.7 and rng.random() < 0.3 else 0)
            syl = ""
            if syllables:
                syl = syllables[syl_i % len(syllables)]
                syl_i += 1
            notes.append(NoteEvent(
                midi_note=pitch, start_beat=base + beat, duration_beats=dur * 0.95,
                velocity=90 + int(20 * section.energy), lyric_syllable=syl))
            beat += dur
    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length_beats, note_events=notes)


_VOWELS = "aeiouy"


def _syllables(line: str) -> list[str]:
    """Naive syllable splitter — good enough for karaoke timing."""
    out: list[str] = []
    for word in re.findall(r"[A-Za-z']+", line):
        groups = re.findall(r"[^aeiouy]*[aeiouy]+(?:[^aeiouy]+$)?", word,
                            re.IGNORECASE)
        out.extend(groups or [word])
    return out
