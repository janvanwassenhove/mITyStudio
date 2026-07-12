"""Sample analysis: lightweight, dependable metrics (numpy) plus filename
heuristics for BPM/key. Unreliable estimates are stored as null + warning.
Analysis results live in SQLite, never next to the original files.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np

from ..db import get_db
from ..models.asset import Asset
from . import asset_repo
from .audio_io import AudioReadError, read_audio

log = logging.getLogger(__name__)

ANALYSIS_VERSION = 3   # 3: CLAP content tags + retrieval embedding

_BPM_RE = re.compile(r"(\d{2,3})\s*bpm", re.IGNORECASE)
_KEY_RE = re.compile(
    r"(?:^|[\s\-_])([A-G][#b]?)\s*(maj(?:or)?|min(?:or)?|m)?(?:[\s\-_.]|$)")

_SOUND_TYPE_KEYWORDS = {
    "kick": "kick", "snare": "snare", "hat": "hihat", "hihat": "hihat",
    "clap": "clap", "crash": "cymbal", "ride": "cymbal", "tom": "tom",
    "perc": "percussion", "808": "808", "bass": "bass", "pad": "pad",
    "lead": "lead", "pluck": "pluck", "vocal": "vocal", "vox": "vocal",
    "fx": "fx", "riser": "riser", "loop": "loop", "piano": "piano",
    "guitar": "guitar", "synth": "synth", "string": "strings",
}


def _bpm_from_filename(name: str) -> float | None:
    m = _BPM_RE.search(name)
    if m:
        bpm = int(m.group(1))
        if 40 <= bpm <= 220:
            return float(bpm)
    return None


def _key_from_filename(name: str) -> str | None:
    stem = name.rsplit(".", 1)[0]
    m = _KEY_RE.search(stem)
    if not m:
        return None
    root = m.group(1)
    qual = (m.group(2) or "").lower()
    if qual in ("m", "min", "minor"):
        return f"{root} minor"
    if qual in ("maj", "major"):
        return f"{root} major"
    return root


def _estimate_bpm_autocorr(mono: np.ndarray, rate: int) -> float | None:
    """Coarse onset-envelope autocorrelation BPM estimate; None if unsure."""
    if mono.size < rate:  # under a second: no tempo
        return None
    hop = 512
    frames = len(mono) // hop
    if frames < 64:
        return None
    env = np.abs(mono[:frames * hop]).reshape(frames, hop).max(axis=1)
    denv = np.maximum(np.diff(env), 0)
    if denv.std() < 1e-6:
        return None
    denv = denv - denv.mean()
    ac = np.correlate(denv, denv, mode="full")[len(denv) - 1:]
    fps = rate / hop
    lo, hi = int(fps * 60 / 200), int(fps * 60 / 60)  # 60..200 bpm
    if hi >= len(ac) or lo < 1:
        return None
    lag = lo + int(np.argmax(ac[lo:hi]))
    peak = ac[lag]
    if peak <= 0 or peak < 0.25 * ac[0]:
        return None  # unreliable
    return round(60.0 * fps / lag, 1)


_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _estimate_pitch(mono: np.ndarray, rate: int) -> tuple[str | None, float | None]:
    """Autocorrelation pitch detection on the loudest 0.5 s segment.
    Returns (note name like 'D#2', frequency) or (None, None) if not tonal."""
    if len(mono) < rate // 4:
        return None, None
    win = min(len(mono), rate // 2)
    hop = max(1, (len(mono) - win) // 8)
    starts = range(0, max(len(mono) - win, 1), hop)
    best_start = max(starts, key=lambda s: float(np.abs(mono[s:s + win]).mean()))
    seg = mono[best_start:best_start + win].astype(np.float64)
    seg -= seg.mean()
    if seg.std() < 1e-5:
        return None, None
    ac = np.correlate(seg, seg, mode="full")[win - 1:]
    lo = int(rate / 1000)  # 1000 Hz max
    hi = int(rate / 40)    # 40 Hz min
    if hi >= len(ac) or lo >= hi:
        return None, None
    lag = lo + int(np.argmax(ac[lo:hi]))
    if ac[lag] < 0.35 * ac[0]:  # not periodic enough
        return None, None
    freq = rate / lag
    midi = int(round(69 + 12 * np.log2(freq / 440.0)))
    if not 12 <= midi <= 108:
        return None, None
    return f"{_NOTE_NAMES[midi % 12]}{midi // 12 - 1}", round(freq, 2)


def analyse_asset(asset: Asset) -> dict:
    warnings: list[str] = []
    path = Path(asset.original_path)
    analysis: dict = {"analysis_version": ANALYSIS_VERSION, "warnings": warnings}

    try:
        data, rate = read_audio(path)
    except AudioReadError as e:
        analysis["error"] = str(e)
        asset_repo.update_metadata(asset.id, analysis_status="failed")
        _store(asset.id, analysis)
        return analysis

    mono = data.mean(axis=1)
    n = len(mono)
    duration = n / rate if rate else 0.0
    rms = float(np.sqrt(np.mean(np.square(mono)))) if n else 0.0
    peak = float(np.max(np.abs(mono))) if n else 0.0

    # silence at edges (below -48 dB)
    thresh = 10 ** (-48 / 20)
    loud = np.flatnonzero(np.abs(mono) > thresh)
    silence_start = float(loud[0] / rate) if loud.size else duration
    silence_end = float((n - 1 - loud[-1]) / rate) if loud.size else duration

    # transient density: normalized count of strong onsets per second
    hop = 512
    frames = n // hop
    transient_density = None
    if frames > 4:
        env = np.abs(mono[:frames * hop]).reshape(frames, hop).max(axis=1)
        denv = np.diff(env)
        onsets = int(np.sum(denv > (denv.std() * 2 + 1e-9)))
        transient_density = round(onsets / duration, 2) if duration > 0 else None

    bpm = _bpm_from_filename(asset.filename)
    bpm_source = "filename" if bpm else None
    if bpm is None:
        bpm = _estimate_bpm_autocorr(mono, rate)
        bpm_source = "autocorrelation" if bpm else None
    if bpm is None:
        warnings.append("bpm could not be estimated reliably")

    key = _key_from_filename(asset.filename)
    pitch_note, pitch_freq = _estimate_pitch(mono, rate)
    if key is None and pitch_note is not None:
        key = pitch_note[:-1] if pitch_note[-1].isdigit() else pitch_note
    if key is None:
        warnings.append("key/pitch could not be detected reliably")

    # loopability: audible right up to both edges and >= 1 bar long
    loopability = None
    if duration > 0:
        edge_silence = silence_start + silence_end
        loopability = round(max(0.0, 1.0 - edge_silence / max(duration, 0.1))
                            * (1.0 if duration >= 1.5 else 0.5), 2)

    sound_type = next((v for k, v in _SOUND_TYPE_KEYWORDS.items()
                       if k in asset.filename.lower()), None)

    # content classification for the AI planner: vocals vs instrumental,
    # acapella, energy — pitched-voice ratio in the singing band + onsets
    from .singing_metrics import frame_f0
    f0 = frame_f0(mono, rate, lo_hz=85, hi_hz=500)
    voiced = float(np.mean(f0 > 0)) if len(f0) else 0.0
    fname = asset.filename.lower()
    has_vocals = (voiced > 0.35 and (transient_density or 0) < 6) \
        or any(k in fname for k in ("vocal", "acapella", "voice", "vox"))
    is_acapella = has_vocals and ((transient_density or 0) < 1.5
                                  or "acapella" in fname)
    energy = ("high-energy" if rms > 0.18 or (transient_density or 0) > 5
              else "mellow" if rms < 0.06 else None)

    vibe_tags = [t for t in (
        sound_type,
        "loop" if (loopability or 0) > 0.85 and duration > 1.5 else None,
        "one-shot" if duration < 1.5 else None,
        "vocals" if has_vocals else "instrumental",
        "acapella" if is_acapella else None,
        energy,
    ) if t]

    # content-based tags + semantic embedding (CLAP hears the audio itself —
    # essential for cryptically named samples). Optional and graceful.
    from . import audio_tagging
    if audio_tagging.available():
        tagged = audio_tagging.tag_audio(mono, rate)
        if tagged:
            analysis["content_tags"] = tagged["content_tags"]
            analysis["clap_embedding"] = tagged["clap_embedding"]
            vibe_tags = list(dict.fromkeys(
                [*vibe_tags, *tagged["content_tags"]]))

    desc_parts = [f"{duration:.2f}s", f"{data.shape[1]}ch @ {rate}Hz"]
    if bpm:
        desc_parts.append(f"~{bpm:g} BPM ({bpm_source})")
    if key:
        desc_parts.append(f"key {key}")
    if sound_type:
        desc_parts.append(sound_type)
    generated_description = ", ".join(desc_parts)

    analysis.update({
        "duration": round(duration, 4),
        "sample_rate": rate,
        "channels": int(data.shape[1]),
        "loudness_rms": round(rms, 5),
        "peak_level": round(peak, 5),
        "estimated_bpm": bpm,
        "bpm_source": bpm_source,
        "estimated_key": key,
        "pitch_range": ({"note": pitch_note, "frequency": pitch_freq}
                        if pitch_note else None),
        "transient_density": transient_density,
        "silence_start": round(silence_start, 4),
        "silence_end": round(silence_end, 4),
        "loopability_estimate": loopability,
        "sound_type_guess": sound_type,
        "has_vocals": has_vocals,
        "is_acapella": is_acapella,
        "voiced_ratio": round(voiced, 3),
        "vibe_tags": vibe_tags,
        "generated_description": generated_description,
    })
    _store(asset.id, analysis)
    asset_repo.update_metadata(asset.id, analysis_status="analysed",
                               generated_description=generated_description)
    return analysis


def _store(asset_id: str, analysis: dict) -> None:
    get_db().execute(
        "INSERT INTO sample_analyses (asset_id, analysis) VALUES (?, ?) "
        "ON CONFLICT(asset_id) DO UPDATE SET analysis=excluded.analysis",
        (asset_id, json.dumps(analysis)))
    get_db().commit()


def get_analysis(asset_id: str) -> dict | None:
    row = get_db().execute(
        "SELECT analysis FROM sample_analyses WHERE asset_id=?",
        (asset_id,)).fetchone()
    return json.loads(row["analysis"]) if row else None


def search_assets(*, text: str | None = None, tags: list[str] | None = None,
                  bpm_min: float | None = None, bpm_max: float | None = None,
                  key: str | None = None, asset_type: str | None = None) -> list[dict]:
    results = []
    for asset in asset_repo.list_assets(asset_type, include_missing=False):
        analysis = get_analysis(asset.id)
        if text:
            haystack = " ".join([asset.filename, asset.user_description,
                                 asset.generated_description,
                                 " ".join(asset.tags)]).lower()
            if not all(w in haystack for w in text.lower().split()):
                continue
        if tags:
            asset_tags = {t.lower() for t in asset.tags}
            asset_tags |= {t.lower() for t in (analysis or {}).get("vibe_tags", [])}
            if not all(t.lower() in asset_tags for t in tags):
                continue
        bpm = (analysis or {}).get("estimated_bpm")
        if bpm_min is not None and (bpm is None or bpm < bpm_min):
            continue
        if bpm_max is not None and (bpm is None or bpm > bpm_max):
            continue
        if key:
            akey = ((analysis or {}).get("estimated_key") or "").lower()
            if not akey.startswith(key.lower()):
                continue
        d = asset.model_dump()
        d["analysis"] = analysis
        results.append(d)
    return results
