"""SingingVoiceEngine interface + MockSingingVoiceEngine.

The mock engine synthesizes a simple vowel-formant tone per melody note (so
vocal tracks are audible in mixes) and produces exact lyrics timing metadata.
Real singing engines (Phase 23) plug in behind the same interface and must
honor the same contract: consent-checked voice profile in, stem + alignment out.
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..config import get_config
from ..models.song import SongProject, StemRef, Track
from . import timing
from .audio_io import write_wav
from .render.soundfont_renderer import SAMPLE_RATE, _register_stem_asset, track_fingerprint

log = logging.getLogger(__name__)


@dataclass
class VocalRenderResult:
    stem_path: Path | None
    alignment: list[dict] = field(default_factory=list)
    render_log: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SingingVoiceEngine(ABC):
    @abstractmethod
    def render(self, project: SongProject, track: Track,
               out_path: Path) -> VocalRenderResult:
        """Render a vocal track to a WAV stem + lyrics alignment."""


def _note_freq(midi_note: int) -> float:
    return 440.0 * 2 ** ((midi_note - 69) / 12)


class MockSingingVoiceEngine(SingingVoiceEngine):
    """Sine + soft harmonics with vibrato and per-note envelope. Not a real
    voice — a placeholder that keeps the entire pipeline (timing, mixing,
    karaoke) real."""

    def render(self, project: SongProject, track: Track,
               out_path: Path) -> VocalRenderResult:
        result = VocalRenderResult(stem_path=None)
        total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
        out = np.zeros(total, dtype=np.float32)
        notes_rendered = 0

        for clip in track.clips:
            if clip.clip_type == "sample":
                continue
            for n in clip.note_events:
                t0 = timing.beats_to_seconds(project, clip.start_beat + n.start_beat)
                dur = timing.beats_to_seconds(project, n.duration_beats)
                i0 = int(t0 * SAMPLE_RATE)
                count = min(int(dur * SAMPLE_RATE), total - i0)
                if count <= 0:
                    continue
                t = np.arange(count) / SAMPLE_RATE
                vibrato = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t)
                f = _note_freq(n.midi_note)
                tone = (0.6 * np.sin(2 * np.pi * f * vibrato * t)
                        + 0.25 * np.sin(2 * np.pi * 2 * f * t)
                        + 0.1 * np.sin(2 * np.pi * 3 * f * t))
                attack = min(int(0.02 * SAMPLE_RATE), count)
                release = min(int(0.06 * SAMPLE_RATE), count)
                env = np.ones(count)
                env[:attack] = np.linspace(0, 1, attack)
                env[-release:] *= np.linspace(1, 0, release)
                out[i0:i0 + count] += (tone * env * (n.velocity / 127) * 0.35).astype(np.float32)
                notes_rendered += 1

        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 1.0:
            out /= peak
        stereo = np.repeat(out[:, None], 2, axis=1)
        write_wav(out_path, stereo, SAMPLE_RATE)
        result.stem_path = out_path
        result.render_log.append(
            f"mock engine rendered {notes_rendered} notes to {out_path.name}")
        if notes_rendered == 0:
            result.warnings.append(
                f"vocal track {track.name!r} has no melody notes — stem is silent; "
                "generate a melody with lyrics first")
        result.alignment = build_lyrics_alignment(project, track)
        return result


# --- lyrics alignment (Phase 18) -----------------------------------------

def _word_syllable_counts(line: str) -> list[tuple[str, int]]:
    out = []
    for word in line.split():
        clean = re.sub(r"[^A-Za-z']", "", word)
        groups = re.findall(r"[^aeiouy]*[aeiouy]+(?:[^aeiouy]+$)?", clean,
                            re.IGNORECASE)
        out.append((word, max(1, len(groups))))
    return out


def build_lyrics_alignment(project: SongProject, track: Track) -> list[dict]:
    """Derive line/word timing from the vocal melody notes.

    Notes carry one syllable each (set by generate_melody); words consume as
    many notes as they have syllables. Lines without matching notes fall back
    to an even spread across their section."""
    alignment: list[dict] = []
    # collect vocal notes with absolute times, ordered
    notes: list[dict] = []
    for clip in track.clips:
        if clip.clip_type == "sample":
            continue
        for n in clip.note_events:
            start = timing.beats_to_seconds(project, clip.start_beat + n.start_beat)
            end = start + timing.beats_to_seconds(project, n.duration_beats)
            notes.append({"id": n.id, "start": start, "end": end,
                          "section_id": clip.section_id})
    notes.sort(key=lambda x: x["start"])

    note_i = 0
    for line in project.lyrics.lines:
        words_spec = _word_syllable_counts(line.text)
        if not words_spec:
            continue
        section = project.get_section(line.section_id) if line.section_id else None
        line_notes_available = notes[note_i:]
        if line.section_id:
            line_notes_available = [x for x in line_notes_available
                                    if x["section_id"] in (line.section_id, "")]
        words: list[dict] = []
        if line_notes_available:
            k = 0
            for word, syl_count in words_spec:
                chunk = line_notes_available[k:k + syl_count]
                if not chunk:
                    break
                words.append({"word": word,
                              "start_time": round(chunk[0]["start"], 4),
                              "end_time": round(chunk[-1]["end"], 4),
                              "linked_note_id": chunk[0]["id"]})
                k += syl_count
            note_i += k
        if len(words) < len(words_spec):
            # fallback: spread remaining words across the section (or 3s)
            if section is not None:
                sec_t = timing.section_timing(project, section.id)
                base = words[-1]["end_time"] if words else sec_t["start_seconds"]
                end = sec_t["end_seconds"]
            else:
                base = words[-1]["end_time"] if words else 0.0
                end = base + 3.0
            remaining = words_spec[len(words):]
            step = max((end - base) / max(len(remaining), 1), 0.15)
            for j, (word, _) in enumerate(remaining):
                words.append({"word": word,
                              "start_time": round(base + j * step, 4),
                              "end_time": round(base + (j + 1) * step, 4),
                              "linked_note_id": None})
        confidence = (sum(1 for w in words if w["linked_note_id"]) /
                      max(len(words), 1))
        alignment.append({
            "line_id": line.id,
            "section_id": line.section_id,
            "text": line.text,
            "start_time": words[0]["start_time"],
            "end_time": words[-1]["end_time"],
            "words": words,
            "confidence": round(confidence, 2),
        })
    return alignment


def get_engine(engine_name: str = "mock") -> SingingVoiceEngine:
    """Factory for singing engines. Real engines register here in Phase 23."""
    if engine_name == "mock":
        return MockSingingVoiceEngine()
    raise ValueError(f"unknown singing voice engine {engine_name!r} "
                     "(only 'mock' is available in v1)")


def render_vocal_stems(project: SongProject) -> dict:
    """Render all vocal tracks; stores stems + lyrics_alignment.json."""
    import json

    cfg = get_config()
    results: dict = {"rendered": [], "skipped": [], "errors": [],
                     "warnings": [], "render_log": []}
    vocal_tracks = [t for t in project.tracks
                    if t.track_type in ("lead_vocal", "backing_vocal")]
    if not vocal_tracks:
        results["skipped"].append("no vocal tracks")
        return results

    engine = get_engine("mock")
    all_alignment: list[dict] = []
    from .midi_export import _safe_name
    for track in vocal_tracks:
        fp = track_fingerprint(project, track)
        out_path = cfg.stems_dir / project.id / f"vocal_{_safe_name(track.name)}_{track.id[:8]}.wav"
        try:
            r = engine.render(project, track, out_path)
        except Exception as e:
            results["errors"].append(f"{track.name}: {e}")
            continue
        results["warnings"].extend(r.warnings)
        results["render_log"].extend(r.render_log)
        rel = out_path.relative_to(cfg.root).as_posix()
        project.stems = [s for s in project.stems
                         if not (s.track_id == track.id and s.stem_type == "vocal")]
        stem = StemRef(track_id=track.id, stem_type="vocal", path=rel,
                       source_fingerprint=fp)
        _register_stem_asset(stem, track.name, "vocal_stem")
        project.stems.append(stem)
        results["rendered"].append({"track": track.name, "path": rel})
        if track.track_type == "lead_vocal" or not all_alignment:
            all_alignment = r.alignment

    align_path = cfg.projects_dir / project.id / "lyrics_alignment.json"
    align_path.parent.mkdir(parents=True, exist_ok=True)
    align_path.write_text(json.dumps(all_alignment, indent=1), encoding="utf-8")

    from .render.waveforms import update_waveform_cache
    update_waveform_cache(project)
    return results
