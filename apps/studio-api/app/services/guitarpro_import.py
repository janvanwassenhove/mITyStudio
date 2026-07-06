"""Guitar Pro importer (.gp3/.gp4/.gp5) via PyGuitarPro.

Converts tab tracks to note events: string+fret → MIDI pitch using each
track's tuning, beat durations → beats, percussion tracks → drums.
(.gpx — GP6 — is not supported by PyGuitarPro and stays a placeholder.)
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def import_guitarpro(path: Path, asset_id: str):
    from .score_import import DetectedTrack, ScoreImportResult, _program_to_track_type

    result = ScoreImportResult(source_asset_id=asset_id, format="guitarpro")
    if path.suffix.lower() == ".gpx":
        result.supported = False
        result.warnings.append(
            ".gpx (Guitar Pro 6) is not supported — export as .gp5 from "
            "Guitar Pro or TuxGuitar")
        return result
    try:
        import guitarpro
        song = guitarpro.parse(str(path))
    except Exception as e:
        result.supported = False
        result.warnings.append(f"cannot parse Guitar Pro file: {e}")
        return result
    return convert_song(song, result)


def convert_song(song, result):
    """Convert a parsed PyGuitarPro Song into a ScoreImportResult
    (separated from file I/O for testability)."""
    from .score_import import DetectedTrack, _program_to_track_type

    result.detected_tempo = float(song.tempo)
    if song.key is not None:
        result.detected_key = str(getattr(song.key, "name", "") or "").replace(
            "Major", "major").replace("Minor", "minor") or None

    for gp_track in song.tracks:
        if getattr(gp_track, "isMute", False):
            continue
        tuning = [s.value for s in gp_track.strings]  # string 1..n MIDI values
        notes: list[dict] = []
        position = 0.0  # beats
        ts_set = False
        for measure in gp_track.measures:
            header = measure.header
            num = header.timeSignature.numerator
            den = header.timeSignature.denominator.value
            if not ts_set:
                result.time_signature = f"{num}/{den}"
                ts_set = True
            measure_beats = num * 4.0 / den
            voice = measure.voices[0] if measure.voices else None
            beat_pos = position
            if voice is not None:
                for beat in voice.beats:
                    # quarter note = 1 beat; duration.value: 1=whole ... 64
                    dur = 4.0 / beat.duration.value
                    if beat.duration.isDotted:
                        dur *= 1.5
                    tuplet = beat.duration.tuplet
                    if tuplet and tuplet.enters and tuplet.times:
                        dur *= tuplet.times / tuplet.enters
                    for note in beat.notes:
                        if note.type.name not in ("normal", "tie"):
                            continue
                        if gp_track.isPercussionTrack:
                            midi = note.value  # fret number = GM drum note
                        else:
                            idx = note.string - 1
                            if not 0 <= idx < len(tuning):
                                continue
                            midi = tuning[idx] + note.value
                        if not 0 <= midi <= 127:
                            continue
                        if note.type.name == "tie":
                            # extend the previous note of the same pitch
                            prev = next((n for n in reversed(notes)
                                         if n["midi_note"] == midi), None)
                            if prev is not None:
                                prev["duration_beats"] += dur
                            continue
                        vel = int(getattr(note, "velocity", 95) or 95)
                        notes.append({
                            "midi_note": midi,
                            "start_beat": round(beat_pos, 6),
                            "duration_beats": max(round(dur, 6), 1 / 32),
                            "velocity": max(1, min(127, vel)),
                        })
                    beat_pos += dur
            position += measure_beats

        if notes:
            notes.sort(key=lambda n: n["start_beat"])
            program = getattr(gp_track.channel, "instrument", 24) or 24
            is_drum = bool(gp_track.isPercussionTrack)
            result.detected_tracks.append(DetectedTrack(
                name=gp_track.name.strip() or f"Track {len(result.detected_tracks) + 1}",
                suggested_track_type=_program_to_track_type(program, is_drum),
                program=program, is_drum=is_drum,
                note_count=len(notes), notes=notes))

    if not result.detected_tracks:
        result.warnings.append("no note data found in Guitar Pro file")
    return result
