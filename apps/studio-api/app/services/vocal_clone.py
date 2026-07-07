"""CloneSingingEngine: neural voice cloning that sings the actual lyrics.

Pipeline per lyric line:
1. XTTS-v2 (Coqui) zero-shot clones the voice from the profile's source
   recording and SPEAKS the line — real words, the user's voice timbre.
2. The spoken line is time-stretched to the melody span and pitch-mapped
   note-by-note (granular, formant-friendly; unvoiced consonants pass
   through untouched so words stay crisp).
3. Lines are placed on the timeline at their notes' positions.

Synthesized lines are cached in analysis-cache/tts/ keyed by
(text, voice profile, engine version) so re-renders are fast.

Consent: the engine refuses profiles without consent_confirmed. Model:
XTTS-v2 (Coqui Public Model License — non-commercial). GPU used when
available.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import numpy as np

from ..config import get_config
from ..models.song import SongProject, Track
from . import timing
from .audio_io import read_audio, resample_linear, write_wav
from .render.soundfont_renderer import SAMPLE_RATE
from .vocal_engine import (SingingVoiceEngine, VocalRenderResult,
                           _note_freq, build_lyrics_alignment)

log = logging.getLogger(__name__)

CLONE_ENGINE_VERSION = "1"

_tts_model = None
_tts_failed: str | None = None


def clone_engine_available() -> bool:
    try:
        import torch  # noqa: F401
        import TTS  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _get_tts():
    global _tts_model, _tts_failed
    if _tts_model is not None:
        return _tts_model
    if _tts_failed:
        raise RuntimeError(_tts_failed)
    import os
    os.environ.setdefault("COQUI_TOS_AGREED", "1")
    try:
        import torch
        from TTS.api import TTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info("loading XTTS-v2 on %s (first run downloads ~1.8 GB)…", device)
        _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        return _tts_model
    except Exception as e:  # noqa: BLE001
        _tts_failed = f"XTTS unavailable: {e}"
        raise RuntimeError(_tts_failed) from e


_XTTS_LANGS = {"en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl",
               "cs", "ar", "zh-cn", "hu", "ko", "ja", "hi"}


def _syllable_count(text: str) -> int:
    n = 0
    for word in re.findall(r"[A-Za-z']+", text):
        groups = re.findall(r"[^aeiouy]*[aeiouy]+(?:[^aeiouy]+$)?", word,
                            re.IGNORECASE)
        n += max(1, len(groups))
    return max(n, 1)


def _lines_with_notes(project: SongProject, track: Track):
    """Pair each lyric line with the melody notes that sing it (same
    consumption rule as the karaoke alignment)."""
    notes = []
    for clip in track.clips:
        if clip.clip_type == "sample":
            continue
        for n in clip.note_events:
            start = timing.beats_to_seconds(project, clip.start_beat + n.start_beat)
            notes.append({"start": start,
                          "end": start + timing.beats_to_seconds(project, n.duration_beats),
                          "freq": _note_freq(n.midi_note),
                          "section_id": clip.section_id})
    notes.sort(key=lambda x: x["start"])
    out = []
    i = 0
    for line in project.lyrics.lines:
        take = _syllable_count(line.text)
        pool = notes[i:]
        if line.section_id:
            pool = [x for x in pool if x["section_id"] in (line.section_id, "")]
        chunk = pool[:take]
        if chunk:
            out.append((line.text, chunk))
            i += len(chunk)
    return out


def _tts_line(text: str, speaker_wav: Path, language: str) -> tuple[np.ndarray, int]:
    """Cloned speech for one line, cached on disk."""
    cfg = get_config()
    cache_dir = cfg.analysis_cache_dir / "tts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(
        f"{CLONE_ENGINE_VERSION}:{language}:{speaker_wav}:{text}".encode()).hexdigest()[:24]
    cached = cache_dir / f"{key}.wav"
    if cached.exists():
        data, rate = read_audio(cached)
        return data[:, 0], rate
    tts = _get_tts()
    wav = tts.tts(text=text, speaker_wav=str(speaker_wav), language=language)
    audio = np.asarray(wav, dtype=np.float32)
    rate = 24000  # XTTS output rate
    write_wav(cached, audio[:, None], rate)
    return audio, rate


def _frame_f0(audio: np.ndarray, rate: int, frame: int = 1024,
              hop: int = 256) -> np.ndarray:
    """Per-frame fundamental (0 = unvoiced)."""
    n_frames = max((len(audio) - frame) // hop + 1, 1)
    f0 = np.zeros(n_frames)
    lo, hi = int(rate / 500), int(rate / 60)
    for k in range(n_frames):
        seg = audio[k * hop:k * hop + frame]
        if len(seg) < frame or np.abs(seg).max() < 0.02:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, mode="full")[len(seg) - 1:]
        if hi >= len(ac):
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.30 * ac[0]:
            f0[k] = rate / lag
    return f0


def _sing_line(spoken: np.ndarray, rate: int, line_notes: list[dict],
               line_dur: float, line_start: float) -> np.ndarray:
    """Time-stretch spoken audio to the melody span and pitch-map voiced
    frames to the note frequencies (44.1 kHz output)."""
    if rate != SAMPLE_RATE:
        spoken = resample_linear(spoken[:, None], rate, SAMPLE_RATE)[:, 0]
    n_in = len(spoken)
    n_out = max(int(line_dur * SAMPLE_RATE), 1)
    if n_in < 512:
        return np.zeros(n_out, dtype=np.float32)

    hop = 256
    f0 = _frame_f0(spoken, SAMPLE_RATE)

    def target_freq(t_abs: float) -> float:
        for nd in line_notes:
            if nd["start"] - 0.02 <= t_abs < nd["end"] + 0.02:
                return nd["freq"]
        return line_notes[-1]["freq"] if line_notes else 220.0

    block = 4096
    fade = 512
    step = block - fade
    win = np.ones(block, dtype=np.float32)
    win[:fade] = np.linspace(0, 1, fade)
    win[-fade:] = np.linspace(1, 0, fade)
    out = np.zeros(n_out + block, dtype=np.float32)
    norm = np.zeros(n_out + block, dtype=np.float32)
    stretch = n_in / n_out  # input samples per output sample

    pos = 0
    while pos < n_out:
        in_center = pos * stretch
        k = int(in_center // hop)
        src_f0 = f0[min(k, len(f0) - 1)] if len(f0) else 0.0
        if src_f0 > 0:
            tgt = target_freq(line_start + pos / SAMPLE_RATE)
            ratio = float(np.clip(tgt / src_f0, 0.35, 3.0))
        else:
            ratio = 1.0  # consonants/breaths untouched → crisp words
        idx = in_center + (np.arange(block) - block / 2) * ratio
        idx = np.clip(idx, 0, n_in - 1.001)
        i0 = idx.astype(np.int64)
        frac = (idx - i0).astype(np.float32)
        grain = spoken[i0] * (1 - frac) + spoken[np.minimum(i0 + 1, n_in - 1)] * frac
        out[pos:pos + block] += grain * win
        norm[pos:pos + block] += win
        pos += step
    norm = np.maximum(norm, 1e-6)
    return (out[:n_out] / norm[:n_out]).astype(np.float32)


class CloneSingingEngine(SingingVoiceEngine):
    def __init__(self, profile) -> None:
        self.profile = profile

    def _speaker_wav(self) -> Path | None:
        """Reference audio for cloning (decoded to wav if needed)."""
        from . import asset_repo
        cfg = get_config()
        for rid in self.profile.source_recording_ids:
            asset = asset_repo.get_asset(rid)
            if asset is None or asset.is_missing:
                continue
            src = Path(asset.original_path)
            if src.suffix.lower() == ".wav":
                return src
            ref = cfg.analysis_cache_dir / "tts" / f"ref_{rid}.wav"
            if ref.exists():
                return ref
            try:
                data, rate = read_audio(src)
                ref.parent.mkdir(parents=True, exist_ok=True)
                write_wav(ref, data, rate)
                return ref
            except Exception:  # noqa: BLE001
                continue
        return None

    def render(self, project: SongProject, track: Track,
               out_path: Path) -> VocalRenderResult:
        if not self.profile.consent_confirmed:
            raise PermissionError(
                "voice profile has no confirmed consent — refusing to render")
        result = VocalRenderResult(stem_path=None)
        speaker = self._speaker_wav()
        if speaker is None:
            raise RuntimeError("no usable source recording on the profile")

        language = (project.lyrics.language or "en").lower()
        if language not in _XTTS_LANGS:
            result.warnings.append(f"language {language!r} not supported by "
                                   "XTTS — singing in English")
            language = "en"

        pairs = _lines_with_notes(project, track)
        total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
        out = np.zeros(total, dtype=np.float32)
        sung = 0
        for text, line_notes in pairs:
            try:
                spoken, rate = _tts_line(text, speaker, language)
            except Exception as e:  # noqa: BLE001
                result.warnings.append(f"line {text[:30]!r}: TTS failed ({e})")
                continue
            line_start = line_notes[0]["start"]
            line_dur = max(line_notes[-1]["end"] - line_start, 0.3)
            sung_line = _sing_line(spoken, rate, line_notes, line_dur, line_start)
            i0 = int(line_start * SAMPLE_RATE)
            seglen = min(len(sung_line), total - i0)
            if seglen > 0:
                edge = min(int(0.02 * SAMPLE_RATE), seglen)
                sung_line[:edge] *= np.linspace(0, 1, edge)
                sung_line[seglen - edge:seglen] *= np.linspace(1, 0, edge)
                out[i0:i0 + seglen] += sung_line[:seglen]
                sung += 1

        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 0.005:
            out *= 0.85 / peak
        write_wav(out_path, np.repeat(out[:, None], 2, axis=1), SAMPLE_RATE)
        result.stem_path = out_path
        result.render_log.append(
            f"clone-singing engine (XTTS, voice {self.profile.name!r}) sang "
            f"{sung}/{len(pairs)} lyric lines")
        if sung == 0:
            result.warnings.append(
                "no lines could be sung — check lyrics + melody exist "
                "(Lyrics tab → 'Sing these lyrics')")
        result.alignment = build_lyrics_alignment(project, track)
        return result
