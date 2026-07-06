"""MusicXML importer (stdlib xml.etree — no extra deps).

Supports part-wise scores (.musicxml, .xml) and compressed .mxl archives:
parts, notes/chords/rests, ties, divisions, tempo, time signature, key
(fifths), per-part MIDI program. Voices/graces/tuplet nuances beyond
duration math are flattened — good enough to arrange from.
"""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from xml.etree import ElementTree

log = logging.getLogger(__name__)

_STEP_TO_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

_FIFTHS_TO_KEY = {
    -7: "Cb", -6: "Gb", -5: "Db", -4: "Ab", -3: "Eb", -2: "Bb", -1: "F",
    0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
}


def _load_root(path: Path) -> ElementTree.Element:
    if path.suffix.lower() == ".mxl" or zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            # META-INF/container.xml names the rootfile; fall back to first xml
            name = None
            try:
                container = ElementTree.fromstring(
                    zf.read("META-INF/container.xml"))
                rf = container.find(".//rootfile")
                if rf is not None:
                    name = rf.get("full-path")
            except KeyError:
                pass
            if name is None:
                name = next(n for n in zf.namelist()
                            if n.endswith(".xml") and not n.startswith("META-INF"))
            return ElementTree.fromstring(zf.read(name))
    return ElementTree.parse(str(path)).getroot()


def _pitch_to_midi(pitch_el) -> int | None:
    step = pitch_el.findtext("step")
    octave = pitch_el.findtext("octave")
    if step is None or octave is None:
        return None
    alter = int(float(pitch_el.findtext("alter") or 0))
    midi = (int(octave) + 1) * 12 + _STEP_TO_PC[step] + alter
    return midi if 0 <= midi <= 127 else None


def import_musicxml(path: Path, asset_id: str):
    from .score_import import DetectedTrack, ScoreImportResult

    result = ScoreImportResult(source_asset_id=asset_id, format="musicxml")
    try:
        root = _load_root(path)
    except Exception as e:
        result.supported = False
        result.warnings.append(f"cannot parse MusicXML: {e}")
        return result

    if root.tag == "score-timewise":
        result.supported = False
        result.warnings.append("timewise MusicXML not supported (export as partwise)")
        return result
    if root.tag != "score-partwise":
        result.supported = False
        result.warnings.append(f"unexpected root element {root.tag!r}")
        return result

    # part names + midi programs from part-list
    part_meta: dict[str, dict] = {}
    for sp in root.iterfind(".//part-list/score-part"):
        pid = sp.get("id", "")
        program = sp.findtext(".//midi-instrument/midi-program")
        channel = sp.findtext(".//midi-instrument/midi-channel")
        part_meta[pid] = {
            "name": (sp.findtext("part-name") or pid).strip(),
            "program": max(0, int(program) - 1) if program else 0,
            "is_drum": channel == "10",
        }

    for part in root.iterfind("part"):
        pid = part.get("id", "")
        meta = part_meta.get(pid, {"name": pid, "program": 0, "is_drum": False})
        divisions = 1
        position = 0.0  # in beats (quarter notes)
        notes: list[dict] = []
        open_ties: dict[int, int] = {}  # midi -> index into notes

        for measure in part.iterfind("measure"):
            attrs = measure.find("attributes")
            if attrs is not None:
                d = attrs.findtext("divisions")
                if d:
                    divisions = int(d)
                fifths = attrs.findtext("key/fifths")
                if fifths is not None:
                    mode = attrs.findtext("key/mode") or "major"
                    root_name = _FIFTHS_TO_KEY.get(int(fifths), "C")
                    result.detected_key = f"{root_name} {mode}"
                beats = attrs.findtext("time/beats")
                beat_type = attrs.findtext("time/beat-type")
                if beats and beat_type:
                    result.time_signature = f"{beats}/{beat_type}"
            for direction in measure.iterfind("direction"):
                tempo_el = direction.find(".//sound[@tempo]")
                if tempo_el is not None:
                    result.detected_tempo = float(tempo_el.get("tempo"))
            for sound in measure.iterfind("sound[@tempo]"):
                result.detected_tempo = float(sound.get("tempo"))

            chord_start = position
            for el in measure:
                if el.tag == "backup":
                    position -= float(el.findtext("duration") or 0) / divisions
                elif el.tag == "forward":
                    position += float(el.findtext("duration") or 0) / divisions
                elif el.tag == "note":
                    dur_beats = float(el.findtext("duration") or 0) / divisions
                    is_chord = el.find("chord") is not None
                    start = chord_start if is_chord else position
                    if not is_chord:
                        chord_start = position
                        position += dur_beats
                    if el.find("rest") is not None or el.find("grace") is not None:
                        continue
                    pitch_el = el.find("pitch")
                    if pitch_el is None:
                        pitch_el = el.find("unpitched")
                    midi = None
                    if pitch_el is not None and pitch_el.tag == "pitch":
                        midi = _pitch_to_midi(pitch_el)
                    elif pitch_el is not None:  # unpitched (percussion)
                        step = pitch_el.findtext("display-step") or "C"
                        octv = pitch_el.findtext("display-octave") or "4"
                        midi = (int(octv) + 1) * 12 + _STEP_TO_PC.get(step, 0)
                    if midi is None:
                        continue
                    tie_types = {t.get("type") for t in el.iterfind("tie")}
                    if "stop" in tie_types and midi in open_ties:
                        notes[open_ties[midi]]["duration_beats"] += dur_beats
                        if "start" not in tie_types:
                            open_ties.pop(midi, None)
                        continue
                    notes.append({
                        "midi_note": midi,
                        "start_beat": round(start, 6),
                        "duration_beats": max(round(dur_beats, 6), 1 / 32),
                        "velocity": 90,
                    })
                    if "start" in tie_types:
                        open_ties[midi] = len(notes) - 1

        if notes:
            notes.sort(key=lambda n: n["start_beat"])
            from .score_import import _program_to_track_type
            result.detected_tracks.append(DetectedTrack(
                name=meta["name"],
                suggested_track_type=_program_to_track_type(
                    meta["program"], meta["is_drum"]),
                program=meta["program"], is_drum=meta["is_drum"],
                note_count=len(notes), notes=notes))

    if result.detected_tempo is None:
        result.warnings.append("no tempo found, defaulting to 120")
        result.detected_tempo = 120.0
    if not result.detected_tracks:
        result.warnings.append("no note data found in MusicXML")
    return result
