"""ScoreImporter: turn score files into song material.

MIDI (.mid/.midi) is fully implemented via mido. MusicXML, Guitar Pro,
MuseScore and PDF have documented placeholder adapters that return a clear
"not implemented" result instead of failing silently.
"""
from __future__ import annotations

import logging
from pathlib import Path

import mido
from pydantic import BaseModel, Field

from ..models.asset import Asset
from ..models.song import (Clip, NoteEvent, Section, SongProject, Track,
                           TrackType, midi_to_pitch_name)

log = logging.getLogger(__name__)


class DetectedTrack(BaseModel):
    name: str
    suggested_track_type: str
    program: int = 0
    is_drum: bool = False
    note_count: int = 0
    notes: list[dict] = Field(default_factory=list)  # midi_note/start_beat/duration_beats/velocity


class ScoreImportResult(BaseModel):
    source_asset_id: str
    format: str
    supported: bool = True
    detected_tracks: list[DetectedTrack] = Field(default_factory=list)
    detected_tempo: float | None = None
    detected_key: str | None = None
    time_signature: str | None = None
    sections: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# General MIDI program -> studio track type (coarse mapping)
def _program_to_track_type(program: int, is_drum: bool) -> TrackType:
    if is_drum:
        return "drums"
    if program <= 7:
        return "keys"
    if program <= 15:
        return "keys"       # chromatic percussion ~ keys
    if program <= 23:
        return "keys"       # organ
    if program <= 31:
        return "guitar"
    if program <= 39:
        return "bass"
    if program <= 47:
        return "strings"
    if program <= 55:
        return "strings"    # ensemble
    if program <= 63:
        return "brass"
    if program <= 79:
        return "brass"      # reed/pipe
    if program <= 95:
        return "synth"
    return "fx"


def import_midi(path: Path, asset_id: str) -> ScoreImportResult:
    result = ScoreImportResult(source_asset_id=asset_id, format="midi")
    try:
        mid = mido.MidiFile(str(path))
    except Exception as e:
        result.supported = False
        result.warnings.append(f"cannot parse MIDI file: {e}")
        return result

    ticks_per_beat = mid.ticks_per_beat or 480
    tempo_us = 500000  # default 120 bpm

    for track in mid.tracks:
        abs_ticks = 0
        active: dict[tuple[int, int], tuple[int, int]] = {}  # (ch, note) -> (start, vel)
        notes: list[dict] = []
        name = ""
        program = 0
        channels: set[int] = set()
        for msg in track:
            abs_ticks += msg.time
            if msg.type == "set_tempo":
                tempo_us = msg.tempo
            elif msg.type == "time_signature":
                result.time_signature = f"{msg.numerator}/{msg.denominator}"
            elif msg.type == "key_signature":
                result.detected_key = msg.key
            elif msg.type == "track_name":
                name = msg.name.strip()
            elif msg.type == "program_change":
                program = msg.program
                channels.add(msg.channel)
            elif msg.type == "note_on" and msg.velocity > 0:
                active[(msg.channel, msg.note)] = (abs_ticks, msg.velocity)
                channels.add(msg.channel)
            elif msg.type in ("note_off", "note_on"):
                key = (msg.channel, msg.note)
                if key in active:
                    start, vel = active.pop(key)
                    notes.append({
                        "midi_note": msg.note,
                        "start_beat": start / ticks_per_beat,
                        "duration_beats": max((abs_ticks - start) / ticks_per_beat, 1 / 32),
                        "velocity": vel,
                    })
        if not notes:
            continue
        is_drum = 9 in channels
        notes.sort(key=lambda n: n["start_beat"])
        result.detected_tracks.append(DetectedTrack(
            name=name or f"Track {len(result.detected_tracks) + 1}",
            suggested_track_type=_program_to_track_type(program, is_drum),
            program=program, is_drum=is_drum, note_count=len(notes),
            notes=notes,
        ))

    result.detected_tempo = round(60_000_000 / tempo_us, 2)
    if not result.detected_tracks:
        result.warnings.append("no note data found in MIDI file")
    return result


_PLACEHOLDER_FORMATS = {".mscz": "musescore", ".pdf": "pdf"}


def import_score(asset: Asset) -> ScoreImportResult:
    path = Path(asset.original_path)
    ext = asset.extension
    if ext in (".mid", ".midi"):
        return import_midi(path, asset.id)
    if ext in (".musicxml", ".xml", ".mxl"):
        from .musicxml_import import import_musicxml
        return import_musicxml(path, asset.id)
    if ext in (".gp3", ".gp4", ".gp5", ".gpx"):
        from .guitarpro_import import import_guitarpro
        return import_guitarpro(path, asset.id)
    fmt = _PLACEHOLDER_FORMATS.get(ext, "unknown")
    msg = {
        "musescore": "MuseScore .mscz is not parsed directly — export to MIDI "
                     "or MusicXML from MuseScore instead.",
        "pdf": "PDF scores are reference-only; no reliable parsing is implemented.",
        "unknown": f"unsupported score format {ext!r}",
    }[fmt]
    return ScoreImportResult(source_asset_id=asset.id, format=fmt,
                             supported=False, warnings=[msg])


def project_from_import(result: ScoreImportResult, title: str,
                        style: str = "") -> SongProject:
    """Create a SongProject from an import result."""
    if not result.detected_tracks:
        raise ValueError("import result contains no tracks")
    bpm = result.detected_tempo or 120.0
    ts = result.time_signature or "4/4"
    tracks: list[Track] = []
    max_beat = 0.0
    for dt in result.detected_tracks:
        notes = [NoteEvent(
            midi_note=n["midi_note"],
            pitch=midi_to_pitch_name(n["midi_note"]),
            start_beat=n["start_beat"],
            duration_beats=n["duration_beats"],
            velocity=max(1, min(127, n["velocity"])),
        ) for n in dt.notes]
        end = max((n.start_beat + n.duration_beats for n in notes), default=0.0)
        max_beat = max(max_beat, end)
        clip = Clip(clip_type="midi", start_beat=0.0,
                    duration_beats=max(end, 1.0), note_events=notes)
        tracks.append(Track(
            name=dt.name, track_type=dt.suggested_track_type,  # type: ignore[arg-type]
            clips=[clip],
        ))
        tracks[-1].instrument_config.program = dt.program
        tracks[-1].instrument_config.is_drum_kit = dt.is_drum

    project = SongProject(title=title, style=style, bpm=bpm,
                          time_signature=ts,
                          key=result.detected_key or "C major",
                          source_assets=[result.source_asset_id])
    num = int(ts.split("/")[0])
    den = int(ts.split("/")[1])
    beats_per_bar = num * 4.0 / den
    total_bars = max(int(max_beat // beats_per_bar) + (1 if max_beat % beats_per_bar else 0), 1)
    project.sections = [Section(name="Imported", start_bar=0, length_bars=total_bars,
                                description=f"imported from asset {result.source_asset_id}")]
    project.tracks = tracks
    return project
