"""OperationApplier: validates and applies ChatOperations to a SongProject.

Referential rules enforced here:
- soundfonts, samples and voice profiles must exist in the registry
  (the LLM cannot invent assets)
- sections/tracks referenced by id or name must exist
"""
from __future__ import annotations

import logging
import re
from typing import Callable

from ..models.operations import ChatOperation, OperationResult
from ..models.song import (Clip, Effect, LyricsLine, Section, SongProject,
                           Track, INSTRUMENT_TRACK_TYPES)
from . import asset_repo, music_gen

log = logging.getLogger(__name__)


class OperationError(Exception):
    pass


def _find_section(project: SongProject, ref: str | None) -> Section:
    if not project.sections:
        raise OperationError("project has no sections yet — add a section first")
    if ref is None:
        return project.sections[-1]
    for s in project.sections:
        if s.id == ref or s.name.lower() == str(ref).lower():
            return s
    raise OperationError(f"section {ref!r} not found")


def _find_track(project: SongProject, ref: str) -> Track:
    for t in project.tracks:
        if t.id == ref or t.name.lower() == str(ref).lower():
            return t
    raise OperationError(f"track {ref!r} not found")


def _require_asset(asset_id: str, expected_type: str):
    asset = asset_repo.get_asset(asset_id)
    if asset is None:
        raise OperationError(f"asset {asset_id} does not exist")
    if asset.asset_type != expected_type:
        raise OperationError(
            f"asset {asset.filename!r} is {asset.asset_type}, expected {expected_type}")
    if asset.is_missing:
        raise OperationError(f"asset file {asset.filename!r} is missing on disk")
    return asset


def _next_start_bar(project: SongProject) -> int:
    return max((s.start_bar + s.length_bars for s in project.sections), default=0)


# --- operation handlers ---------------------------------------------------

def op_create_song(project: SongProject, p: dict) -> str:
    project.title = p.get("title", project.title)
    project.style = p.get("style", project.style)
    if "bpm" in p:
        project.bpm = float(p["bpm"])
    if "key" in p:
        project.key = str(p["key"])
    if "time_signature" in p:
        project.time_signature = str(p["time_signature"])
    return (f"song set up: {project.title!r}, style={project.style or 'n/a'}, "
            f"{project.bpm:g} BPM, {project.key}")


def op_add_section(project: SongProject, p: dict) -> str:
    name = p.get("name") or f"Section {len(project.sections) + 1}"
    section = Section(
        name=name,
        start_bar=int(p.get("start_bar", _next_start_bar(project))),
        length_bars=int(p.get("length_bars", 8)),
        energy=float(p.get("energy", 0.5)),
        description=p.get("description", ""))
    project.sections.append(section)
    return f"added section {name!r} ({section.length_bars} bars at bar {section.start_bar})"


def op_update_section(project: SongProject, p: dict) -> str:
    s = _find_section(project, p.get("section"))
    for field in ("name", "length_bars", "start_bar", "energy", "description"):
        if field in p:
            setattr(s, field, p[field])
    return f"updated section {s.name!r}"


def op_add_track(project: SongProject, p: dict) -> str:
    track_type = p.get("track_type", "keys")
    name = p.get("name") or track_type.replace("_", " ").title()
    track = Track(name=name, track_type=track_type)
    if p.get("synth_patch"):
        from .render import synth_engine
        if synth_engine.get_patch(str(p["synth_patch"])) is not None:
            track.instrument_config.synth_patch = str(p["synth_patch"])
    elif p.get("soundfont_asset_id"):
        _require_asset(p["soundfont_asset_id"], "soundfont")
        track.instrument_config.soundfont_asset_id = p["soundfont_asset_id"]
    if "program" in p:
        track.instrument_config.program = int(p["program"])
    track.instrument_config.is_drum_kit = track_type == "drums"
    project.tracks.append(track)
    return f"added {track_type} track {name!r}"


def op_update_track(project: SongProject, p: dict) -> str:
    t = _find_track(project, p.get("track", ""))
    changes = []
    if p.get("name"):
        changes.append(f"renamed to {p['name']!r}")
        t.name = str(p["name"])
    if "volume" in p:
        t.volume = max(0.0, min(2.0, float(p["volume"])))
        changes.append(f"volume {t.volume:g}")
    if "pan" in p:
        t.pan = max(-1.0, min(1.0, float(p["pan"])))
        changes.append(f"pan {t.pan:g}")
    if "mute" in p:
        t.mute = bool(p["mute"])
        changes.append("muted" if t.mute else "unmuted")
    if "solo" in p:
        t.solo = bool(p["solo"])
        changes.append("soloed" if t.solo else "unsoloed")
    if not changes:
        raise OperationError(
            "update_track requires at least one of: name, volume, pan, mute, solo")
    return f"track {t.name!r}: " + ", ".join(changes)


def _clip_at_bar(project: SongProject, track: Track, at_bar) :
    """The clip covering the given bar (1-based, as users speak); without
    at_bar, the track's last clip."""
    if not track.clips:
        raise OperationError(f"track {track.name!r} has no clips")
    if at_bar is None:
        return max(track.clips, key=lambda c: c.start_beat)
    beat = (float(at_bar) - 1) * project.beats_per_bar
    for c in track.clips:
        if c.start_beat <= beat < c.start_beat + c.duration_beats:
            return c
    raise OperationError(f"no clip on track {track.name!r} at bar {at_bar}")


def op_split_clip(project: SongProject, p: dict) -> str:
    from ..models.song import new_id
    t = _find_track(project, p.get("track", ""))
    if p.get("at_bar") is None:
        raise OperationError("split_clip requires 'at_bar'")
    clip = _clip_at_bar(project, t, p["at_bar"])
    cut = (float(p["at_bar"]) - 1) * project.beats_per_bar
    rel = cut - clip.start_beat
    if rel <= 0.01 or rel >= clip.duration_beats - 0.01:
        raise OperationError("the split point must fall inside the clip")
    second = clip.model_copy(deep=True)
    second.id = new_id()
    second.start_beat = clip.start_beat + rel
    second.duration_beats = clip.duration_beats - rel
    second.fade_in_seconds = 0.0
    clip.fade_out_seconds = 0.0
    if clip.clip_type == "sample":
        second.source_offset_seconds = (clip.source_offset_seconds
                                        + rel * 60.0 / project.bpm)
        second.note_events = []
    else:
        first_notes, moved = [], []
        for n in clip.note_events:
            if n.start_beat < rel:
                n.duration_beats = min(n.duration_beats, rel - n.start_beat)
                if n.duration_beats > 0.01:
                    first_notes.append(n)
            else:
                n2 = n.model_copy()
                n2.id = new_id()
                n2.start_beat = n.start_beat - rel
                moved.append(n2)
        clip.note_events = first_notes
        second.note_events = moved
    clip.duration_beats = rel
    t.clips.insert(t.clips.index(clip) + 1, second)
    return f"split the clip on {t.name!r} at bar {p['at_bar']}"


def op_duplicate_clip(project: SongProject, p: dict) -> str:
    from ..models.song import new_id
    t = _find_track(project, p.get("track", ""))
    clip = _clip_at_bar(project, t, p.get("at_bar"))
    copy = clip.model_copy(deep=True)
    copy.id = new_id()
    copy.start_beat = clip.start_beat + clip.duration_beats
    for n in copy.note_events:
        n.id = new_id()
    t.clips.insert(t.clips.index(clip) + 1, copy)
    bar = int(copy.start_beat / project.beats_per_bar) + 1
    return f"duplicated the clip on {t.name!r} (copy starts at bar {bar})"


def op_delete_clip(project: SongProject, p: dict) -> str:
    t = _find_track(project, p.get("track", ""))
    clip = _clip_at_bar(project, t, p.get("at_bar"))
    t.clips = [c for c in t.clips if c.id != clip.id]
    return f"deleted a clip from {t.name!r}"


def op_remove_track(project: SongProject, p: dict) -> str:
    t = _find_track(project, p.get("track", ""))
    project.tracks = [x for x in project.tracks if x.id != t.id]
    return f"removed track {t.name!r}"


def op_assign_soundfont(project: SongProject, p: dict) -> str:
    """Assign a SoundFont preset to a track. The LLM may name a preset the
    font doesn't contain (it can't see every bank/program), so the bank +
    program are VERIFIED against the font's real inventory. If the pair isn't
    a real preset, snap to the best-fitting preset for the track type — in
    that font, else anywhere in the library. The label always reflects the
    preset that is actually loaded, never the model's claim."""
    from pathlib import Path

    from .sf2_parser import (find_best_soundfont, get_preset_inventory,
                             score_soundfont_for_track)

    t = _find_track(project, p.get("track", ""))
    asset = _require_asset(p.get("soundfont_asset_id", ""), "soundfont")
    bank = int(p["bank"]) if "bank" in p else None
    program = int(p["program"]) if "program" in p else None

    inv = get_preset_inventory(asset.id, Path(asset.original_path)) or {}
    presets = inv.get("presets", [])
    real = None
    if bank is not None and program is not None:
        real = next((pr for pr in presets
                     if pr["bank"] == bank and pr["program"] == program), None)

    if real is None and presets:
        # the model's bank/program isn't in this font — pick a preset that
        # genuinely suits the track type instead of a phantom sound
        _score, real = score_soundfont_for_track(inv, t.track_type,
                                                  asset.filename)
    if real is None:
        # this font has nothing tagged for the track — search the whole
        # library for a font that does
        match = find_best_soundfont(t.track_type)
        if match is not None:
            asset, real = match
    if real is None:
        # last resort: SOME real preset from the assigned font, so a track
        # never ends up pointing at a bank/program that doesn't exist
        inv2 = get_preset_inventory(asset.id, Path(asset.original_path)) or {}
        p2 = inv2.get("presets")
        real = p2[0] if p2 else None

    t.instrument_config.soundfont_asset_id = asset.id
    if real is not None:
        t.instrument_config.bank = int(real["bank"])
        t.instrument_config.program = int(real["program"])
        label = real["name"] or asset.filename
    else:
        # font is unreadable — keep the model's numbers, nothing better exists
        if bank is not None:
            t.instrument_config.bank = bank
        if program is not None:
            t.instrument_config.program = program
        label = p.get("preset") or asset.filename
    t.instrument_config.is_drum_kit = t.instrument_config.bank == 128
    # a real SoundFont was chosen — drop any prior built-in synth override
    t.instrument_config.synth_patch = ""
    return f"assigned instrument {label!r} to track {t.name!r}"


def op_assign_synth(project: SongProject, p: dict) -> str:
    """Route a track to a built-in synth patch (works with zero setup, no
    SoundFont/FluidSynth needed). The patch id is validated against the
    engine; assigning a synth clears any SoundFont so the synth wins."""
    from .render import synth_engine

    t = _find_track(project, p.get("track", ""))
    patch_id = str(p.get("synth_patch", "")).strip()
    patch = synth_engine.get_patch(patch_id)
    if patch is None:
        raise OperationError(
            f"unknown synth patch {patch_id!r}; valid ids: "
            + ", ".join(sorted(synth_engine.PATCHES)))
    t.instrument_config.synth_patch = patch.id
    t.instrument_config.soundfont_asset_id = None
    t.instrument_config.is_drum_kit = patch.id == "drum_kit"
    return f"assigned built-in synth {patch.label!r} to track {t.name!r}"


def op_select_sample(project: SongProject, p: dict) -> str:
    asset = _require_asset(p.get("sample_asset_id", ""), "sample")
    track_ref = p.get("track")
    track = None
    if track_ref:
        track = _find_track(project, track_ref)
        if track.track_type != "sample":
            # LLMs often aim a sample at an instrument/vocal track — put it
            # on a sample lane instead of failing the whole placement
            track = next((t for t in project.tracks
                          if t.track_type == "sample"), None)
    if track is None:
        track = Track(name=p.get("track_name") or asset.filename.rsplit(".", 1)[0],
                      track_type="sample")
        project.tracks.append(track)
    bpb = project.beats_per_bar
    section = _find_section(project, p.get("section")) if project.sections else None
    start_beat = float(p.get("start_beat",
                             section.start_bar * bpb if section else 0.0))
    duration = float(p.get("duration_beats",
                           section.length_bars * bpb if section else bpb * 4))
    track.clips.append(Clip(
        section_id=section.id if section else "",
        clip_type="sample", start_beat=start_beat, duration_beats=duration,
        source_asset_id=asset.id, loop=bool(p.get("loop", False)),
        gain_db=float(p.get("gain_db", 0.0))))
    return f"placed sample {asset.filename!r} on track {track.name!r} at beat {start_beat:g}"


def _generate(project: SongProject, p: dict, kind: str,
              default_track_type: str, gen: Callable) -> str:
    # section "all"/"*" generates for every section in one operation
    if str(p.get("section", "")).lower() in ("all", "*"):
        if not project.sections:
            raise OperationError("project has no sections yet")
        summaries = []
        for s in project.sections:
            sub = dict(p)
            sub["section"] = s.id
            summaries.append(_generate(project, sub, kind,
                                       default_track_type, gen))
        return f"generated {kind} for all {len(project.sections)} sections"
    section = _find_section(project, p.get("section"))
    track_ref = p.get("track")
    track = None
    if track_ref:
        try:
            track = _find_track(project, track_ref)
        except OperationError:
            track = Track(name=str(track_ref), track_type=default_track_type)
            track.instrument_config.is_drum_kit = default_track_type == "drums"
            project.tracks.append(track)
    else:
        track = next((t for t in project.tracks
                      if t.track_type == default_track_type), None)
    if track is None:
        track = Track(name=default_track_type.title(),
                      track_type=default_track_type)
        track.instrument_config.is_drum_kit = default_track_type == "drums"
        project.tracks.append(track)
    clip = gen(project, section)
    # replace an existing generated clip for the same section
    track.clips = [c for c in track.clips if c.section_id != section.id]
    track.clips.append(clip)
    return (f"generated {kind} for section {section.name!r} on track "
            f"{track.name!r} ({len(clip.note_events)} notes)")


def op_generate_drums(project: SongProject, p: dict) -> str:
    return _generate(project, p, "drums", "drums", music_gen.generate_drums)


def op_generate_bassline(project: SongProject, p: dict) -> str:
    return _generate(project, p, "bassline", "bass", music_gen.generate_bassline)


def op_generate_chords(project: SongProject, p: dict) -> str:
    default = p.get("track_type", "guitar" if project.style.lower() in
                    ("punk", "rock", "metal") else "keys")
    return _generate(project, p, "chords", default, music_gen.generate_chords)


def op_write_notes(project: SongProject, p: dict) -> str:
    """LLM-composed part: explicit notes for one section on one track —
    the AI writes the actual pattern instead of a procedural template.
    notes: [{midi_note, start_beat (relative to the section), duration_beats,
    velocity?}], validated and clamped so a hallucinated note can't corrupt
    the project."""
    from ..models.song import NoteEvent

    raw = p.get("notes")
    if not isinstance(raw, list) or not raw:
        raise OperationError("write_notes needs a non-empty 'notes' list")
    if len(raw) > 400:
        raise OperationError("write_notes: too many notes (max 400)")

    track_type = str(p.get("track_type", "synth"))

    def gen(proj: SongProject, section) -> Clip:
        bpb = proj.beats_per_bar
        length = section.length_bars * bpb
        events: list[NoteEvent] = []
        for n in raw:
            try:
                midi = int(n.get("midi_note", n.get("midi", 0)))
                start = float(n.get("start_beat", 0.0))
                dur = float(n.get("duration_beats", 0.5))
                vel = int(n.get("velocity", 96))
            except (TypeError, ValueError, AttributeError):
                continue
            if not 12 <= midi <= 120 or dur <= 0 or start < 0 \
                    or start >= length:
                continue
            events.append(NoteEvent(
                pitch="", midi_note=midi,
                start_beat=round(start, 4),
                duration_beats=round(min(dur, length - start), 4),
                velocity=max(1, min(vel, 127)), lyric_syllable=""))
        if not events:
            raise OperationError("write_notes: no valid notes after "
                                 "validation")
        return Clip(section_id=section.id, clip_type="midi",
                    start_beat=section.start_bar * bpb,
                    duration_beats=length, note_events=events)

    return _generate(project, p, "written part", track_type, gen)


def op_generate_melody(project: SongProject, p: dict) -> str:
    if str(p.get("section", "")).lower() in ("all", "*"):
        if not project.sections:
            raise OperationError("project has no sections yet")
        for s in project.sections:
            sub = dict(p)
            sub["section"] = s.id
            op_generate_melody(project, sub)
        return f"generated melodies for all {len(project.sections)} sections"
    section = _find_section(project, p.get("section"))
    lines = [l.text for l in project.lyrics.lines
             if l.section_id == section.id] or None
    track_type = p.get("track_type", "lead_vocal" if lines else "synth")

    if lines and track_type in ("lead_vocal", "backing_vocal"):
        # sung/rapped vocals: one note per syllable (clone-engine aligned)
        rap = str(p.get("style", "")).lower() == "rap"
        track_ref = p.get("track")
        pace = 1.0
        if track_ref:
            existing = next((t for t in project.tracks
                             if t.id == track_ref
                             or t.name.lower() == str(track_ref).lower()), None)
            if existing is not None:
                rap = rap or existing.vocal_style == "rap"
                pace = getattr(existing, "vocal_pace", 1.0) or 1.0

        harmony = track_type == "backing_vocal"

        def gen(proj, sec):
            return music_gen.generate_vocal_melody(proj, sec, lines, rap=rap,
                                                   harmony=harmony, pace=pace)
        return _generate(project, p, "rap flow" if rap else "vocal melody",
                         track_type, gen)

    def gen(proj, sec):
        return music_gen.generate_melody(proj, sec, lines)
    return _generate(project, p, "melody", track_type, gen)


_SECTION_PREFIX = re.compile(
    r"^\s*((?:pre-?)?(?:verse|chorus|bridge|intro|outro|drop|hook|refrain|"
    r"final\s+chorus)(?:\s*\d+)?)\s*:\s*", re.IGNORECASE)


def _split_prefixed_sheet(lines: list) -> list[tuple[str, str]] | None:
    """LLMs often dump a full lyric sheet as one op, prefixing lines with
    'Chorus:', 'Verse 2:' …  Detect that and return [(section_hint, text)];
    None when the lines aren't a prefixed sheet."""
    hits = 0
    parsed: list[tuple[str, str]] = []
    current = ""
    for raw in lines:
        text = str(raw)
        m = _SECTION_PREFIX.match(text)
        if m:
            hits += 1
            current = m.group(1).strip().lower()
            text = text[m.end():].strip()
        parsed.append((current, text))
    return parsed if hits >= max(2, len(lines) // 3) else None


def op_rewrite_lyrics(project: SongProject, p: dict) -> str:
    from . import lyrics_editing

    lines = p.get("lines")
    if not isinstance(lines, list) or not lines:
        raise OperationError("rewrite_lyrics requires a non-empty 'lines' list")
    lyrics_editing.snapshot(project, "chat")

    # a prefixed full-sheet targets the WHOLE song, whatever section the op
    # names — putting 30 lines in one section silences most of the singing
    sheet = _split_prefixed_sheet(lines) if project.sections else None
    if sheet is not None:
        by_name = {s.name.lower(): s for s in project.sections}
        placed = 0
        project.lyrics.lines = []
        fallback = project.sections[0]
        for hint, text in sheet:
            if not text.strip():
                continue
            section = by_name.get(hint)
            if section is None and hint:   # 'verse 2' → any section containing 'verse 2', then 'verse'
                section = next((s for n, s in by_name.items() if hint in n or n in hint), None)
            if section is None and hint:
                base = hint.split()[0]
                section = next((s for n, s in by_name.items() if base in n), None)
            section = section or fallback
            fallback = section
            project.lyrics.lines.append(LyricsLine(section_id=section.id,
                                                   text=text))
            placed += 1
        if "language" in p:
            project.lyrics.language = str(p["language"])
        for s in project.sections:
            lyrics_editing.resync_section(project, s.id)
        return (f"detected a full lyric sheet — placed {placed} lines across "
                f"their sections")

    if str(p.get("section", "")).lower() in ("all", "*") and project.sections:
        # distribute lines across sections in even chunks (full-song lyrics)
        sections = project.sections
        chunk = max(1, -(-len(lines) // len(sections)))  # ceil division
        total = 0
        for i, s in enumerate(sections):
            part = lines[i * chunk:(i + 1) * chunk]
            if not part:
                break
            project.lyrics.lines = [l for l in project.lyrics.lines
                                    if l.section_id != s.id]
            for text in part:
                project.lyrics.lines.append(LyricsLine(section_id=s.id,
                                                       text=str(text)))
            total += len(part)
        if "language" in p:
            project.lyrics.language = str(p["language"])
        for s in sections:   # existing melodies must follow the new words
            lyrics_editing.resync_section(project, s.id)
        return f"distributed {total} lyric lines across {len(sections)} sections"
    section = _find_section(project, p.get("section")) if project.sections else None
    section_id = section.id if section else ""
    project.lyrics.lines = [l for l in project.lyrics.lines
                            if l.section_id != section_id]
    for text in lines:
        project.lyrics.lines.append(LyricsLine(section_id=section_id,
                                               text=str(text)))
    if "language" in p:
        project.lyrics.language = str(p["language"])
    if section_id:
        lyrics_editing.resync_section(project, section_id)
    where = f" for section {section.name!r}" if section else ""
    return f"set {len(lines)} lyric line(s){where}"


def op_change_key(project: SongProject, p: dict) -> str:
    key = p.get("key")
    if not key:
        raise OperationError("change_key requires 'key'")
    project.key = str(key)
    return f"changed key to {project.key}"


def op_change_tempo(project: SongProject, p: dict) -> str:
    bpm = p.get("bpm")
    if bpm is None:
        raise OperationError("change_tempo requires 'bpm'")
    if isinstance(bpm, str) and bpm.strip().startswith(("+", "-")):
        bpm = project.bpm + float(bpm)   # relative change, e.g. "+15"
    else:
        bpm = float(bpm)
    if not 20 < bpm < 400:
        raise OperationError(f"bpm {bpm} out of range (20-400)")
    project.bpm = bpm
    return f"changed tempo to {bpm:g} BPM"


def op_import_score(project: SongProject, p: dict) -> str:
    from . import score_import
    asset = _require_asset(p.get("score_asset_id", ""), "score")
    result = score_import.import_score(asset)
    if not result.supported:
        raise OperationError("; ".join(result.warnings))
    p["_import_result"] = result  # available for arrange_from_score
    return (f"imported score {asset.filename!r}: "
            f"{len(result.detected_tracks)} tracks, "
            f"tempo {result.detected_tempo or 'unknown'}")


def op_arrange_from_score(project: SongProject, p: dict) -> str:
    from . import score_import
    asset = _require_asset(p.get("score_asset_id", ""), "score")
    result = p.get("_import_result") or score_import.import_score(asset)
    if not result.supported or not result.detected_tracks:
        raise OperationError(
            f"score {asset.filename!r} cannot be arranged: "
            + "; ".join(result.warnings))
    imported = score_import.project_from_import(result, project.title,
                                                project.style)
    project.bpm = imported.bpm
    project.time_signature = imported.time_signature
    project.key = imported.key
    project.sections = imported.sections
    project.tracks = imported.tracks
    if asset.id not in project.source_assets:
        project.source_assets.append(asset.id)
    return (f"arranged project from {asset.filename!r} "
            f"({len(project.tracks)} tracks)")


_EFFECT_TYPES = {"gain", "pan", "eq", "compressor", "reverb", "delay",
                 "distortion", "robot", "telephone", "chorus", "autotune"}


def op_add_effect(project: SongProject, p: dict) -> str:
    etype = p.get("effect_type")
    if etype not in _EFFECT_TYPES:
        raise OperationError(f"unknown effect type {etype!r} "
                             f"(supported: {sorted(_EFFECT_TYPES)})")
    params = p.get("params", {})
    if not isinstance(params, dict):
        raise OperationError("'params' must be an object")
    effect = Effect(effect_type=etype, params={
        k: float(v) for k, v in params.items()})
    target = p.get("track", "")
    if str(target).lower() == "master":
        project.mix_settings.master_effects.effects.append(effect)
        return f"added {etype} effect to the master bus"
    t = _find_track(project, target)
    t.effects.effects.append(effect)
    return f"added {etype} effect to track {t.name!r}"


def op_update_effect(project: SongProject, p: dict) -> str:
    t = _find_track(project, p.get("track", ""))
    ref = p.get("effect_id") or p.get("effect_type")
    for e in t.effects.effects:
        if e.id == ref or e.effect_type == ref:
            if "params" in p:
                e.params.update({k: float(v) for k, v in p["params"].items()})
            if "enabled" in p:
                e.enabled = bool(p["enabled"])
            return f"updated {e.effect_type} effect on track {t.name!r}"
    raise OperationError(f"effect {ref!r} not found on track {t.name!r}")


def op_create_vocal_track(project: SongProject, p: dict) -> str:
    track_type = p.get("track_type", "lead_vocal")
    if track_type not in ("lead_vocal", "backing_vocal"):
        raise OperationError("track_type must be lead_vocal or backing_vocal")
    name = p.get("name") or ("Lead Vocal" if track_type == "lead_vocal"
                             else "Backing Vocal")
    track = Track(name=name, track_type=track_type)
    style = str(p.get("vocal_style", "")).lower()
    if style in ("rap", "soft", "powerful"):
        track.vocal_style = style  # type: ignore[assignment]
    elif "rap" in name.lower():
        track.vocal_style = "rap"
    if p.get("voice_profile_id"):
        from . import voice_profiles
        profile = voice_profiles.get_profile(p["voice_profile_id"])
        if profile is None:
            raise OperationError(f"voice profile {p['voice_profile_id']} does not exist")
        track.voice_profile_id = profile.id
    project.tracks.append(track)
    return f"created vocal track {name!r}"


def op_assign_voice_profile(project: SongProject, p: dict) -> str:
    from . import voice_profiles
    t = _find_track(project, p.get("track", ""))
    if t.track_type not in ("lead_vocal", "backing_vocal"):
        raise OperationError(f"track {t.name!r} is not a vocal track")
    profile = voice_profiles.get_profile(p.get("voice_profile_id", ""))
    if profile is None:
        raise OperationError("voice profile does not exist")
    if not profile.consent_confirmed:
        raise OperationError("voice profile has no confirmed consent")
    t.voice_profile_id = profile.id
    return f"assigned voice profile {profile.name!r} to track {t.name!r}"


def op_render_stems(project: SongProject, p: dict) -> str:
    # rendering is executed by the render endpoints; from chat we only flag it
    project.render_status = "render_requested"
    return "stem rendering requested — use the Export panel or render endpoints"


def op_render_mix(project: SongProject, p: dict) -> str:
    project.render_status = "mix_requested"
    return "mix export requested — use the Export panel or export endpoint"


_HANDLERS: dict[str, Callable[[SongProject, dict], str]] = {
    "create_song": op_create_song,
    "add_section": op_add_section,
    "update_section": op_update_section,
    "add_track": op_add_track,
    "update_track": op_update_track,
    "remove_track": op_remove_track,
    "split_clip": op_split_clip,
    "duplicate_clip": op_duplicate_clip,
    "delete_clip": op_delete_clip,
    "assign_soundfont": op_assign_soundfont,
    "assign_synth": op_assign_synth,
    "select_sample": op_select_sample,
    "generate_chords": op_generate_chords,
    "generate_melody": op_generate_melody,
    "generate_drums": op_generate_drums,
    "write_notes": op_write_notes,
    "generate_bassline": op_generate_bassline,
    "rewrite_lyrics": op_rewrite_lyrics,
    "change_key": op_change_key,
    "change_tempo": op_change_tempo,
    "import_score": op_import_score,
    "arrange_from_score": op_arrange_from_score,
    "add_effect": op_add_effect,
    "update_effect": op_update_effect,
    "create_vocal_track": op_create_vocal_track,
    "assign_voice_profile": op_assign_voice_profile,
    "render_stems": op_render_stems,
    "render_mix": op_render_mix,
}


def apply_operations(project: SongProject,
                     operations: list[ChatOperation]) -> list[OperationResult]:
    """Apply operations in order. Each op is validated against a working copy
    so a failing op never leaves the project half-modified."""
    results: list[OperationResult] = []
    for op in operations:
        handler = _HANDLERS.get(op.op_type)
        if handler is None:
            results.append(OperationResult(op_type=op.op_type, summary="",
                                           applied=False,
                                           error=f"unknown operation {op.op_type!r}"))
            continue
        snapshot = project.model_copy(deep=True)
        try:
            summary = handler(project, dict(op.params))
            SongProject.model_validate(project.model_dump())  # re-validate
            results.append(OperationResult(op_type=op.op_type,
                                           summary=summary, applied=True))
        except (OperationError, ValueError) as e:
            project.sections = snapshot.sections
            project.tracks = snapshot.tracks
            project.lyrics = snapshot.lyrics
            project.bpm, project.key = snapshot.bpm, snapshot.key
            project.title, project.style = snapshot.title, snapshot.style
            project.time_signature = snapshot.time_signature
            project.mix_settings = snapshot.mix_settings
            results.append(OperationResult(op_type=op.op_type, summary="",
                                           applied=False, error=str(e)))
    return results
