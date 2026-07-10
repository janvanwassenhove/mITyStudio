"""Guided voice-recording wizard support: take QA, vocal-range detection,
synthesized guide clips, device detection, and profile confidence.

The wizard's job is clean, varied TIMBRE data (dynamics + range), not genre
acting — the performance layer comes from the singing pipeline.
"""
from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path

import numpy as np

from ..config import get_config
from .audio_io import AudioReadError, read_audio, write_wav

log = logging.getLogger(__name__)

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _note_name(midi: int) -> str:
    return f"{_NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


# --------------------------------------------------------------------------
# per-take QA
# --------------------------------------------------------------------------

def qa_take(path: Path) -> dict:
    """Quality-check one recorded take. verdict: pass | warn | fail."""
    issues: list[str] = []
    tips: list[str] = []
    try:
        data, rate = read_audio(path)
    except AudioReadError as e:
        return {"verdict": "fail", "issues": [f"unreadable audio: {e}"],
                "tips": ["try recording again"]}
    mono = data.mean(axis=1)
    n = len(mono)
    duration = n / rate if rate else 0.0

    peak = float(np.abs(mono).max()) if n else 0.0
    clip_ratio = float(np.mean(np.abs(mono) > 0.985)) if n else 0.0
    rms = float(np.sqrt(np.mean(mono ** 2))) if n else 0.0
    rms_db = 20 * np.log10(rms + 1e-9)

    # noise floor: 10th percentile of 50 ms frame RMS — only meaningful when
    # the take has pauses (a continuously sung tone has no floor to measure)
    frame = max(int(0.05 * rate), 1)
    frames = n // frame
    noise_db = -90.0
    has_pauses = False
    if frames > 4:
        fr = np.sqrt(np.mean(mono[:frames * frame].reshape(frames, frame) ** 2, axis=1))
        noise_db = float(20 * np.log10(np.percentile(fr, 10) + 1e-9))
        med_db = float(20 * np.log10(np.median(fr) + 1e-9))
        has_pauses = noise_db < med_db - 12

    silence_ratio = float(np.mean(np.abs(mono) < 0.01)) if n else 1.0

    if duration < 1.5:
        issues.append("too short")
        tips.append("hold the exercise a little longer (2+ seconds)")
    if clip_ratio > 0.001:
        issues.append("clipping detected")
        tips.append("lower the microphone gain or move back a little")
    if rms_db < -34:
        issues.append("very quiet")
        tips.append("move closer to the microphone or sing a bit louder")
    if has_pauses and noise_db > -35:
        issues.append("noisy background")
        tips.append("find a quieter spot or turn off fans/music")
    if silence_ratio > 0.65:
        issues.append("mostly silence")
        tips.append("start singing right after pressing record")

    hard = {"clipping detected", "unreadable audio", "mostly silence", "too short"}
    verdict = ("fail" if any(i in hard for i in issues)
               else "warn" if issues else "pass")
    return {"verdict": verdict, "issues": issues, "tips": tips,
            "duration": round(duration, 2), "peak": round(peak, 3),
            "rms_db": round(rms_db, 1), "noise_floor_db": round(noise_db, 1),
            "clip_ratio": round(clip_ratio, 5)}


# --------------------------------------------------------------------------
# vocal range detection (from a recorded scale)
# --------------------------------------------------------------------------

def detect_range(path: Path) -> dict:
    try:
        data, rate = read_audio(path)
    except AudioReadError as e:
        return {"error": str(e)}
    mono = data.mean(axis=1).astype(np.float64)
    frame, hop = 2048, 512
    lo_lag, hi_lag = int(rate / 600), int(rate / 60)   # 60..600 Hz singing
    midis: list[float] = []
    for k in range((len(mono) - frame) // hop):
        seg = mono[k * hop:k * hop + frame]
        if np.abs(seg).max() < 0.03:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, mode="full")[frame - 1:]
        if hi_lag >= len(ac):
            continue
        lag = lo_lag + int(np.argmax(ac[lo_lag:hi_lag]))
        if ac[lag] > 0.35 * ac[0]:
            midis.append(69 + 12 * np.log2(rate / lag / 440.0))
    if len(midis) < 10:
        return {"error": "not enough pitched singing detected — try again, "
                         "louder and closer to the microphone"}
    lo = int(round(float(np.percentile(midis, 5))))
    hi = int(round(float(np.percentile(midis, 95))))
    return {"low_midi": lo, "high_midi": hi,
            "low_note": _note_name(lo), "high_note": _note_name(hi),
            "range_semitones": hi - lo,
            "vocal_range": f"{_note_name(lo)}–{_note_name(hi)}"}


# --------------------------------------------------------------------------
# guide clips (synthesized reference the user hears before each take)
# --------------------------------------------------------------------------

def _tone(freq: float, dur: float, rate: int, amp: float = 0.28) -> np.ndarray:
    t = np.arange(int(dur * rate)) / rate
    env = np.minimum(np.minimum(t / 0.03, 1), np.minimum((dur - t) / 0.08, 1))
    return (amp * env * (np.sin(2 * np.pi * freq * t)
                         + 0.3 * np.sin(4 * np.pi * freq * t))).astype(np.float32)


def _midi_freq(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def render_guide(exercise_id: str) -> Path:
    """Synthesized guide audio per exercise, cached on disk."""
    rate = 32000
    cache = get_config().analysis_cache_dir / "wizard"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"guide_{exercise_id}.wav"
    if out.exists():
        return out

    parts: list[np.ndarray] = []
    gap = np.zeros(int(0.12 * rate), np.float32)
    if exercise_id == "range_scale":
        for m in range(48, 72):                      # chromatic-ish rise C3→C5
            parts += [_tone(_midi_freq(m), 0.28, rate), gap]
    elif exercise_id == "sustain_low":
        parts = [_tone(_midi_freq(52), 3.0, rate)]   # E3
    elif exercise_id == "sustain_high":
        parts = [_tone(_midi_freq(64), 3.0, rate)]   # E4
    elif exercise_id == "dynamics":
        parts = [_tone(_midi_freq(57), 1.5, rate, 0.10), gap,
                 _tone(_midi_freq(57), 1.5, rate, 0.38)]
    elif exercise_id == "phrase":
        for m in (57, 60, 62, 60, 57):
            parts += [_tone(_midi_freq(m), 0.5, rate), gap]
    else:                                            # generic A3 reference
        parts = [_tone(_midi_freq(57), 2.0, rate)]
    audio = np.concatenate(parts)
    write_wav(out, audio[:, None], rate)
    return out


EXERCISES = [
    {"id": "range_scale", "title": "Range check",
     "coach": "Sing along with the rising notes as far as comfortable — up "
              "AND down. Stop where it strains; never force the high notes.",
     "seconds": 20},
    {"id": "sustain_low", "title": "Sustained vowel (low)",
     "coach": "One long relaxed “aaah” on the low note. Breathe first, keep "
              "it steady — quiet is fine.", "seconds": 6},
    {"id": "sustain_high", "title": "Sustained vowel (high)",
     "coach": "Same “aaah”, higher. If it strains, pick any comfortable "
              "higher note instead.", "seconds": 6},
    {"id": "dynamics", "title": "Quiet, then loud",
     "coach": "Sing the note softly first, then confidently louder. This "
              "teaches the model your dynamics.", "seconds": 8},
    {"id": "phrase", "title": "Melodic phrase",
     "coach": "Follow the little melody on “la”. Timing matters more than "
              "perfection.", "seconds": 8},
    {"id": "speech", "title": "Spoken sentences",
     "coach": "Read 3–4 sentences in your language, naturally, like telling "
              "a friend a story. Consonants matter here.", "seconds": 20},
]


# --------------------------------------------------------------------------
# device detection + confidence
# --------------------------------------------------------------------------

def detect_device() -> dict:
    """CUDA > MPS > CPU, with an honest description for the UI."""
    try:
        out = subprocess.run(["nvidia-smi", "-L"], capture_output=True,
                             text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            name = out.stdout.strip().splitlines()[0].split(":", 1)[-1].split("(")[0].strip()
            return {"device": "cuda", "name": name,
                    "message": f"GPU found ({name}) — fast training available",
                    "recommended_tier": "full"}
    except (OSError, subprocess.TimeoutExpired):
        pass
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return {"device": "mps", "name": "Apple Silicon",
                "message": "Apple Silicon detected — training uses MPS/CPU "
                           "(unverified for this workload); the quick tier "
                           "is recommended",
                "recommended_tier": "quick"}
    return {"device": "cpu", "name": platform.processor() or "CPU",
            "message": "No dedicated GPU detected — training runs on CPU and "
                       "takes considerably longer. The quick tier keeps it "
                       "practical; day-to-day singing is unaffected.",
            "recommended_tier": "quick"}


TIER_EPOCHS = {"quick": 60, "full": 200}


def profile_confidence(profile, recordings: list[dict]) -> dict:
    """Honest quality expectation from the training material itself."""
    minutes = sum(r.get("minutes", 0.0) for r in recordings)
    score = 0.0
    notes: list[str] = []
    score += min(minutes / 20.0, 1.0) * 0.5          # amount of audio
    if minutes < 5:
        notes.append("under 5 minutes of audio — expect a rough clone; "
                     "record more takes when you can")
    elif minutes < 15:
        notes.append("decent audio amount — more material would still help")
    else:
        notes.append("good amount of training audio")
    rng = (profile.vocal_range or "")
    if "–" in rng or "-" in rng:
        score += 0.2
        notes.append(f"vocal range mapped ({rng})")
    else:
        notes.append("no range test yet — melodies may sit outside the "
                     "comfortable range")
    if profile.consent_recording_id:
        score += 0.05
    exercise_takes = sum(1 for r in recordings if r.get("wizard_take"))
    if exercise_takes >= 4:
        score += 0.25
        notes.append("varied wizard takes (dynamics + range) recorded")
    elif exercise_takes:
        score += 0.1
        notes.append("some wizard takes recorded — finish the session for "
                     "better dynamics coverage")
    else:
        notes.append("built from free-form recordings only — the guided "
                     "wizard adds dynamics/range variety")
    return {"score": round(min(score, 1.0), 2), "minutes": round(minutes, 1),
            "notes": notes}
