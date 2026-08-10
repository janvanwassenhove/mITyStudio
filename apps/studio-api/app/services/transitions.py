"""Section transitions — what makes a song feel joined up instead of a row
of separate blocks.

Generated songs sounded like eight-bar tiles butted together: every part
stopped dead on the section line and the next one started cold. Real
arrangements glue sections with three things, all of which this module adds
deterministically (no LLM, so it is repeatable and measurable):

- **tails** — the last sustained note of a section rings over the boundary
  instead of being cut, so the harmony hands over rather than restarts;
- **pickups** — a short lead-in (drum fill, bass walk-up) in the final beat
  before a section that lifts, so the new section is announced;
- **swells** — a crash/ride on the downbeat of a lifting section, and a
  rising velocity ramp through the pickup, so the lift lands.

Re-running is safe. Notes this module ADDS (pickups, swells) carry an
articulation marker and are replaced on the next run instead of stacking.
Tails are different: they are existing generator/user notes whose duration
we lengthen, so they carry no marker — the target length is deterministic,
which makes a second run a no-op. Marking them would have been worse than
useless: the cleanup would then delete real music (it did, once).
"""
from __future__ import annotations

import logging

from ..models.song import Clip, NoteEvent, Section, SongProject

log = logging.getLogger(__name__)

# articulation markers — our own additions, safe to remove and re-add
PICKUP = "pickup"
SWELL = "swell"
TAIL = "tail"
# only these are notes WE add, so only these may be removed on a re-run.
# A tail is an existing generator note we lengthened — never strip that, or
# the pass eats the music it was meant to join up.
_ADDED = {PICKUP, SWELL}
_OURS = {PICKUP, SWELL, TAIL}

# a section counts as "lifting" when its energy rises by at least this much
LIFT = 0.12
CRASH, RIDE, SNARE, TOM_HI, TOM_MID, TOM_LO, KICK = 49, 51, 38, 50, 47, 45, 36

# how far a tail may ring past the boundary (beats) — enough to bind the
# sections, short enough not to smear the new chord
_MAX_TAIL_BEATS = 1.75
_SUSTAINING = {"keys", "strings", "brass", "guitar", "synth", "bass", "fx"}


def _clip_for(track, section: Section) -> Clip | None:
    for c in track.clips:
        if c.section_id == section.id and c.clip_type == "midi":
            return c
    return None


def _strip_ours(project: SongProject) -> int:
    """Remove notes a previous run added, so this pass is idempotent."""
    removed = 0
    for t in project.tracks:
        for c in t.clips:
            before = len(c.note_events)
            c.note_events = [n for n in c.note_events
                             if n.articulation not in _ADDED]
            removed += before - len(c.note_events)
    return removed


def apply_transitions(project: SongProject) -> list[str]:
    """Glue the sections together. Returns human-readable log lines."""
    if len(project.sections) < 2:
        return []
    bpb = project.beats_per_bar
    _strip_ours(project)
    sections = sorted(project.sections, key=lambda s: s.start_bar)
    lines: list[str] = []
    tails = pickups = swells = 0

    for cur, nxt in zip(sections, sections[1:]):
        lift = nxt.energy - cur.energy

        for track in project.tracks:
            clip = _clip_for(track, cur)
            if clip is None or not clip.note_events:
                continue

            # --- tails: let the section's final sustained note ring over ---
            if track.track_type in _SUSTAINING:
                end = clip.duration_beats
                # the notes that finish closest to the boundary
                last_start = max(n.start_beat for n in clip.note_events)
                for n in clip.note_events:
                    if n.start_beat < last_start - 0.01 or n.articulation in _ADDED:
                        continue
                    over = min(_MAX_TAIL_BEATS, max(0.5, bpb * 0.4))
                    want = (end - n.start_beat) + over
                    # deterministic target length → running twice is a no-op
                    if want > n.duration_beats + 0.01:
                        n.duration_beats = round(want, 4)
                        tails += 1

            # --- pickups: announce a section that lifts ---
            if lift < LIFT:
                continue
            lead = clip.duration_beats - 1.0        # final beat of the section
            if lead <= 0:
                continue
            if track.track_type == "drums":
                # a four-stroke tom/snare run into the downbeat, rising
                for i, note in enumerate((SNARE, TOM_HI, TOM_MID, TOM_LO)):
                    clip.note_events.append(NoteEvent(
                        midi_note=note, start_beat=round(lead + i * 0.25, 4),
                        duration_beats=0.22, velocity=min(127, 84 + i * 12),
                        articulation=PICKUP))
                pickups += 1
            elif track.track_type == "bass":
                # a walk-up: two eighths climbing to the next section's root
                nxt_clip = _clip_for(track, nxt)
                target = (min(nxt_clip.note_events,
                              key=lambda n: n.start_beat).midi_note
                          if nxt_clip and nxt_clip.note_events else None)
                if target is not None:
                    for i, step in enumerate((-3, -1)):
                        clip.note_events.append(NoteEvent(
                            midi_note=max(0, min(127, target + step)),
                            start_beat=round(lead + i * 0.5, 4),
                            duration_beats=0.45, velocity=96 + i * 8,
                            articulation=PICKUP))
                    pickups += 1

        # --- swell: crash the downbeat of the lifting section ---
        if lift >= LIFT:
            for track in project.tracks:
                if track.track_type != "drums":
                    continue
                nxt_clip = _clip_for(track, nxt)
                if nxt_clip is None:
                    continue
                has_crash = any(n.midi_note == CRASH and n.start_beat < 0.1
                                for n in nxt_clip.note_events)
                if not has_crash:
                    nxt_clip.note_events.append(NoteEvent(
                        midi_note=CRASH, start_beat=0.0, duration_beats=1.5,
                        velocity=min(127, 100 + int(30 * lift)),
                        articulation=SWELL))
                    swells += 1

    if tails or pickups or swells:
        lines.append(f"transitions: {tails} notes ring over section lines, "
                     f"{pickups} pickups into lifts, {swells} crash swells")
    return lines


def transition_coverage(project: SongProject) -> float:
    """Fraction of section boundaries that are glued (tail, pickup or swell).
    This is what the quality score measures — a song of hard-cut blocks
    scores 0, a properly joined arrangement approaches 1."""
    sections = sorted(project.sections, key=lambda s: s.start_bar)
    if len(sections) < 2:
        return 1.0
    glued = 0
    for cur, nxt in zip(sections, sections[1:]):
        cur_end = (cur.start_bar + cur.length_bars) * project.beats_per_bar
        joined = False
        for t in project.tracks:
            for c in t.clips:
                if c.section_id == cur.id:
                    # a note ringing past this section's end
                    if any(c.start_beat + n.start_beat + n.duration_beats
                           > cur_end + 0.05 for n in c.note_events):
                        joined = True
                    if any(n.articulation in _OURS for n in c.note_events):
                        joined = True
                elif c.section_id == nxt.id:
                    if any(n.articulation == SWELL for n in c.note_events):
                        joined = True
            if joined:
                break
        glued += 1 if joined else 0
    return round(glued / (len(sections) - 1), 3)
