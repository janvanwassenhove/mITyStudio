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


# vowel formant frequencies (F1, F2, F3) and relative amplitudes — classic
# soprano/alto averages; consonants are approximated by a short noise burst
_VOWEL_FORMANTS = {
    "a": ((800, 1150, 2900), (1.0, 0.50, 0.18)),
    "e": ((400, 1600, 2700), (1.0, 0.35, 0.15)),
    "i": ((350, 1700, 2700), (1.0, 0.25, 0.12)),
    "o": ((450, 800, 2830), (1.0, 0.45, 0.10)),
    "u": ((325, 700, 2700), (1.0, 0.35, 0.08)),
}


def _vowel_of(syllable: str) -> str:
    s = syllable.lower()
    for ch in s:
        if ch in "aeiou":
            return "e" if ch == "y" else ch
    return "a"


def _has_leading_consonant(syllable: str) -> bool:
    return bool(syllable) and syllable[0].lower() not in "aeiouy"


class MockSingingVoiceEngine(SingingVoiceEngine):
    """Formant singing synthesis: a sawtooth-ish glottal source shaped by the
    vowel formants of each lyric syllable, with vibrato, consonant noise
    bursts and legato envelopes. Clearly synthetic — no cloning — but sings
    recognizable vowels in time and in tune."""

    def render(self, project: SongProject, track: Track,
               out_path: Path) -> VocalRenderResult:
        result = VocalRenderResult(stem_path=None)
        total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
        out = np.zeros(total, dtype=np.float32)
        notes_rendered = 0
        rng = np.random.default_rng(hash(track.id) & 0xFFFFFFFF)

        seq: list[tuple[float, float, "object"]] = []
        for clip in track.clips:
            if clip.clip_type == "sample":
                continue
            for n in clip.note_events:
                t0 = timing.beats_to_seconds(project, clip.start_beat + n.start_beat)
                dur = timing.beats_to_seconds(project, n.duration_beats)
                seq.append((t0, dur, n))
        seq.sort(key=lambda x: x[0])
        prev_f0: float | None = None
        prev_end = -1.0
        for t0, dur, n in seq:
                i0 = int(t0 * SAMPLE_RATE)
                count = min(int(dur * SAMPLE_RATE), total - i0)
                if count <= 0:
                    continue
                t = np.arange(count) / SAMPLE_RATE
                f0 = _note_freq(n.midi_note)
                # legato portamento from the previous note, else scoop in
                if prev_f0 is not None and t0 - prev_end < 0.06:
                    glide = min(0.06, dur * 0.3)
                    scoop = 1 + (prev_f0 / f0 - 1) * np.exp(-t / max(glide, 1e-3))
                else:
                    scoop = 1 - 0.03 * np.exp(-t / 0.05)
                vib_depth = 0.008 * np.minimum(t / 0.25, 1.0)  # delayed vibrato
                freq = f0 * scoop * (1 + vib_depth * np.sin(2 * np.pi * 5.5 * t))
                prev_f0 = f0
                prev_end = t0 + dur
                phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE

                # glottal-ish source: harmonics shaped by vowel formants
                formants, amps = _VOWEL_FORMANTS[_vowel_of(n.lyric_syllable)]
                tone = np.zeros(count)
                for h in range(1, 13):
                    hf = f0 * h
                    if hf > SAMPLE_RATE / 2:
                        break
                    # formant resonance gains for this harmonic
                    g = 0.06  # residual spectral tilt
                    for (fc, a) in zip(formants, amps):
                        bw = 90 + fc * 0.06
                        g += a * np.exp(-0.5 * ((hf - fc) / bw) ** 2)
                    tone += (g / h ** 0.7) * np.sin(h * phase)
                tone += 0.01 * rng.standard_normal(count)  # breathiness

                # consonant approximation: 25 ms noise burst at note start
                if _has_leading_consonant(n.lyric_syllable):
                    burst = min(int(0.025 * SAMPLE_RATE), count)
                    tone[:burst] += 0.12 * rng.standard_normal(burst) \
                        * np.linspace(1, 0, burst)

                attack = min(int(0.02 * SAMPLE_RATE), count)
                release = min(int(0.08 * SAMPLE_RATE), max(count - attack, 1))
                env = np.ones(count)
                env[:attack] = np.linspace(0, 1, attack)
                env[-release:] *= np.linspace(1, 0, release)
                out[i0:i0 + count] += (tone * env * (n.velocity / 127) * 0.5
                                       ).astype(np.float32)
                notes_rendered += 1

        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 1.0:
            out /= peak
        stereo = np.repeat(out[:, None], 2, axis=1)
        write_wav(out_path, stereo, SAMPLE_RATE)
        result.stem_path = out_path
        result.render_log.append(
            f"formant engine rendered {notes_rendered} notes to {out_path.name}")
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


class RecordingVoiceEngine(SingingVoiceEngine):
    """AI-voice simulation from a consented voice profile: takes a voiced
    segment of the profile's source recording and pitch-shifts it to every
    melody note (resampling-based, so timbre follows the singer's voice).
    Crude but genuinely 'sings' with the recorded voice's character. Requires
    a voice profile with consent — enforced at assignment time and re-checked
    here."""

    def __init__(self, profile) -> None:
        self.profile = profile

    def _load_source(self) -> tuple[np.ndarray, int, float] | None:
        """Returns (voiced segment mono, rate, fundamental_hz) or None."""
        from . import asset_repo
        from .audio_io import AudioReadError, read_audio
        from .sample_analysis import _estimate_pitch
        for rid in self.profile.source_recording_ids:
            asset = asset_repo.get_asset(rid)
            if asset is None or asset.is_missing:
                continue
            try:
                data, rate = read_audio(Path(asset.original_path))
            except AudioReadError:
                continue
            mono = data.mean(axis=1)
            note, freq = _estimate_pitch(mono, rate)
            if freq is None:
                continue
            # loudest ~0.4 s window = the sustained voiced part
            win = min(len(mono), int(0.4 * rate))
            if win < rate // 10:
                continue
            hop = max(1, (len(mono) - win) // 16)
            starts = range(0, max(len(mono) - win, 1), hop)
            best = max(starts, key=lambda s: float(np.abs(mono[s:s + win]).mean()))
            seg = mono[best:best + win].astype(np.float32)
            # loopable segment: fade edges to avoid clicks when tiling
            edge = max(int(0.01 * rate), 1)
            seg[:edge] *= np.linspace(0, 1, edge)
            seg[-edge:] *= np.linspace(1, 0, edge)
            return seg, rate, freq
        return None

    def render(self, project: SongProject, track: Track,
               out_path: Path) -> VocalRenderResult:
        if not self.profile.consent_confirmed:
            raise PermissionError(
                "voice profile has no confirmed consent — refusing to render")
        source = self._load_source()
        if source is None:
            result = MockSingingVoiceEngine().render(project, track, out_path)
            result.warnings.append(
                f"voice profile {self.profile.name!r}: no usable pitched "
                "source recording — fell back to the formant engine")
            return result
        seg, src_rate, src_freq = source

        result = VocalRenderResult(stem_path=None)
        total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
        out = np.zeros(total, dtype=np.float32)
        notes_rendered = 0
        # gather notes in time order for portamento/legato context
        seq: list[tuple[float, float, "object"]] = []
        for clip in track.clips:
            if clip.clip_type == "sample":
                continue
            for n in clip.note_events:
                t0 = timing.beats_to_seconds(project, clip.start_beat + n.start_beat)
                dur = timing.beats_to_seconds(project, n.duration_beats)
                seq.append((t0, dur, n))
        seq.sort(key=lambda x: x[0])

        # resample the source segment to the output rate once, then build the
        # PSOLA grain bank (formant-preserving pitch shifting: grains keep the
        # spectral envelope of the voice, so it doesn't chipmunk)
        if src_rate != SAMPLE_RATE:
            from .audio_io import resample_linear
            seg = resample_linear(seg[:, None], src_rate, SAMPLE_RATE)[:, 0]
        p0 = max(int(SAMPLE_RATE / src_freq), 8)
        grain_len = 2 * p0
        window = np.hanning(grain_len).astype(np.float32)
        marks = list(range(p0, len(seg) - grain_len, p0))
        if not marks:
            marks = [0]
            grain_len = min(grain_len, len(seg))
            window = np.hanning(grain_len).astype(np.float32)
        grains = [seg[m:m + grain_len] * window for m in marks]
        n_grains = len(grains)
        rng_g = np.random.default_rng(hash(track.id) & 0xFFFFFF)

        prev_freq: float | None = None
        prev_end = -1.0
        for t0, dur, n in seq:
            i0 = int(t0 * SAMPLE_RATE)
            count = min(int(dur * SAMPLE_RATE), total - i0)
            if count <= 0:
                continue
            target = _note_freq(n.midi_note)
            t = np.arange(count) / SAMPLE_RATE
            if prev_freq is not None and t0 - prev_end < 0.06:
                glide = min(0.07, dur * 0.3)
                freq = target + (prev_freq - target) * np.exp(-t / max(glide, 1e-3))
            else:
                freq = target * (1 - 0.04 * np.exp(-t / 0.04))  # scoop in
            vib = 1 + (0.010 * np.minimum(t / 0.3, 1.0)
                       * np.sin(2 * np.pi * 5.3 * t))
            freq = freq * vib

            # TD-PSOLA: place source grains at the target pitch period,
            # walking forward-and-back through the grain bank (natural motion,
            # no seams), with tiny jitter for realism
            note_buf = np.zeros(count + grain_len, dtype=np.float32)
            pos = 0
            gi = 0
            direction = 1
            while pos < count:
                g = grains[gi]
                note_buf[pos:pos + grain_len] += g[:min(grain_len, len(note_buf) - pos)]
                f = float(freq[min(pos, count - 1)])
                period = max(int(SAMPLE_RATE / max(f, 30.0)), 8)
                pos += period + rng_g.integers(-1, 2)
                gi += direction
                if gi >= n_grains - 1 or gi <= 0:
                    direction *= -1
                    gi = max(0, min(n_grains - 1, gi))
            note = note_buf[:count]

            attack = min(int(0.015 * SAMPLE_RATE), count)
            release = min(int(0.05 * SAMPLE_RATE), max(count - attack, 1))
            env = np.ones(count, dtype=np.float32)
            env[:attack] = np.linspace(0, 1, attack)
            env[-release:] *= np.linspace(1, 0, release)
            env *= 0.85 + 0.15 * np.sin(np.pi * np.minimum(t / max(dur, 1e-3), 1.0))
            out[i0:i0 + count] += note * env * (n.velocity / 127) * 0.8
            prev_freq = target
            prev_end = t0 + dur
            notes_rendered += 1

        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 1.0:
            out /= peak
        write_wav(out_path, np.repeat(out[:, None], 2, axis=1), SAMPLE_RATE)
        result.stem_path = out_path
        result.render_log.append(
            f"recording-voice engine ({self.profile.name!r}, source ≈"
            f"{src_freq:.0f} Hz) rendered {notes_rendered} notes")
        if notes_rendered == 0:
            result.warnings.append(
                f"vocal track {track.name!r} has no melody notes")
        result.alignment = build_lyrics_alignment(project, track)
        return result


def get_engine(engine_name: str = "mock", profile=None) -> SingingVoiceEngine:
    """Factory for singing engines. A consented voice profile with source
    recordings selects the recording-based engine; real neural engines
    register here later (Phase 23 contract)."""
    if profile is not None and profile.consent_confirmed \
            and profile.source_recording_ids:
        return RecordingVoiceEngine(profile)
    if engine_name == "mock":
        return MockSingingVoiceEngine()
    raise ValueError(f"unknown singing voice engine {engine_name!r} "
                     "(only 'mock' is available in v1)")


def _mix_recorded_takes(project: SongProject, track: Track,
                        stem_path: Path, result: VocalRenderResult) -> None:
    """Vocal tracks can carry sample clips (live-recorded takes). Mix them
    into the rendered vocal stem at their timeline position."""
    sample_clips = [c for c in track.clips if c.clip_type == "sample"]
    if not sample_clips:
        return
    import soundfile as sf

    from .render.sample_renderer import _render_clip
    data, rate = sf.read(str(stem_path), dtype="float32", always_2d=True)
    total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
    if len(data) < total:
        data = np.vstack([data, np.zeros((total - len(data), 2), np.float32)])
    for clip in sample_clips:
        _render_clip(project, clip, data, result.warnings)
    peak = float(np.max(np.abs(data)))
    if peak > 1.0:
        data /= peak
    write_wav(stem_path, data, SAMPLE_RATE)
    result.render_log.append(
        f"mixed {len(sample_clips)} recorded take(s) into {stem_path.name}")


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

    all_alignment: list[dict] = []
    from .midi_export import _safe_name
    for track in vocal_tracks:
        profile = None
        if track.voice_profile_id:
            from . import voice_profiles
            profile = voice_profiles.get_profile(track.voice_profile_id)
        engine = get_engine("mock", profile)
        fp = track_fingerprint(project, track)
        out_path = cfg.stems_dir / project.id / f"vocal_{_safe_name(track.name)}_{track.id[:8]}.wav"
        try:
            r = engine.render(project, track, out_path)
            _mix_recorded_takes(project, track, out_path, r)
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
