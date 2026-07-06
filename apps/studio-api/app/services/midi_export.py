"""MidiExporter: SongProject instrument tracks → standard MIDI files.

One MIDI file per instrument/vocal track plus an optional full-song file.
Files are written to midi/{project_id}/ and referenced in the project.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import mido

from ..config import get_config
from ..models.song import (INSTRUMENT_TRACK_TYPES, SongProject, Track,
                           VOCAL_TRACK_TYPES)

log = logging.getLogger(__name__)

TICKS_PER_BEAT = 480


class MidiExportError(Exception):
    pass


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name).strip("_") or "track"


def _track_to_midi(project: SongProject, track: Track,
                   channel: int = 0) -> mido.MidiTrack:
    mtrack = mido.MidiTrack()
    mtrack.append(mido.MetaMessage("track_name", name=track.name, time=0))
    if track.instrument_config.is_drum_kit:
        channel = 9
    if not track.instrument_config.is_drum_kit:
        mtrack.append(mido.Message(
            "program_change", program=track.instrument_config.program,
            channel=channel, time=0))

    events: list[tuple[int, int, mido.Message]] = []  # (tick, order, msg)
    for clip in track.clips:
        if clip.clip_type == "sample":
            continue
        for n in clip.note_events:
            if not 0 <= n.midi_note <= 127:
                raise MidiExportError(
                    f"track {track.name!r}: note {n.midi_note} out of MIDI range")
            start = clip.start_beat + n.start_beat
            if start < 0 or n.duration_beats <= 0:
                raise MidiExportError(
                    f"track {track.name!r}: invalid note timing "
                    f"(start {start}, duration {n.duration_beats})")
            on_tick = round(start * TICKS_PER_BEAT)
            off_tick = round((start + n.duration_beats) * TICKS_PER_BEAT)
            if off_tick <= on_tick:
                off_tick = on_tick + 1
            events.append((on_tick, 1, mido.Message(
                "note_on", note=n.midi_note, velocity=n.velocity,
                channel=channel, time=0)))
            events.append((off_tick, 0, mido.Message(
                "note_off", note=n.midi_note, velocity=0,
                channel=channel, time=0)))

    events.sort(key=lambda e: (e[0], e[1]))
    last_tick = 0
    for tick, _, msg in events:
        msg.time = tick - last_tick
        mtrack.append(msg)
        last_tick = tick
    mtrack.append(mido.MetaMessage("end_of_track", time=0))
    return mtrack


def _tempo_track(project: SongProject) -> mido.MidiTrack:
    t = mido.MidiTrack()
    num, den = (int(x) for x in project.time_signature.split("/"))
    t.append(mido.MetaMessage("time_signature", numerator=num,
                              denominator=den, time=0))
    t.append(mido.MetaMessage("set_tempo",
                              tempo=mido.bpm2tempo(project.bpm), time=0))
    t.append(mido.MetaMessage("end_of_track", time=0))
    return t


def exportable_tracks(project: SongProject) -> list[Track]:
    return [t for t in project.tracks
            if t.track_type in INSTRUMENT_TRACK_TYPES | VOCAL_TRACK_TYPES
            and any(c.clip_type != "sample" and c.note_events for c in t.clips)]


def export_project_midi(project: SongProject,
                        include_full_song: bool = True) -> dict[str, str]:
    """Returns {track_id or '__full__': relative midi path}."""
    cfg = get_config()
    out_dir = cfg.midi_dir / project.id
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}

    tracks = exportable_tracks(project)
    for track in tracks:
        mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
        mid.tracks.append(_tempo_track(project))
        mid.tracks.append(_track_to_midi(project, track))
        path = out_dir / f"{_safe_name(track.name)}_{track.id[:8]}.mid"
        mid.save(str(path))
        outputs[track.id] = path.relative_to(cfg.root).as_posix()

    if include_full_song and tracks:
        mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
        mid.tracks.append(_tempo_track(project))
        ch = 0
        for track in tracks:
            if ch == 9:
                ch += 1  # channel 10 (index 9) is reserved for drums
            mid.tracks.append(_track_to_midi(project, track, channel=ch))
            if not track.instrument_config.is_drum_kit:
                ch = (ch + 1) % 16
        path = out_dir / f"{_safe_name(project.title)}_full.mid"
        mid.save(str(path))
        outputs["__full__"] = path.relative_to(cfg.root).as_posix()

    project.midi_files = outputs
    return outputs
