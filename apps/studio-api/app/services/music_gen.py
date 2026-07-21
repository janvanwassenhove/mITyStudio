"""Algorithmic music generators — production-quality pass.

What makes these sound like parts instead of patterns:
- a real genre engine (services/genres.py): token-matched style families
  with per-genre groove templates, swing, chord colour and progressions —
  bossa, funk, reggae, trap, country, synthwave... each audibly distinct
- tempo awareness: hat subdivision, fill density and pattern density derive
  from project.bpm, not just from section energy
- humanized timing (±8 ms swing-aware jitter) and velocity contours
- chord voicings with inversions chosen by voice-leading distance
- guitar strums, power chords, reggae skanks, funk stabs, pads
- drum grooves with accents, ghost notes, fills and section crashes
- bass lines per genre (driving 8ths, walking jazz, bossa root-fifth,
  syncopated funk 16ths, one-drop reggae, long 808s)
- melodies built from a repeated 2-bar motif with variations, phrase
  arcs that resolve to chord tones, and breaths between phrases

Seeded randomness keeps every (project, section) render reproducible.
"""
from __future__ import annotations

import random
import re

from ..models.song import Clip, NoteEvent, Section, SongProject
from .genres import GenreProfile, genre_profile, profile_for

_NOTE_OFFSETS = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
                 "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
                 "A#": 10, "Bb": 10, "B": 11}

MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

# GM drum notes
KICK, SNARE, RIM, HAT_CLOSED, HAT_PEDAL, HAT_OPEN = 36, 38, 37, 42, 44, 46
CRASH, RIDE, TOM_LO, TOM_MID, TOM_HI = 49, 51, 45, 47, 50


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
    """One chord (list of pitch classes, root first) per bar, using the
    genre profile's progression and chord colour."""
    root, minor = parse_key(key)
    scale = MINOR_SCALE if minor else MAJOR_SCALE
    prof = profile_for(style)

    def triad(degree: int, seventh: bool = False) -> list[int]:
        pcs = [(root + scale[(degree + i) % 7]) % 12 for i in (0, 2, 4)]
        if seventh:
            pcs.append((root + scale[(degree + 6) % 7]) % 12)
        return pcs

    degrees = prof.degrees_minor if minor else prof.degrees_major
    return [triad(degrees[i % len(degrees)], prof.seventh)
            for i in range(bars)]


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

def _hat_subdivision(prof: GenreProfile, bpm: float, energy: float) -> float:
    """Hat step in beats — tempo-aware: fast songs get 8ths (16ths would
    blur), slow songs earn 16ths, mid tempo follows section energy."""
    if prof.groove == "funk":
        return 0.5 if bpm >= 140 else 0.25
    if prof.groove in ("halftime", "sparse"):
        return 0.5
    if bpm >= 150:
        return 0.5
    if bpm <= 88:
        return 0.25
    return 0.25 if energy > 0.75 else 0.5


def generate_drums(project: SongProject, section: Section) -> Clip:
    bpb = project.beats_per_bar
    length = section.length_bars * bpb
    prof = genre_profile(project)
    groove = prof.groove
    bpm = float(project.bpm or 110)
    energy = section.energy
    rng = _rng(project, section, "drums")
    notes: list[NoteEvent] = []

    def hit(n: int, b: float, v: int, d: float = 0.2, j: float = 0.012) -> None:
        _note(notes, n, b, d, v, rng, length, j)

    def sw(b: float) -> float:
        """Swing: delay offbeat 8ths by the profile's swing amount."""
        return b + (prof.swing if abs(b % 1 - 0.5) < 0.01 else 0.0)

    hat_step = _hat_subdivision(prof, bpm, energy)
    # tempo-aware fill density: very fast songs fill half as often
    fill_every = 8 if bpm >= 168 else 4
    quiet = groove in ("sparse", "bossa", "reggae")

    for bar in range(section.length_bars):
        base = bar * bpb
        is_fill_bar = (bar % fill_every == fill_every - 1) \
            and energy > (0.6 if quiet else 0.35) and section.length_bars >= 4
        fill_start = bpb - 1.0 if is_fill_bar else bpb + 1  # last beat of fill bars

        # kick/snare skeleton per groove template
        if groove == "rock":
            for b in range(int(bpb)):
                hit(KICK, base + b, 112)
            hit(SNARE, base + 1, 116)
            hit(SNARE, base + 3, 118)
            if energy > 0.6 and rng.random() < 0.4:
                hit(KICK, base + 2.5, 96)   # push into beat 3
        elif groove == "four_floor":
            for b in range(int(bpb)):
                hit(KICK, base + b, 122, j=0.004)
                hit(HAT_OPEN, base + b + 0.5, 60 + int(30 * energy), 0.3)
            hit(SNARE, base + 1, 100)
            hit(SNARE, base + 3, 102)
        elif groove == "swing":
            # ride swing pattern, cross-stick on 2 & 4, feathered kick
            for b in range(int(bpb)):
                hit(RIDE, base + b, 88)
                hit(RIDE, base + b + 0.5 + prof.swing, 66)
            hit(RIM, base + 1, 78)
            hit(RIM, base + 3, 80)
            hit(HAT_PEDAL, base + 1, 60)
            hit(HAT_PEDAL, base + 3, 60)
            if rng.random() < 0.3:
                hit(KICK, base + rng.choice([0.0, 2.0]), 55)
        elif groove == "bossa":
            # surdo-style kick: 1 and the "and of 2", repeated on 3
            hit(KICK, base + 0, 98, j=0.006)
            hit(KICK, base + 1.5, 88, j=0.006)
            hit(KICK, base + 2, 96, j=0.006)
            hit(KICK, base + 3.5, 86, j=0.006)
            # rim clave (3-2 son) across two bars
            clave = (0.0, 1.5, 3.0) if bar % 2 == 0 else (1.0, 2.0)
            for c in clave:
                hit(RIM, base + c, 74, 0.15)
        elif groove == "funk":
            hit(KICK, base + 0, 116)
            if rng.random() < 0.6:
                hit(KICK, base + 0.75, 92)
            hit(KICK, base + 2.5, 104)
            if energy > 0.5 and rng.random() < 0.5:
                hit(KICK, base + 3.25, 90)
            hit(SNARE, base + 1, 112)
            hit(SNARE, base + 3, 114)
            for g in (1.75, 2.25, 3.75):        # ghosted snare 16ths
                if rng.random() < 0.45:
                    hit(SNARE, base + g, 34, 0.08)
        elif groove == "reggae":
            # one drop: kick + cross-stick together on beat 3, bar 1 empty
            hit(KICK, base + 2, 108)
            hit(RIM, base + 2, 96)
            if energy > 0.5 and rng.random() < 0.3:
                hit(KICK, base + 0, 68)         # occasional pickup
        elif groove == "halftime":
            # trap/hip-hop: snare on 3 only; syncopated sparse kicks
            hit(KICK, base + 0, 118)
            if rng.random() < 0.55:
                hit(KICK, base + rng.choice([0.75, 1.25, 1.75]), 96)
            hit(SNARE, base + 2, 116)
            if energy > 0.6 and rng.random() < 0.35:
                # trap hat roll into the next bar
                for i in range(4):
                    hit(HAT_CLOSED, base + 3.5 + i * 0.125, 58 + i * 8, 0.06)
        elif groove == "train":
            # country train beat: kick 1&3, snare 2&4 with 8th drive
            hit(KICK, base + 0, 108)
            hit(KICK, base + 2, 104)
            hit(SNARE, base + 1, 104)
            hit(SNARE, base + 3, 106)
            if energy > 0.5:
                hit(SNARE, base + 1.5, 52, 0.1)
                hit(SNARE, base + 3.5, 52, 0.1)
        elif groove == "sparse":
            # ballad/ambient: minimal motion, let the song breathe
            hit(KICK, base + 0, 92)
            if energy > 0.3:
                hit(RIM, base + 2, 70)
            if energy > 0.55:
                hit(KICK, base + 2.5, 74)
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

        # hats — grooves with their own top pattern skip these
        if groove in ("rock", "pop", "funk", "train", "halftime"):
            b = 0.0
            while b < bpb - 0.01:
                on_beat = abs(b - round(b)) < 0.01
                vel = (78 if on_beat else 56) + int(22 * energy)
                if base + b < base + fill_start:
                    hit(HAT_CLOSED, base + sw(b), vel, 0.12)
                b += hat_step
            if energy > 0.55 and groove != "halftime" and rng.random() < 0.5:
                hit(HAT_OPEN, base + bpb - 0.5, 74, 0.4)  # open-hat push
        elif groove == "bossa":
            b = 0.0
            while b < bpb - 0.01:   # light shaker 8ths
                on_beat = abs(b - round(b)) < 0.01
                hit(HAT_CLOSED, base + b, (58 if on_beat else 44)
                    + int(14 * energy), 0.1, 0.02)
                b += 0.5
        elif groove == "reggae":
            for b in range(int(bpb)):   # offbeat skank hats
                hit(HAT_CLOSED, base + b + 0.5, 72 + int(12 * energy), 0.12)
        elif groove == "sparse" and energy > 0.4:
            for b in range(int(bpb)):   # soft quarter hats
                hit(HAT_CLOSED, base + b, 46 + int(16 * energy), 0.1)

        # fills: snare/tom run over the last beat of every fill bar
        if is_fill_bar:
            if quiet:   # gentle two-note fill for laid-back grooves
                hit(SNARE, base + fill_start, 72, 0.2)
                hit(TOM_LO, base + fill_start + 0.5, 78, 0.3)
            else:
                fill_notes = rng.choice([
                    [SNARE, SNARE, TOM_HI, TOM_LO],
                    [SNARE, TOM_HI, TOM_MID, TOM_LO],
                    [SNARE, SNARE, SNARE, SNARE],
                    [TOM_HI, TOM_HI, TOM_MID, TOM_LO],
                ])
                for i, n in enumerate(fill_notes):
                    hit(n, base + fill_start + i * 0.25, 88 + i * 8, 0.2)

        # crash on section start and after every fill (laid-back grooves
        # only crash when the section really pushes)
        crash_ok = not quiet or energy > 0.6
        if crash_ok and (bar == 0
                         or (bar % fill_every == 0 and bar > 0 and energy > 0.5)):
            hit(CRASH, base, 104 if not quiet else 88, 1.2)

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
    prof = genre_profile(project)
    energy = section.energy
    chords = chord_progression(project.key, project.style.lower(),
                               section.length_bars)
    rng = _rng(project, section, "bass")
    notes: list[NoteEvent] = []

    for bar, chord in enumerate(chords):
        base = bar * bpb
        root = _nearest_octave(chord[0], 38)          # around D2
        fifth = _nearest_octave(chord[1 % len(chord)], root + 5)
        next_chord = chords[(bar + 1) % len(chords)]
        next_root = _nearest_octave(next_chord[0], root)

        if prof.bass_style == "drive":
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
        elif prof.bass_style == "walk":
            # walking quarter notes: root, chord tone, scale walk, approach
            walk = [root,
                    _nearest_octave(chord[2 % len(chord)], root),
                    fifth,
                    next_root + rng.choice([-1, 1, -2, 2])]
            for i, pitch in enumerate(walk[:int(bpb)]):
                _note(notes, pitch, base + i, 0.92, 92 + rng.randint(-4, 8),
                      rng, length, 0.015)
        elif prof.bass_style == "octave":
            # off-beat octave bounce
            for b in range(int(bpb)):
                _note(notes, root, base + b, 0.4, 106, rng, length, 0.005)
                _note(notes, root + 12, base + b + 0.5, 0.35, 92, rng, length, 0.005)
        elif prof.bass_style == "bossa":
            # classic bossa: root on 1 and 3, fifth on the "and of 2"/"of 4"
            _note(notes, root, base + 0, 1.35, 100, rng, length, 0.01)
            _note(notes, fifth, base + 1.5, 0.45, 88, rng, length, 0.01)
            _note(notes, root, base + 2, 1.35, 98, rng, length, 0.01)
            if next_root != root and rng.random() < 0.5:
                _note(notes, next_root + rng.choice([-2, -1, 1, 2]),
                      base + 3.5, 0.45, 86, rng, length, 0.01)
            else:
                _note(notes, fifth, base + 3.5, 0.45, 86, rng, length, 0.01)
        elif prof.bass_style == "funk":
            # syncopated 16ths with octave pops and dead-note feel
            _note(notes, root, base + 0, 0.3, 114, rng, length, 0.006)
            for off in (0.75, 1.5, 2.25, 2.75, 3.5):
                if rng.random() < 0.35 + 0.4 * energy:
                    pitch = root + 12 if rng.random() < 0.3 else root
                    _note(notes, pitch, base + off, 0.2, 96, rng, length, 0.006)
            _note(notes, fifth, base + 2, 0.3, 102, rng, length, 0.006)
            if next_root != root:
                _note(notes, next_root + rng.choice([-1, 1]),
                      base + bpb - 0.25, 0.2, 92, rng, length, 0.006)
        elif prof.bass_style == "reggae":
            # spacious one-drop bass: often rests on 1, melodic and calm
            if rng.random() < 0.55:
                _note(notes, root, base + 0.5, 0.9, 96, rng, length, 0.012)
            else:
                _note(notes, root, base + 0, 1.3, 96, rng, length, 0.012)
            _note(notes, _nearest_octave(chord[2 % len(chord)], root),
                  base + 2, 0.9, 92, rng, length, 0.012)
            _note(notes, root, base + 3, 0.7, 90, rng, length, 0.012)
        elif prof.bass_style == "half":
            # long 808-style roots; occasional slide into the next bar
            _note(notes, root, base + 0, 2.6, 106, rng, length, 0.006)
            if energy > 0.6 and rng.random() < 0.4:
                _note(notes, root, base + 2.75, 0.4, 92, rng, length, 0.006)
            if next_root != root and rng.random() < 0.5:
                _note(notes, next_root + (1 if next_root < root else -1),
                      base + 3.5, 0.45, 88, rng, length, 0.006)
        elif prof.bass_style == "sparse":
            # ballad: whole-note roots, fifth colour at higher energy
            _note(notes, root, base + 0, bpb * 0.95, 88, rng, length, 0.015)
            if energy > 0.5:
                _note(notes, fifth, base + 2, bpb * 0.45, 78, rng, length, 0.015)
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
    prof = genre_profile(project)
    energy = section.energy
    chords = chord_progression(project.key, project.style.lower(),
                               section.length_bars)
    rng = _rng(project, section, "chords")
    notes: list[NoteEvent] = []
    prev_voicing: list[int] | None = None

    for bar, chord in enumerate(chords):
        base = bar * bpb
        if prof.chord_style == "power":
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
        elif prof.chord_style == "strum":
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
        elif prof.chord_style == "skank":
            # reggae skank: short chord stabs on every offbeat
            voiced = _voice_chord(chord, prev_voicing, center=64)
            prev_voicing = voiced
            for b in range(int(bpb)):
                for j, n in enumerate(voiced):
                    _note(notes, n, base + b + 0.5 + j * 0.006, 0.22,
                          94 - j * 3 + int(8 * energy), rng, length, 0.006)
        elif prof.chord_style == "stab":
            # funk stabs: tight 16th hits leaving space for the rhythm section
            voiced = _voice_chord(chord, prev_voicing, center=64)
            prev_voicing = voiced
            stabs = [0.0, 1.75, 2.5]
            if energy > 0.6 and rng.random() < 0.5:
                stabs.append(3.25)
            for b in stabs:
                if b >= bpb:
                    continue
                for j, n in enumerate(voiced):
                    _note(notes, n, base + b + j * 0.005, 0.18,
                          102 - j * 3, rng, length, 0.005)
        elif prof.chord_style == "comp":
            # bossa comp: syncopated short chords (guitar-style comping)
            voiced = _voice_chord(chord, prev_voicing, center=60)
            prev_voicing = voiced
            pattern = [(0.0, 0.9), (1.5, 0.4), (2.0, 0.9), (3.5, 0.4)]
            for b, dur in pattern:
                if b >= bpb:
                    continue
                for j, n in enumerate(voiced):
                    _note(notes, n, base + b + j * 0.008, dur,
                          84 - j * 3 + int(10 * energy), rng, length, 0.008)
        elif prof.chord_style == "pad":
            # sustained pad: one soft voicing per bar, slow-attack friendly
            voiced = _voice_chord(chord, prev_voicing, center=62)
            prev_voicing = voiced
            for j, n in enumerate(voiced):
                _note(notes, n, base + j * 0.01, bpb * 0.98,
                      68 - j * 2 + int(18 * energy), rng, length, 0.01)
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

from .lyric_text import line_syllables as _syllables  # noqa: E402


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


def generate_vocal_melody(project: SongProject, section: Section,
                          lyrics_lines: list[str],
                          rap: bool = False,
                          harmony: bool = False,
                          pace: float = 1.0) -> Clip:
    """Singable vocal melody: exactly ONE note per syllable, phrased per
    lyric line with breaths between lines, contour arcs that resolve to
    chord tones. Rap mode keeps a tight monotone-ish rhythm instead.

    The 1:1 syllable↔note mapping is what lets the clone-singing engine
    place every word exactly on its note (fluent, on-beat vocals).
    """
    bpb = project.beats_per_bar
    length = section.length_bars * bpb
    scale = scale_notes(project.key)
    chords = chord_progression(project.key, project.style.lower(),
                               section.length_bars)
    rng = _rng(project, section, "vocal")
    notes: list[NoteEvent] = []

    lines = [(l, _syllables(l)) for l in lyrics_lines if _syllables(l)]
    if not lines:
        return Clip(section_id=section.id, clip_type="midi",
                    start_beat=section.start_bar * bpb,
                    duration_beats=length, note_events=[])

    slot = length / len(lines)          # beats available per line
    center = 65 if section.energy > 0.6 else 62

    for li, (line, syls) in enumerate(lines):
        line_start = li * slot
        # rest at the end of every line — shrinks when the section is packed
        # so crowded lyrics spend their time on words, not pauses
        crowded = slot / max(len(syls), 1) < 0.5
        breath = min(1.0, slot * (0.08 if crowded else 0.18))
        usable = slot - breath
        n = len(syls)
        # rhythm: mostly even syllables, stretched last syllable of the line.
        # `pace` stretches the per-syllable time (slow singing on request);
        # the floor keeps crowded sections from machine-gunning syllables —
        # when even the floor doesn't fit, syllables get the room there is.
        pace = max(pace, 0.5)
        base_dur = max(min(usable / n, 1.0 * pace),
                       min(0.35 * pace, usable / n if n else 0.35))
        durs = [base_dur] * n
        durs[-1] = min(base_dur * 2.2, usable - base_dur * (n - 1) + base_dur)
        if not rap:
            for i in range(0, n - 1):
                if rng.random() < 0.2:  # occasional pushed short pair
                    durs[i] *= 0.75
        total_needed = sum(durs)
        if total_needed > usable and total_needed > 0:
            scalef = usable / total_needed
            durs = [d * scalef for d in durs]

        bar0 = int(line_start // bpb) % len(chords)
        chord = chords[bar0]
        if rap:
            # rap: 1-3 pitches around the root, rhythm carries everything
            root = _nearest_octave(chord[0], center)
            beat = line_start
            for i, syl in enumerate(syls):
                pitch = root + rng.choice([0, 0, 0, 2, -1]) if i % 4 else root
                _note(notes, pitch, beat, durs[i] * 0.92,
                      104 if i % 2 == 0 else 92, rng, length, 0.01,
                      syllable=syl)
                beat += durs[i]
            continue

        # sung contour: arc up to a mid-line peak, resolve to a chord tone
        start_pitch = _nearest_octave(rng.choice(chord), center)
        peak_i = max(n // 2, 1)
        degree = scale.index(start_pitch % 12) if start_pitch % 12 in scale else 0
        beat = line_start
        pitch = start_pitch
        for i, syl in enumerate(syls):
            if i == 0:
                pitch = start_pitch
            elif i == n - 1:
                bar_i = int(beat // bpb) % len(chords)
                pitch = _nearest_octave(
                    min(chords[bar_i], key=lambda c: abs(_nearest_octave(c, pitch) - pitch)),
                    pitch)  # land on a chord tone
            else:
                move = 1 if i < peak_i else -1
                if rng.random() < 0.3:
                    move = rng.choice([-1, 0, 1])
                degree = max(-3, min(9, degree + move))
                pitch = _nearest_octave(scale[degree % 7], center + (4 if i < peak_i else 0))
            _note(notes, pitch, beat, durs[i] * 0.95,
                  92 + int(20 * section.energy) + (6 if i == 0 else 0),
                  rng, length, 0.012, syllable=syl)
            beat += durs[i]

    if harmony and not rap:
        # backing vocals sing a diatonic third above the lead instead of a
        # unison double (identical lines from two voices sound phasey)
        for n in notes:
            pc = n.midi_note % 12
            k = (scale.index(pc) if pc in scale
                 else min(range(7), key=lambda j: min((scale[j] - pc) % 12,
                                                      (pc - scale[j]) % 12)))
            n.midi_note = min(127, n.midi_note + (scale[(k + 2) % 7] - pc) % 12)
            n.velocity = max(20, n.velocity - 14)   # sit behind the lead

    return Clip(section_id=section.id, clip_type="midi",
                start_beat=section.start_bar * bpb,
                duration_beats=length, note_events=notes)


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
