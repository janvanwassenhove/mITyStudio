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
    codes: list[str] = []   # stable ids the UI translates
    try:
        data, rate = read_audio(path)
    except AudioReadError as e:
        return {"verdict": "fail", "issues": [f"unreadable audio: {e}"],
                "tips": ["try recording again"], "issue_codes": ["unreadable"]}
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
        codes.append("too_short")
    if clip_ratio > 0.001:
        issues.append("clipping detected")
        tips.append("lower the microphone gain or move back a little")
        codes.append("clipping")
    if rms_db < -34:
        issues.append("very quiet")
        tips.append("move closer to the microphone or sing a bit louder")
        codes.append("quiet")
    if has_pauses and noise_db > -35:
        issues.append("noisy background")
        tips.append("find a quieter spot or turn off fans/music")
        codes.append("noisy")
    if silence_ratio > 0.65:
        issues.append("mostly silence")
        tips.append("start singing right after pressing record")
        codes.append("silence")

    hard = {"clipping detected", "unreadable audio", "mostly silence", "too short"}
    verdict = ("fail" if any(i in hard for i in issues)
               else "warn" if issues else "pass")
    return {"verdict": verdict, "issues": issues, "tips": tips,
            "issue_codes": codes,
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


# --------------------------------------------------------------------------
# Karaoke guides — a single source of truth for BOTH the synthesized guide
# audio and the on-screen note/lyric cues, so what the user sees is exactly
# what they hear. Fixed notes + phrases mean the trainer knows the intended
# target for every frame (better pitch/phoneme alignment when we later map
# the voice), which is why the wizard prescribes them instead of "sing
# anything". Each cue: (midi | None, dur seconds, amp, label).
# --------------------------------------------------------------------------

_GAP = 0.12

# Phonetically rich fixed sentences per language — reading known text gives the
# clone broad, consistent phoneme coverage (vowels + hard/soft consonants).
SPEECH_TEXT = {
    "en": ["The quick brown fox jumps over the lazy dog.",
           "Bright vivid colours dance while soft waves whisper.",
           "Ask me anything and I will happily sing it back."],
    "nl": ["Zwarte vogels vliegen snel over het rustige water.",
           "Lieve mensen zingen graag een vrolijk en helder lied.",
           "Vraag mij iets en ik antwoord je met plezier."],
    "fr": ["Le vif renard brun saute par-dessus le chien paresseux.",
           "De douces vagues chuchotent sous un ciel clair et vif.",
           "Demande-moi ce que tu veux, je te le chanterai."],
    "de": ["Der flinke braune Fuchs springt über den faulen Hund.",
           "Sanfte Wellen flüstern unter einem klaren, hellen Himmel.",
           "Frag mich irgendetwas und ich singe es dir zurück."],
}
READING_TEXT = {
    "en": "Sing this slowly and clearly. Every warm vowel and crisp "
          "consonant you give the model becomes part of your voice — "
          "so relax, breathe, and let the words flow naturally.",
    "nl": "Zing dit rustig en helder. Elke warme klinker en scherpe "
          "medeklinker die je geeft wordt deel van je stem — dus "
          "ontspan, adem, en laat de woorden natuurlijk stromen.",
    "fr": "Chante ceci lentement et clairement. Chaque voyelle chaude et "
          "chaque consonne nette que tu donnes devient une partie de ta "
          "voix — alors détends-toi, respire et laisse les mots couler.",
    "de": "Singe dies langsam und deutlich. Jeder warme Vokal und klare "
          "Konsonant, den du gibst, wird Teil deiner Stimme — also "
          "entspanne dich, atme und lass die Worte natürlich fließen.",
}


def _cue_sequence(exercise_id: str) -> list[tuple[int | None, float, float, str]]:
    """(midi, dur, amp, label) cues for the note/vowel-based exercises."""
    if exercise_id == "range_scale":
        return [(m, 0.28, 0.28, _note_name(m)) for m in range(48, 72)]
    if exercise_id == "sustain_low":
        return [(52, 3.0, 0.28, "aaah")]
    if exercise_id == "sustain_high":
        return [(64, 3.0, 0.28, "aaah")]
    if exercise_id == "dynamics":
        return [(57, 1.5, 0.10, "soft"), (57, 1.5, 0.38, "loud")]
    if exercise_id == "phrase":
        return [(m, 0.5, 0.28, "la") for m in (57, 60, 62, 60, 57)]
    if exercise_id == "vowels":
        return [(57, 1.6, 0.28, v) for v in ("aa", "ee", "ii", "oo", "uu")]
    if exercise_id == "soft_head":
        return [(69, 3.0, 0.12, "oo")]
    return []


def guide_for(exercise_id: str, language: str = "en") -> dict:
    """Karaoke timeline the UI overlays while recording. kind:
    'notes' (pitched cues with note names) | 'text' (fixed lines to read) |
    'siren' (a continuous glide)."""
    lang = language if language in SPEECH_TEXT else "en"
    if exercise_id == "siren":
        return {"kind": "siren", "total": 4.0,
                "cues": [{"at": 0.0, "dur": 4.0, "label": "oo", "midi": None}]}
    if exercise_id == "speech":
        lines = SPEECH_TEXT[lang]
        return {"kind": "text", "total": 0.0, "lines": lines}
    if exercise_id == "reading":
        return {"kind": "text", "total": 0.0, "lines": [READING_TEXT[lang]]}
    seq = _cue_sequence(exercise_id)
    cues, at = [], 0.0
    for midi, dur, _amp, label in seq:
        cues.append({"at": round(at, 3), "dur": round(dur, 3),
                     "label": label, "midi": midi,
                     "note": _note_name(midi) if midi is not None else None})
        at += dur + _GAP
    return {"kind": "notes", "total": round(at, 3), "cues": cues}


def render_guide(exercise_id: str) -> Path:
    """Synthesized guide audio per exercise, cached on disk. Built from the
    same cue sequence the UI shows, so audio and karaoke stay in lock-step."""
    rate = 32000
    cache = get_config().analysis_cache_dir / "wizard"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"guide_{exercise_id}.wav"
    if out.exists():
        return out

    gap = np.zeros(int(_GAP * rate), np.float32)
    if exercise_id == "siren":                       # smooth low→high→low sweep
        t = np.arange(int(4.0 * rate)) / rate
        midi = 52 + 12 * np.sin(np.pi * t / 4.0)     # E3 up an octave and back
        phase = 2 * np.pi * np.cumsum(_midi_freq(midi)) / rate
        env = np.minimum(np.minimum(t / 0.05, 1), np.minimum((4.0 - t) / 0.15, 1))
        audio = (0.26 * env * np.sin(phase)).astype(np.float32)
    else:
        seq = _cue_sequence(exercise_id)
        if not seq:                                  # speech/reading/unknown
            seq = [(57, 2.0, 0.28, "")]              # generic A3 reference
        parts: list[np.ndarray] = []
        for midi, dur, amp, _label in seq:
            parts += [_tone(_midi_freq(midi), dur, rate, amp), gap]
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
    {"id": "vowels", "title": "All five vowels",
     "coach": "Sing “aa – ee – ii – oo – uu” on the reference note, each for "
              "a couple of seconds. Vowel color is what the model learns "
              "here.", "seconds": 12},
    {"id": "siren", "title": "Siren glide",
     "coach": "Glide smoothly low→high→low like a siren on “oo”. Connects "
              "your registers — go gently through the break.", "seconds": 8},
    {"id": "soft_head", "title": "Soft high voice",
     "coach": "A soft, light “oo” on a comfortable high note (head voice is "
              "fine). Quiet and airy is exactly right.", "seconds": 6},
    {"id": "speech", "title": "Spoken sentences",
     "coach": "Read 3–4 sentences in your language, naturally, like telling "
              "a friend a story. Consonants matter here.", "seconds": 20},
    {"id": "reading", "title": "Longer reading",
     "coach": "Read half a minute from any book or article, relaxed. This "
              "adds the most raw material — repeat it as often as you like.",
     "seconds": 40},
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
    codes: list[str] = []   # stable ids the UI translates
    score += min(minutes / 20.0, 1.0) * 0.5          # amount of audio
    if minutes < 5:
        notes.append("under 5 minutes of audio — expect a rough clone; "
                     "record more takes when you can")
        codes.append("low_audio")
    elif minutes < 15:
        notes.append("decent audio amount — more material would still help")
        codes.append("medium_audio")
    else:
        notes.append("good amount of training audio")
        codes.append("good_audio")
    rng = (profile.vocal_range or "")
    if "–" in rng or "-" in rng:
        score += 0.2
        notes.append(f"vocal range mapped ({rng})")
        codes.append("range_mapped")
    else:
        notes.append("no range test yet — melodies may sit outside the "
                     "comfortable range")
        codes.append("no_range")
    if profile.consent_recording_id:
        score += 0.05
    exercise_takes = sum(1 for r in recordings if r.get("wizard_take"))
    if exercise_takes >= 4:
        score += 0.25
        notes.append("varied wizard takes (dynamics + range) recorded")
        codes.append("varied_takes")
    elif exercise_takes:
        score += 0.1
        notes.append("some wizard takes recorded — finish the session for "
                     "better dynamics coverage")
        codes.append("some_takes")
    else:
        notes.append("built from free-form recordings only — the guided "
                     "wizard adds dynamics/range variety")
        codes.append("freeform_only")
    return {"score": round(min(score, 1.0), 2), "minutes": round(minutes, 1),
            "notes": notes, "note_codes": codes, "vocal_range": rng}
