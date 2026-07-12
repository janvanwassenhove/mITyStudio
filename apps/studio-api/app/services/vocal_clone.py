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

CLONE_ENGINE_VERSION = "2"

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


from .lyric_text import syllable_count as _syllable_count  # noqa: E402


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
                          "syl": n.lyric_syllable,
                          "section_id": clip.section_id})
    notes.sort(key=lambda x: x["start"])

    def consume(use_sections: bool):
        out = []
        full = 0
        used = [False] * len(notes)
        for line in project.lyrics.lines:
            if not line.text.strip():
                continue   # blank lyric line — nothing to sing
            take = _syllable_count(line.text)
            chunk = []
            for j, nd in enumerate(notes):
                if len(chunk) >= take:
                    break
                if used[j]:
                    continue
                if use_sections and line.section_id \
                        and nd["section_id"] not in (line.section_id, ""):
                    continue
                chunk.append(nd)
                used[j] = True
            if chunk:
                out.append((line.text, chunk))
                if len(chunk) >= take * 0.6:
                    full += 1
        return out, full

    strict, full_strict = consume(True)
    # section-aware matching first; when lyric section ids don't line up with
    # the melody clips (e.g. a whole sheet assigned to one section) most of
    # the song would fall silent or cram — fall back to sequential matching
    total = sum(1 for l in project.lyrics.lines if l.text.strip())
    if total and full_strict < total * 0.75:
        loose, full_loose = consume(False)
        if full_loose > full_strict:
            log.warning("lyric sections don't match melody sections "
                        "(%d/%d lines well-matched) — singing sequentially",
                        full_strict, total)
            return loose
    return strict


def _tts_line(text: str, speaker_wavs: list[Path],
              language: str) -> tuple[np.ndarray, int, Path]:
    """Cloned speech for one line, cached on disk. Multiple reference
    recordings improve the clone's fidelity. Returns (audio, rate, cache
    path) — the path also keys the forced-alignment cache."""
    cfg = get_config()
    cache_dir = cfg.analysis_cache_dir / "tts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    refs = ";".join(str(p) for p in speaker_wavs)
    key = hashlib.sha256(
        f"{CLONE_ENGINE_VERSION}:{language}:{refs}:{text}".encode()).hexdigest()[:24]
    cached = cache_dir / f"{key}.wav"
    if cached.exists():
        data, rate = read_audio(cached)
        return data[:, 0], rate, cached
    tts = _get_tts()
    wav = tts.tts(text=text,
                  speaker_wav=[str(p) for p in speaker_wavs],
                  language=language)
    audio = np.asarray(wav, dtype=np.float32)
    rate = 24000  # XTTS output rate
    write_wav(cached, audio[:, None], rate)
    return audio, rate, cached


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


def _trim_silence(audio: np.ndarray, rate: int,
                  thresh: float = 0.015) -> np.ndarray:
    loud = np.flatnonzero(np.abs(audio) > thresh)
    if not loud.size:
        return audio
    pad = int(0.02 * rate)
    return audio[max(loud[0] - pad, 0):min(loud[-1] + pad, len(audio))]


def _syllable_cuts(spoken: np.ndarray, rate: int,
                   syllables: list[str]) -> list[int]:
    """Sample indices of syllable boundaries (len = n_syllables + 1).

    Energy-valley boundaries near the proportional positions predicted from
    syllable text weights — valleys snap the cuts to the real pauses between
    syllables so segments contain whole phonemes."""
    n = len(syllables)
    if n <= 1 or len(spoken) < 256:
        return [0, len(spoken)]
    weights = np.array([len(s) + 1.5 for s in syllables], dtype=np.float64)
    targets = np.cumsum(weights)[:-1] / weights.sum() * len(spoken)

    hop = 128
    frames = len(spoken) // hop
    env = np.abs(spoken[:frames * hop]).reshape(frames, hop).mean(axis=1)
    k = 9
    env = np.convolve(env, np.ones(k) / k, mode="same")

    cuts = [0]
    for t in targets:
        f = int(t // hop)
        radius = max(int(0.06 * rate / hop), 2)
        lo = max(f - radius, cuts[-1] // hop + 1)
        hi = min(f + radius, frames - 1)
        if hi <= lo:
            cut = int(t)
        else:
            cut = (lo + int(np.argmin(env[lo:hi]))) * hop  # nearest valley
        cuts.append(max(cut, cuts[-1] + hop))
    cuts.append(len(spoken))
    return cuts


def _syllable_segments(spoken: np.ndarray, rate: int,
                       syllables: list[str]) -> list[np.ndarray]:
    cuts = _syllable_cuts(spoken, rate, syllables)
    return [spoken[cuts[i]:cuts[i + 1]] for i in range(len(cuts) - 1)]


def _stretch_pitch_segment(seg: np.ndarray, n_out: int, tgt_freq: float | None,
                           vibrato: bool) -> np.ndarray:
    """Stretch one syllable segment to its note length; map voiced frames to
    the note frequency (None = rap: keep natural pitch). Unvoiced audio
    passes through pitch-untouched so consonants stay crisp."""
    n_in = len(seg)
    out = np.zeros(n_out, dtype=np.float32)
    if n_in < 64 or n_out < 64:
        return out
    hop = 256
    f0 = _frame_f0(seg, SAMPLE_RATE, frame=min(1024, n_in), hop=hop)

    block = 2048
    fade = 384
    step = block - fade
    win = np.ones(block, dtype=np.float32)
    win[:fade] = np.linspace(0, 1, fade)
    win[-fade:] = np.linspace(1, 0, fade)
    buf = np.zeros(n_out + block, dtype=np.float32)
    norm = np.zeros(n_out + block, dtype=np.float32)
    stretch = n_in / n_out

    pos = 0
    while pos < n_out:
        in_center = pos * stretch
        k = int(in_center // hop)
        src_f0 = f0[min(k, len(f0) - 1)] if len(f0) else 0.0
        if tgt_freq is not None and src_f0 > 0:
            t = pos / SAMPLE_RATE
            # glide into the note over 35 ms, delayed vibrato on long notes
            glide = 1 - 0.06 * np.exp(-t / 0.035)
            vib = 1.0
            if vibrato and n_out > int(0.35 * SAMPLE_RATE):
                vib = 1 + 0.02 * min(t / 0.25, 1.0) * np.sin(2 * np.pi * 5.4 * t)
            ratio = float(np.clip(tgt_freq * glide * vib / src_f0, 0.35, 3.0))
        else:
            ratio = 1.0
        idx = in_center + (np.arange(block) - block / 2) * ratio
        idx = np.clip(idx, 0, n_in - 1.001)
        i0 = idx.astype(np.int64)
        frac = (idx - i0).astype(np.float32)
        grain = seg[i0] * (1 - frac) + seg[np.minimum(i0 + 1, n_in - 1)] * frac
        buf[pos:pos + block] += grain * win
        norm[pos:pos + block] += win
        pos += step
    norm = np.maximum(norm, 1e-6)
    return (buf[:n_out] / norm[:n_out]).astype(np.float32)


def _map_syllable_frames(a: int, b: int, span: int, rng) -> np.ndarray:
    """Frame indices warping one syllable onto its note. Short notes compress
    linearly; SUSTAINED notes keep onset/coda at natural speech rate and
    ping-pong-loop the vowel core with jitter — removing the slow-motion
    vowel artifact of stretching speech."""
    span_in = max(b - a, 1)
    if span <= span_in + 2:
        return np.clip(np.linspace(a, b - 1, span).astype(np.int64), a, b - 1)
    onset = min(span_in // 3 + 1, span // 4)
    coda = min(max(span_in // 4, 1), span // 4)
    core0 = a + onset
    core1 = max(b - coda, core0 + 2)
    core_len = core1 - core0
    mid = span - onset - coda
    period = max(2 * (core_len - 1), 1)
    k = np.arange(mid)
    tri = period / 2 - np.abs((k % period) - period / 2)
    jit = rng.integers(-1, 2, size=mid)
    core = np.clip(core0 + tri.astype(np.int64) + jit, core0, core1 - 1)
    return np.concatenate([np.arange(a, a + onset), core,
                           np.arange(b - coda, b)]).astype(np.int64)


# vocal delivery profiles: vibrato depth+rate, breathiness (aperiodicity
# boost), gain, portamento overshoot, timing feel (seconds; + = laid back,
# - = pushing ahead). User-facing styles (sing/soft/powerful/rap) come from
# Track.vocal_style; the genre profiles below are auto-selected from the
# project's style when the track uses the default "sing".
_STYLES = {
    "sing":     {"vib": 0.018, "vib_rate": 5.3, "breath": 0.0,  "gain": 1.0,
                 "overshoot": 0.06, "feel": 0.0},
    "soft":     {"vib": 0.010, "vib_rate": 5.0, "breath": 0.22, "gain": 0.85,
                 "overshoot": 0.04, "feel": 0.012},
    "powerful": {"vib": 0.028, "vib_rate": 5.6, "breath": 0.0,  "gain": 1.12,
                 "overshoot": 0.09, "feel": -0.008},
    "ballad":   {"vib": 0.024, "vib_rate": 5.0, "breath": 0.14, "gain": 0.95,
                 "overshoot": 0.05, "feel": 0.02},
    "rock":     {"vib": 0.022, "vib_rate": 5.8, "breath": 0.04, "gain": 1.10,
                 "overshoot": 0.10, "feel": -0.010},
    "jazz":     {"vib": 0.016, "vib_rate": 5.0, "breath": 0.10, "gain": 0.92,
                 "overshoot": 0.03, "feel": 0.025},
    "edm":      {"vib": 0.008, "vib_rate": 5.5, "breath": 0.06, "gain": 1.05,
                 "overshoot": 0.03, "feel": 0.0},
    "country":  {"vib": 0.020, "vib_rate": 5.4, "breath": 0.08, "gain": 1.0,
                 "overshoot": 0.12, "feel": 0.008},
}

# genre keyword → delivery profile (first match wins, checked in order)
_GENRE_STYLE = [
    (("ballad", "acoustic", "folk", "singer-songwriter", "lullaby"), "ballad"),
    (("punk", "metal", "hard rock", "grunge", "rock"), "rock"),
    (("jazz", "blues", "soul", "swing", "bossa"), "jazz"),
    (("edm", "house", "techno", "trance", "dance", "electro", "dubstep"), "edm"),
    (("country", "americana", "bluegrass"), "country"),
    (("r&b", "rnb", "neo-soul", "lofi", "chill", "ambient"), "soft"),
    (("gospel", "anthem", "power", "epic"), "powerful"),
]


def resolve_delivery(track_style: str, project_style: str | None) -> str:
    """The delivery profile for a track: explicit styles win; the default
    'sing' is refined by the project's genre so a ballad breathes and a rock
    song pushes without the user configuring anything."""
    if track_style and track_style not in ("sing", "rap"):
        return track_style if track_style in _STYLES else "sing"
    if track_style == "rap":
        return "sing"   # rap keeps natural pitch; delivery params barely used
    genre = (project_style or "").lower()
    for keywords, style in _GENRE_STYLE:
        if any(k in genre for k in keywords):
            return style
    return "sing"


def _world_sing_line(spoken: np.ndarray, rate: int, line_notes: list[dict],
                     line_dur: float, line_start: float,
                     rap: bool = False, style: str = "sing",
                     layout: dict | None = None) -> np.ndarray:
    """WORLD-vocoder singing resynthesis (the speech-to-singing technique):
    the whole line is decomposed into pitch / spectral envelope /
    aperiodicity, time-warped so each syllable spans exactly its note, and
    resynthesized with one CONTINUOUS musical pitch curve — portamento
    between notes, delayed vibrato, slight overshoot, phrase-end fall,
    human micro-drift. Formants (the voice's identity) are untouched.

    `layout` (from vocal_align.align_syllables, computed on the SAME trimmed
    audio) provides phoneme-accurate syllable cuts + vowel onsets; without it
    the energy-valley heuristic is used. With vowel onsets, each syllable's
    consonants are placed AHEAD of the note so the vowel lands on the beat —
    how real singers phrase.
    """
    import pyworld

    spoken = _trim_silence(spoken, rate)
    n_out_samples = max(int(line_dur * SAMPLE_RATE), 1)
    if len(spoken) < 512 or not line_notes:
        return np.zeros(n_out_samples, dtype=np.float32)

    st = _STYLES.get(style, _STYLES["sing"])
    fp_ms = 5.0
    x = spoken.astype(np.float64)
    f0_in, sp, ap = pyworld.wav2world(x, rate, frame_period=fp_ms)
    n_in = len(f0_in)
    if n_in < 4:
        return np.zeros(n_out_samples, dtype=np.float32)
    med_f0 = float(np.median(f0_in[f0_in > 0])) if np.any(f0_in > 0) else 180.0

    # LEGATO: bridge micro-gaps between a line's notes (humanized melodies
    # leave small rests between syllables; silencing each one made the voice
    # choppy — measured voiced_ratio 0.27). Singers connect syllables within
    # a phrase; only real rests (>180 ms) stay silent. Rap keeps its gaps.
    if not rap and len(line_notes) > 1:
        bridged = []
        for i, nd in enumerate(line_notes):
            nd = dict(nd)
            if i + 1 < len(line_notes):
                gap = line_notes[i + 1]["start"] - nd["end"]
                if 0 < gap < 0.18:
                    nd["end"] = line_notes[i + 1]["start"]
            bridged.append(nd)
        line_notes = bridged

    syllables = [nd.get("syl") or "la" for nd in line_notes]
    vowel_at: list[int] | None = None
    if layout and len(layout.get("cuts", [])) == len(line_notes) + 1:
        cuts = [min(int(c), len(spoken)) for c in layout["cuts"]]
        vowel_at = [int(v) for v in layout["vowel_at"]]
    else:
        cuts = _syllable_cuts(spoken, rate, syllables)
    # input frame boundary per syllable
    in_bounds = [min(int(c / rate * 1000 / fp_ms), n_in - 1) for c in cuts]
    if len(in_bounds) - 1 != len(line_notes):
        in_bounds = list(np.linspace(0, n_in - 1, len(line_notes) + 1).astype(int))
        vowel_at = None
    # vowel onset per syllable in input frames (consonant lead-in anchor)
    vowel_f = None
    if vowel_at is not None:
        vowel_f = [min(max(int(v / rate * 1000 / fp_ms), in_bounds[i]),
                       max(in_bounds[i + 1] - 1, in_bounds[i]))
                   for i, v in enumerate(vowel_at)]

    fp_s = fp_ms / 1000.0
    n_out = max(int(line_dur / fp_s), 2)
    frame_map = np.zeros(n_out, dtype=np.int64)
    f0_out = np.zeros(n_out)
    audible = np.zeros(n_out, dtype=bool)

    rng = np.random.default_rng(len(spoken))
    drift = np.cumsum(rng.standard_normal(n_out)) * 0.0015
    drift -= np.linspace(drift[0], drift[-1], n_out)  # zero-mean wander

    feel_frames = int(st.get("feel", 0.0) / fp_s)
    prev_freq: float | None = None
    for i, nd in enumerate(line_notes):
        t0 = int((nd["start"] - line_start) / fp_s) + feel_frames
        t1 = int((nd["end"] - line_start) / fp_s) + feel_frames
        t0 = max(min(t0, n_out - 1), 0)
        t1 = max(min(t1, n_out), t0 + 1)
        span = t1 - t0
        a, b = in_bounds[i], max(in_bounds[i + 1], in_bounds[i] + 1)
        # with a known vowel onset, the consonants LEAD the beat at natural
        # speech rate and the vowel lands exactly on the note start
        if vowel_f is not None and vowel_f[i] > a and t0 > 0:
            lead = min(vowel_f[i] - a, int(0.12 / fp_s), t0)
            if lead > 0:
                lf = np.linspace(a, vowel_f[i] - 1, lead).astype(np.int64)
                frame_map[t0 - lead:t0] = np.clip(lf, 0, n_in - 1)
                audible[t0 - lead:t0] = True
            a = vowel_f[i]
        # time-warp: onset/coda natural, vowel core looped on sustains
        frame_map[t0:t1] = np.clip(
            _map_syllable_frames(a, max(b, a + 1), span, rng), 0, n_in - 1)
        audible[t0:t1] = True

        target = nd["freq"]
        is_last = i == len(line_notes) - 1
        tt = np.arange(span) * fp_s
        curve = np.full(span, float(target))
        if prev_freq is not None:
            # portamento from the previous note over ~70 ms, slight overshoot
            gl = np.exp(-tt / 0.05)
            curve = target + (prev_freq - target) * gl
            curve += (target - prev_freq) * st["overshoot"] \
                * np.exp(-((tt - 0.09) / 0.03) ** 2)
        else:
            curve = target * (1 - 0.05 * np.exp(-tt / 0.05))  # scoop in
        note_dur = span * fp_s
        if note_dur > 0.3:
            vib_on = np.clip((tt - 0.4 * note_dur) / (0.25 * note_dur), 0, 1)
            curve *= 1 + st["vib"] * vib_on * np.sin(
                2 * np.pi * st.get("vib_rate", 5.3) * tt)
        if is_last and span > 8:
            tail = max(int(span * 0.25), 2)
            curve[-tail:] *= np.linspace(1.0, 0.975, tail)  # phrase-end fall
        f0_out[t0:t1] = curve
        prev_freq = target

    # fill gaps between notes by holding the boundary frame (silenced later)
    for t in range(n_out):
        if not audible[t]:
            frame_map[t] = frame_map[t - 1] if t > 0 else 0

    src_f0 = f0_in[frame_map]
    voiced = src_f0 > 0
    if rap:
        f0_final = np.where(voiced, src_f0, 0.0)   # natural speech pitch
    else:
        f0_final = np.where(voiced, f0_out * (1 + drift), 0.0)
        # keep the melody in a comfortable register for the voice
        vv = f0_final[voiced]
        if vv.size and np.median(vv) > med_f0 * 1.9:
            f0_final[voiced] = vv / 2
        elif vv.size and np.median(vv) < med_f0 * 0.45:
            f0_final[voiced] = vv * 2

    sp_out = np.ascontiguousarray(sp[frame_map])
    ap_out = np.ascontiguousarray(ap[frame_map])
    if st["breath"] > 0:   # airy delivery: raise aperiodicity on voiced frames
        ap_out = np.ascontiguousarray(np.minimum(ap_out + st["breath"], 1.0))
    y = pyworld.synthesize(np.ascontiguousarray(f0_final), sp_out, ap_out,
                           rate, fp_ms).astype(np.float32)
    y *= st["gain"]

    # silence the inter-note gaps with short fades (bre. pauses)
    env = np.ones(len(y), dtype=np.float32)
    spf = int(rate * fp_s)
    fade = max(spf, 1)
    t = 0
    while t < n_out:
        if not audible[t]:
            g0 = t
            while t < n_out and not audible[t]:
                t += 1
            s0, s1 = g0 * spf, min(t * spf, len(y))
            if s1 > s0:
                env[s0:s1] = 0
                if s0 - fade >= 0:
                    env[s0 - fade:s0] *= np.linspace(1, 0, fade)
                if s1 + fade <= len(y):
                    env[s1:s1 + fade] *= np.linspace(0, 1, fade)
        else:
            t += 1
    y *= env

    if rate != SAMPLE_RATE:
        y = resample_linear(y[:, None], rate, SAMPLE_RATE)[:, 0]
    if len(y) < n_out_samples:
        y = np.concatenate([y, np.zeros(n_out_samples - len(y), np.float32)])
    return y[:n_out_samples]


def _sing_line(spoken: np.ndarray, rate: int, line_notes: list[dict],
               line_dur: float, line_start: float,
               rap: bool = False, style: str = "sing",
               layout: dict | None = None) -> np.ndarray:
    """Sing one spoken line onto its notes. WORLD resynthesis when available
    (smooth, human), granular fallback otherwise."""
    try:
        return _world_sing_line(spoken, rate, line_notes, line_dur,
                                line_start, rap, style, layout)
    except Exception as e:  # noqa: BLE001
        log.warning("WORLD resynthesis failed (%s) — granular fallback", e)
        return _granular_sing_line(spoken, rate, line_notes, line_dur,
                                   line_start, rap)


def _breath(rate: int, seed: int) -> np.ndarray:
    """A soft inhale: shaped noise, ~180 ms."""
    n = int(0.18 * rate)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n).astype(np.float32)
    # gentle band emphasis via first-order smoothing (removes harsh hiss)
    smooth = np.convolve(noise, np.ones(8, np.float32) / 8, mode="same")
    env = np.hanning(n).astype(np.float32) ** 1.5
    return 0.02 * smooth * env


def _granular_sing_line(spoken: np.ndarray, rate: int, line_notes: list[dict],
                        line_dur: float, line_start: float,
                        rap: bool = False) -> np.ndarray:
    """Fallback: per-syllable granular stretch + pitch-map."""
    if rate != SAMPLE_RATE:
        spoken = resample_linear(spoken[:, None], rate, SAMPLE_RATE)[:, 0]
    spoken = _trim_silence(spoken, SAMPLE_RATE)
    n_out = max(int(line_dur * SAMPLE_RATE), 1)
    if len(spoken) < 512 or not line_notes:
        return np.zeros(n_out, dtype=np.float32)

    syllables = [nd.get("syl") or "la" for nd in line_notes]
    segments = _syllable_segments(spoken, SAMPLE_RATE, syllables)
    out = np.zeros(n_out, dtype=np.float32)
    for nd, seg in zip(line_notes, segments):
        note_len = max(int((nd["end"] - nd["start"]) * SAMPLE_RATE), 64)
        sung = _stretch_pitch_segment(
            seg, note_len, None if rap else nd["freq"], vibrato=not rap)
        i0 = int((nd["start"] - line_start) * SAMPLE_RATE)
        if i0 < 0 or i0 >= n_out:
            continue
        seglen = min(len(sung), n_out - i0)
        # short crossfade edges to avoid clicks between syllables
        edge = min(int(0.008 * SAMPLE_RATE), seglen // 2)
        if edge > 0:
            sung[:edge] *= np.linspace(0, 1, edge)
            sung[seglen - edge:seglen] *= np.linspace(1, 0, edge)
        out[i0:i0 + seglen] += sung[:seglen]
    return out


class CloneSingingEngine(SingingVoiceEngine):
    def __init__(self, profile) -> None:
        self.profile = profile

    def _speaker_wavs(self) -> list[Path]:
        """ALL reference recordings for cloning (decoded to wav if needed) —
        more reference audio → better voice fidelity."""
        from . import asset_repo
        cfg = get_config()
        refs: list[Path] = []
        for rid in self.profile.source_recording_ids:
            asset = asset_repo.get_asset(rid)
            if asset is None or asset.is_missing:
                continue
            src = Path(asset.original_path)
            if src.suffix.lower() == ".wav":
                refs.append(src)
                continue
            ref = cfg.analysis_cache_dir / "tts" / f"ref_{rid}.wav"
            if ref.exists():
                refs.append(ref)
                continue
            try:
                data, rate = read_audio(src)
                ref.parent.mkdir(parents=True, exist_ok=True)
                write_wav(ref, data, rate)
                refs.append(ref)
            except Exception:  # noqa: BLE001
                continue
        return refs

    def render(self, project: SongProject, track: Track,
               out_path: Path) -> VocalRenderResult:
        if not self.profile.consent_confirmed:
            raise PermissionError(
                "voice profile has no confirmed consent — refusing to render")
        result = VocalRenderResult(stem_path=None)
        speakers = self._speaker_wavs()
        if not speakers:
            raise RuntimeError("no usable source recording on the profile")

        language = (project.lyrics.language or "en").lower()
        if language not in _XTTS_LANGS:
            result.warnings.append(f"language {language!r} not supported by "
                                   "XTTS — singing in English")
            language = "en"

        pairs = _lines_with_notes(project, track)
        total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
        style = getattr(track, "vocal_style", "sing") or "sing"
        rap = style == "rap"
        delivery = resolve_delivery(style, project.style)
        if delivery != style and not rap:
            result.render_log.append(
                f"delivery profile {delivery!r} (from genre {project.style!r})")

        # sing each line, keep (timeline start, audio) — placed onto the
        # timeline only AFTER the (optional) RVC stage
        segments: list[tuple[int, np.ndarray]] = []
        aligned_lines = 0
        prev_end = -10.0
        for text, line_notes in pairs:
            try:
                spoken, rate, tts_path = _tts_line(text, speakers, language)
            except Exception as e:  # noqa: BLE001
                result.warnings.append(f"line {text[:30]!r}: TTS failed ({e})")
                continue
            # phoneme-accurate syllable layout (forced alignment) — computed
            # on the trimmed audio, exactly what _world_sing_line warps
            spoken = _trim_silence(spoken, rate)
            layout = None
            if not rap and len(spoken) > 512:
                syls = [nd.get("syl") or "la" for nd in line_notes]
                try:
                    from .vocal_align import align_syllables
                    layout = align_syllables(
                        spoken, rate, text, syls,
                        cache_path=tts_path.with_name(
                            f"{tts_path.stem}.align{len(syls)}.json"))
                except Exception as e:  # noqa: BLE001
                    log.debug("alignment skipped for %r: %s", text[:30], e)
                if layout:
                    aligned_lines += 1
            line_start = line_notes[0]["start"]
            line_dur = max(line_notes[-1]["end"] - line_start, 0.3)
            sung_line = _sing_line(spoken, rate, line_notes, line_dur,
                                   line_start, rap=rap, style=delivery,
                                   layout=layout)
            i0 = int(line_start * SAMPLE_RATE)
            seglen = min(len(sung_line), total - i0)
            if seglen > 0:
                sl = np.array(sung_line[:seglen], dtype=np.float32)
                edge = min(int(0.02 * SAMPLE_RATE), seglen)
                sl[:edge] *= np.linspace(0, 1, edge)
                sl[seglen - edge:seglen] *= np.linspace(1, 0, edge)
                segments.append((i0, sl))
                # a soft inhale before the phrase when there is room for one
                if not rap and line_start - prev_end > 0.45:
                    b = _breath(SAMPLE_RATE, i0)
                    bp = i0 - int(0.24 * SAMPLE_RATE)
                    if bp >= 0:
                        segments.append((bp, b))
                prev_end = line_notes[-1]["end"]
        sung = sum(1 for _, s in segments if len(s) > int(0.2 * SAMPLE_RATE))

        # final fidelity stage: trained RVC model of this exact voice. RVC is
        # run on the DENSE concatenation of sung lines — feeding it the sparse
        # timeline-length mix makes it collapse to silence.
        from .rvc_convert import rvc_model_ready
        placed = segments
        if sung and rvc_model_ready(self.profile):
            converted = self._rvc_convert_segments(segments, result,
                                                   autotune=not rap)
            if converted is not None:
                placed = converted
                result.render_log.append(
                    f"RVC conversion applied (trained {self.profile.name!r} model)")

        out = np.zeros(total, dtype=np.float32)
        for i0, sl in placed:
            n = min(len(sl), total - i0)
            if n > 0:
                out[i0:i0 + n] += sl[:n]
        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 0.005:
            out *= 0.85 / peak
        write_wav(out_path, np.repeat(out[:, None], 2, axis=1), SAMPLE_RATE)
        result.stem_path = out_path
        result.render_log.append(
            f"clone-singing engine (XTTS, voice {self.profile.name!r}) sang "
            f"{sung}/{len(pairs)} lyric lines "
            f"({aligned_lines} phoneme-aligned)")
        if sung == 0:
            result.warnings.append(
                "no lines could be sung — check lyrics + melody exist "
                "(Lyrics tab → 'Sing these lyrics')")
        result.alignment = build_lyrics_alignment(project, track)
        return result

    def _rvc_convert_segments(self, segments: list[tuple[int, np.ndarray]],
                              result: VocalRenderResult,
                              autotune: bool = True):
        """RVC-convert the dense concatenation of sung lines in ONE pass, then
        slice the converted audio back per line. Returns [(start, audio)] or
        None on failure (caller keeps the un-converted cloned singing).

        Dense input is essential: RVC collapses long, mostly-silent stems to
        silence, but converts continuous audio faithfully."""
        from .rvc_convert import convert_stem
        cfg = get_config()
        gap = int(0.2 * SAMPLE_RATE)
        parts: list[np.ndarray] = []
        offsets: list[tuple[int, int]] = []   # (start in dense, length)
        pos = 0
        for _, sl in segments:
            offsets.append((pos, len(sl)))
            parts.append(sl)
            parts.append(np.zeros(gap, dtype=np.float32))
            pos += len(sl) + gap
        dense = np.concatenate(parts).astype(np.float32)
        pk = float(np.abs(dense).max())
        if pk > 0.005:
            dense = dense * (0.9 / pk)

        tmp = cfg.analysis_cache_dir / "tts"
        tmp.mkdir(parents=True, exist_ok=True)
        tin = tmp / f"_rvc_in_{self.profile.id[:8]}.wav"
        tout = tmp / f"_rvc_out_{self.profile.id[:8]}.wav"
        write_wav(tin, np.repeat(dense[:, None], 2, axis=1), SAMPLE_RATE)
        warnings = convert_stem(tin, tout, self.profile, autotune=autotune)
        if warnings or not tout.exists():
            result.warnings.extend(warnings)
            return None
        conv, rate = read_audio(tout)
        conv = conv[:, 0]
        if rate != SAMPLE_RATE:
            conv = resample_linear(conv[:, None], rate, SAMPLE_RATE)[:, 0]
        out_segs: list[tuple[int, np.ndarray]] = []
        for (i0, _sl), (dstart, dlen) in zip(segments, offsets):
            seg = conv[dstart:dstart + dlen]
            if len(seg) < dlen:
                seg = np.concatenate(
                    [seg, np.zeros(dlen - len(seg), dtype=np.float32)])
            out_segs.append((i0, seg.astype(np.float32)))
        return out_segs
