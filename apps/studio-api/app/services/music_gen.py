"""Algorithmic music generators — production-quality pass.

What makes these sound like parts instead of patterns:
- humanized timing (±8 ms swing-aware jitter) and velocity contours
- chord voicings with inversions chosen by voice-leading distance
- guitar strums (sequential note offsets, down/up velocity shapes),
  power chords for rock/punk/metal
- drum grooves with accents, ghost notes, open-hat pushes, fills every
  4 bars and crashes on section starts, density scaled by section energy
- bass lines with passing notes approaching the next chord and style
  patterns (driving 8ths, syncopated pop, walking jazz)
- melodies built from a repeated 2-bar motif with variations, phrase
  arcs that resolve to chord tones, and breaths between phrases

Seeded randomness keeps every (project, section) render reproducible.
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
KICK, SNARE, RIM, HAT_CLOSED, HAT_PEDAL, HAT_OPEN = 36, 38, 37, 42, 44, 46
CRASH, RIDE, TOM_LO, TOM_MID, TOM_HI = 49, 51, 45, 47, 50

_ROCKY = ("punk", "rock", "metal", "grunge")
_DANCY = ("edm", "dance", "house", "techno", "electro")
_JAZZY = ("jazz", "blues", "swing")


def parse_key(key: str) -> tuple[int, bool]:
    m = re.match(r"\s*([A-G][#b]?)\s*(minor|min|m)?", key.strip(), re.IGNORECASE)
    if not m:
        return 0, False
    root = _NOTE_OFFSETS.get(m.group(1)[0].upper() + m.group(1)[1:], 0)
    return root, bool(m.group(2))


def scale_notes(key: str) -> list[int]:
    root, minor = parse_key(key)
    return [(root + off) % 12 for off in (MINOR_SCALE if minor else MAJOR_SCALE)]


def chord_progression(key: str, style: str, bars: int) -> list[list[int]]:
    """One chord (list of pitch classes, root first) per bar."""
    root, minor = parse_key(key)
    scale = MINOR_SCALE if minor else MAJOR_SCALE

    def triad(degree: int, seventh: bool = False) -> list[int]:
        pcs = [(root + scale[(degree + i) % 7]) % 12 for i in (0, 2, 4)]
        if seventh:
            pcs.append((root + scale[(degree + 6) % 7]) % 12)
        return pcs

    seventh = style in _JAZZY
    if minor:
        degrees = [0, 5, 2, 6]           # i VI III VII
    elif style in _ROCKY:
        degrees = [0, 4, 5, 3]           # I V vi IV
    elif style in _DANCY or style == "pop":
        degrees = [5, 3, 0, 4]           # vi IV I V
    elif style in _JAZZY:
        degrees = [1, 4, 0, 5]           # ii V I vi
    else:
        degrees = [0, 3, 4, 0]           # I IV V I
    return [triad(degrees[i % len(degrees)], seventh) for i in range(bars)]


def _rng(project: SongProject, section: Section, salt: str) -> random.Random:
    return random.Random(f"{project.id}:{section.id}:{salt}")


def _note(notes: list[NoteEvent], midi: int, beat: float, dur: float, vel: int,
          rng: random.Random, length_beats: float, jitter: float = 0.02,
          syllable: str = "") -> None:
    """Humanized note append: timing jitter + velocity variation."""
    beat = max(0.0, beat + rng.uniform(-jitter, jitter))
    if beat >= length_beats - 0.01:
        return
    dur = min(dur, length_beats - beat)
    vel = max(20, min(127, vel + rng.randint(-6, 6)))
    notes.append(NoteEvent(midi_note=max(0, min(127, midi)), start_beat=round(beat, 4),
                           duration_beats=round(max(dur, 1 / 32), 4),
                           velocity=vel, lyric_syllable=syllable))


# --------------------------------------------------------------------------
# DRUMS
# --------------------------------------------------------------------------

def generate_drums(project: SongProject, section: Section) -> Clip:
    bpb = project.beats_per_bar
    length = section.length_bars * bpb
    style = project.style.lower()
    energy = section.energy
    rng = _rng(project, section, "drums")
    notes: list[NoteEvent] = []

    def hit(n: int, b: float, v: int, d: float = 0.2, j: float = 0.012) -> None:
        _note(notes, n, b, d, v, rng, length, j)

    hat_step = 0.25 if (energy > 0.75 and style in _ROCKY + _DANCY) else 0.5
    for bar in range(section.length_bars):
        base = bar * bpb
        is_fill_bar = (bar % 4 == 3) and energy > 0.35 and section.length_bars >= 4
        fill_start = bpb - 1.0 if is_fill_bar else bpb + 1  # last beat of fill bars

        # kick/snare skeleton per style
        if style in _ROCKY:
            for b in range(int(bpb)):
                hit(KICK, base + b, 112)
            hit(SNARE, base + 1, 116)
            hit(SNARE, base + 3, 118)
            if energy > 0.6 and rng.random() < 0.4:
                hit(KICK, base + 2.5, 96)   # push into beat 3
        elif style in _DANCY:
            for b in range(int(bpb)):
                hit(KICK, base + b, 122, j=0.004)
                hit(HAT_OPEN, base + b + 0.5, 60 + int(30 * energy), 0.3)
            hit(SNARE, base + 1, 100)
            hit(SNARE, base + 3, 102)
        elif style in _JAZZY:
            # ride swing pattern, cross-stick on 2 & 4, feathered kick
            for b in range(int(bpb)):
                hit(RIDE, base + b, 88)
                hit(RIDE, base + b + 0.66, 66)
            hit(RIM, base + 1, 78)
            hit(RIM, base + 3, 80)
            hit(HAT_PEDAL, base + 1, 60)
            hit(HAT_PEDAL, base + 3, 60)
            if rng.random() < 0.3:
                hit(KICK, base + rng.choice([0.0, 2.0]), 55)
        else:  # pop / default backbeat
            hit(KICK, base + 0, 112)
            if energy > 0.4:
                hit(KICK, base + 2.5, 92)
            if rng.random() < 0.35:
                hit(KICK, base + 3.5, 84)
            hit(SNARE, base + 1, 110)
            hit(SNARE, base + 3, 112)
            # ghost snares
            if energy > 0.5 and rng.random() < 0.5:
                hit(SNARE, base + rng.choice([1.75, 3.75]), 38, 0.1)

        # hats with downbeat accents (not for dance/jazz which set their own)
        if style not in _DANCY and style not in _JAZZY:
            b = 0.0
            while b < bpb - 0.01:
                on_beat = abs(b - round(b)) < 0.01
                vel = (78 if on_beat else 56) + int(22 * energy)
                if base + b < base + fill_start:
                    hit(HAT_CLOSED, base + b, vel, 0.12)
                b += hat_step
            if energy > 0.55 and rng.random() < 0.5:
                hit(HAT_OPEN, base + bpb - 0.5, 74, 0.4)  # open-hat push

        # fills: snare/tom run over the last beat of every 4th bar
        if is_fill_bar:
            fill_notes = rng.choice([
                [SNARE, SNARE, TOM_HI, TOM_LO],
                [SNARE, TOM_HI, TOM_MID, TOM_LO],
                [SNARE, SNARE, SNARE, SNARE],
                [TOM_HI, TOM_HI, TOM_MID, TOM_LO],
            ])
            for i, n in enumerate(fill_notes):
                hit(n, base + fill_start + i * 0.25, 88 + i * 8, 0.2)

        # crash on section start and after every fill
        if bar == 0 or (bar % 4 == 0 and bar > 0 and energy > 0.5):
            hit(CRASH, base, 104, 1.2)

    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length, note_events=notes)


# --------------------------------------------------------------------------
# BASS
# --------------------------------------------------------------------------

def _nearest_octave(pc: int, around: int) -> int:
    """MIDI note with pitch class pc nearest to 'around'."""
    candidates = [pc + 12 * o for o in range(11) if 0 <= pc + 12 * o <= 127]
    return min(candidates, key=lambda n: abs(n - around))


def generate_bassline(project: SongProject, section: Section) -> Clip:
    bpb = project.beats_per_bar
    length = section.length_bars * bpb
    style = project.style.lower()
    energy = section.energy
    chords = chord_progression(project.key, style, section.length_bars)
    rng = _rng(project, section, "bass")
    notes: list[NoteEvent] = []

    for bar, chord in enumerate(chords):
        base = bar * bpb
        root = _nearest_octave(chord[0], 38)          # around D2
        fifth = _nearest_octave(chord[1 % len(chord)], root + 5)
        next_chord = chords[(bar + 1) % len(chords)]
        next_root = _nearest_octave(next_chord[0], root)

        if style in _ROCKY:
            # driving 8ths, accented downbeats, approach note into next bar
            for i in range(int(bpb * 2)):
                b = i * 0.5
                vel = 108 if b % 1 == 0 else 96
                pitch = root
                if b >= bpb - 0.5 and next_root != root:
                    pitch = next_root + (1 if next_root < root else -1)
                _note(notes, pitch, base + b, 0.46, vel, rng, length, 0.008)
            if energy > 0.7 and rng.random() < 0.3:
                _note(notes, root + 12, base + bpb - 0.5, 0.4, 100, rng, length)
        elif style in _JAZZY:
            # walking quarter notes: root, chord tone, scale walk, approach
            walk = [root,
                    _nearest_octave(chord[2 % len(chord)], root),
                    fifth,
                    next_root + rng.choice([-1, 1, -2, 2])]
            for i, pitch in enumerate(walk[:int(bpb)]):
                _note(notes, pitch, base + i, 0.92, 92 + rng.randint(-4, 8),
                      rng, length, 0.015)
        elif style in _DANCY:
            # off-beat octave bounce
            for b in range(int(bpb)):
                _note(notes, root, base + b, 0.4, 106, rng, length, 0.005)
                _note(notes, root + 12, base + b + 0.5, 0.35, 92, rng, length, 0.005)
        else:
            # pop: root on 1, syncopated pushes, fifth colour, approach note
            _note(notes, root, base + 0, 1.4, 104, rng, length)
            _note(notes, root, base + 1.5, 0.4, 90, rng, length)
            _note(notes, fifth if rng.random() < 0.5 else root, base + 2.5,
                  0.9, 96, rng, length)
            if next_root != root:
                _note(notes, next_root + rng.choice([-2, -1, 1, 2]),
                      base + bpb - 0.5, 0.45, 88, rng, length)
            elif rng.random() < 0.4:
                _note(notes, root + 12, base + bpb - 0.5, 0.4, 86, rng, length)

    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length, note_events=notes)


# --------------------------------------------------------------------------
# CHORDS (guitar strums / keys voicings)
# --------------------------------------------------------------------------

def _voice_chord(pcs: list[int], prev: list[int] | None,
                 center: int = 60) -> list[int]:
    """Voice a chord around 'center', choosing the inversion with minimal
    movement from the previous voicing (voice leading)."""
    best: list[int] | None = None
    best_cost = 1e9
    for inversion in range(len(pcs)):
        order = pcs[inversion:] + pcs[:inversion]
        voiced = []
        cur = center - 6
        for pc in order:
            n = _nearest_octave(pc, max(cur + 1, center - 8))
            while voiced and n <= voiced[-1]:
                n += 12
            voiced.append(n)
            cur = n
        if prev:
            cost = sum(min(abs(a - b) for b in prev) for a in voiced)
        else:
            cost = abs(voiced[0] - center)
        if cost < best_cost:
            best_cost = cost
            best = voiced
    return best or [center]


def generate_chords(project: SongProject, section: Section) -> Clip:
    bpb = project.beats_per_bar
    length = section.length_bars * bpb
    style = project.style.lower()
    energy = section.energy
    chords = chord_progression(project.key, style, section.length_bars)
    rng = _rng(project, section, "chords")
    notes: list[NoteEvent] = []
    prev_voicing: list[int] | None = None

    guitarish = style in _ROCKY or style in ("folk", "country")

    for bar, chord in enumerate(chords):
        base = bar * bpb
        if guitarish and style in _ROCKY:
            # power chords, palm-mute feel: root+5th+octave, driving 8ths
            root = _nearest_octave(chord[0], 45)
            stack = [root, root + 7, root + 12]
            for i in range(int(bpb * 2)):
                b = i * 0.5
                accent = 106 if b % 2 == 0 else 92
                dur = 0.4 if i < bpb * 2 - 1 else 0.9
                for j, n in enumerate(stack):
                    _note(notes, n, base + b + j * 0.006, dur, accent - j * 4,
                          rng, length, 0.006)
        elif guitarish:
            # folk strum pattern D _ D U _ U D U with up-strums lighter
            voiced = _voice_chord(chord, prev_voicing, center=55)
            prev_voicing = voiced
            pattern = [(0.0, True), (1.0, True), (1.5, False), (2.5, False),
                       (3.0, True), (3.5, False)]
            for b, down in pattern:
                if b >= bpb:
                    continue
                order = voiced if down else list(reversed(voiced))
                for j, n in enumerate(order):
                    _note(notes, n, base + b + j * 0.012,
                          0.9 if down else 0.5, (96 if down else 78) - j * 3,
                          rng, length, 0.004)
        else:
            # keys: voice-led sustained chords; arpeggiate at low energy
            voiced = _voice_chord(chord, prev_voicing, center=62)
            prev_voicing = voiced
            if energy < 0.4:
                arp = voiced + [voiced[1]]
                step = bpb / len(arp)
                for i, n in enumerate(arp):
                    _note(notes, n, base + i * step, step * 1.6, 78, rng,
                          length, 0.01)
            else:
                hits = [(0.0, bpb * 0.6), (2.5, bpb - 2.5 + 0.4)] \
                    if bpb >= 4 else [(0.0, bpb)]
                for b, dur in hits:
                    for j, n in enumerate(voiced):
                        _note(notes, n, base + b + j * 0.008, dur,
                              88 - j * 3 + int(10 * energy), rng, length, 0.008)

    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length, note_events=notes)


# --------------------------------------------------------------------------
# MELODY
# --------------------------------------------------------------------------

_VOWELS = "aeiouy"


def _syllables(line: str) -> list[str]:
    out: list[str] = []
    for word in re.findall(r"[A-Za-z']+", line):
        groups = re.findall(r"[^aeiouy]*[aeiouy]+(?:[^aeiouy]+$)?", word,
                            re.IGNORECASE)
        out.extend(groups or [word])
    return out


def _make_motif(rng: random.Random, bpb: float) -> list[tuple[float, float, int]]:
    """A 2-bar rhythmic/contour motif: (beat, duration, scale-degree step)."""
    rhythms = [
        [(0, 1), (1, 0.5), (1.5, 0.5), (2, 1.5), (4, 0.5), (4.5, 0.5),
         (5, 1), (6, 1.5)],
        [(0, 0.5), (0.5, 0.5), (1, 1), (2, 0.75), (2.75, 1.25), (4, 1),
         (5, 0.5), (5.5, 0.5), (6, 2)],
        [(0.5, 0.5), (1, 0.5), (1.5, 1.5), (3, 1), (4.5, 0.5), (5, 1),
         (6, 1.75)],
    ]
    rhythm = rng.choice(rhythms)
    contour: list[tuple[float, float, int]] = []
    step = 0
    for i, (b, d) in enumerate(rhythm):
        if b >= bpb * 2:
            continue
        if i == 0:
            move = 0
        elif i == len(rhythm) - 1:
            move = -step  # motif resolves home
        else:
            move = rng.choice([-2, -1, -1, 0, 1, 1, 2])
        step += move
        step = max(-4, min(6, step))
        contour.append((b, d, step))
    return contour


def generate_melody(project: SongProject, section: Section,
                    lyrics_lines: list[str] | None = None) -> Clip:
    bpb = project.beats_per_bar
    length = section.length_bars * bpb
    scale = scale_notes(project.key)
    chords = chord_progression(project.key, project.style.lower(),
                               section.length_bars)
    rng = _rng(project, section, "melody")
    motif = _make_motif(rng, bpb)

    syllables: list[str] = []
    for line in (lyrics_lines or []):
        syllables.extend(_syllables(line))

    notes: list[NoteEvent] = []
    syl_i = 0
    root_pc = chords[0][0]
    base_degree = scale.index(root_pc) if root_pc in scale else 0
    center = 67 if section.energy > 0.6 else 64

    two_bar_phrases = max(section.length_bars // 2, 1)
    for phrase in range(two_bar_phrases):
        phrase_base = phrase * 2 * bpb
        # vary the motif per phrase: transpose within scale; last phrase resolves
        transpose = [0, 0, 2, 0, 3, -1][phrase % 6]
        is_last = phrase == two_bar_phrases - 1
        for i, (b, d, step) in enumerate(motif):
            beat = phrase_base + b
            if beat >= length - 0.05:
                break
            # occasional rhythmic variation (skip or split a note)
            if not is_last and rng.random() < 0.12:
                continue
            degree = base_degree + step + transpose
            pc = scale[degree % 7]
            pitch = _nearest_octave(pc, center)
            # land phrase endings on a chord tone of the current bar
            bar_i = int(beat // bpb) % len(chords)
            if i == len(motif) - 1 or is_last and i >= len(motif) - 2:
                chord_pcs = chords[bar_i]
                pitch = _nearest_octave(
                    min(chord_pcs, key=lambda c: abs(_nearest_octave(c, pitch) - pitch)),
                    pitch)
            syl = ""
            if syllables:
                syl = syllables[syl_i % len(syllables)]
                syl_i += 1
            vel = 88 + int(22 * section.energy) + (6 if b % 1 == 0 else 0)
            _note(notes, pitch, beat, d * 0.92, vel, rng, length, 0.015,
                  syllable=syl)

    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length, note_events=notes)
