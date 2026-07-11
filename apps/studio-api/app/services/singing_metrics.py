"""Objective singing-quality metrics for validating the vocal pipeline.

These don't replace listening, but they catch regressions and rank engine
variants without ears:
- voiced_ratio        how much of the audio carries pitched voice (silence /
                      noise-only output scores ~0 — catches "silent stem" bugs)
- pitch_accuracy      how well the sung pitch tracks the target melody notes
                      (median error in cents + % of frames within 50 cents)
- spectral_flatness   buzziness indicator on voiced frames (robotic vocoder
                      output is flatter/noisier than natural voice)
"""
from __future__ import annotations

import numpy as np

_FRAME = 2048
_HOP = 512


def frame_f0(audio: np.ndarray, rate: int,
             lo_hz: float = 60, hi_hz: float = 600) -> np.ndarray:
    """Per-frame fundamental frequency via autocorrelation (0 = unvoiced)."""
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)
    n_frames = max((len(mono) - _FRAME) // _HOP + 1, 0)
    f0 = np.zeros(n_frames)
    lo, hi = int(rate / hi_hz), int(rate / lo_hz)
    for k in range(n_frames):
        seg = mono[k * _HOP:k * _HOP + _FRAME]
        if np.abs(seg).max() < 0.02:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, mode="full")[_FRAME - 1:]
        if hi >= len(ac):
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.30 * ac[0]:
            f0[k] = rate / lag
    return f0


def voiced_ratio(audio: np.ndarray, rate: int) -> float:
    """Fraction of frames with detectable pitch (over the whole clip)."""
    f0 = frame_f0(audio, rate)
    return float(np.mean(f0 > 0)) if len(f0) else 0.0


def pitch_accuracy(audio: np.ndarray, rate: int,
                   notes: list[dict]) -> dict:
    """Compare sung pitch to target notes.
    notes: [{"start": s, "end": s, "freq": hz}] on the same clock as audio.
    Octave errors are folded (register choice is a feature, not a bug)."""
    f0 = frame_f0(audio, rate)
    errors: list[float] = []
    for nd in notes:
        k0 = int(nd["start"] * rate / _HOP)
        k1 = min(int(nd["end"] * rate / _HOP), len(f0))
        target = nd["freq"]
        for k in range(max(k0, 0), k1):
            if f0[k] <= 0:
                continue
            cents = 1200 * np.log2(f0[k] / target)
            cents = ((cents + 600) % 1200) - 600   # fold octaves
            errors.append(abs(cents))
    if not errors:
        return {"median_cents_error": None, "within_50_cents": 0.0, "frames": 0}
    arr = np.array(errors)
    return {"median_cents_error": round(float(np.median(arr)), 1),
            "within_50_cents": round(float(np.mean(arr <= 50)), 3),
            "frames": len(errors)}


def spectral_flatness(audio: np.ndarray, rate: int) -> float:
    """Mean spectral flatness of voiced frames (0=tonal … 1=noise)."""
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)
    f0 = frame_f0(mono, rate)
    vals: list[float] = []
    for k in range(len(f0)):
        if f0[k] <= 0:
            continue
        seg = mono[k * _HOP:k * _HOP + _FRAME]
        mag = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) + 1e-10
        vals.append(float(np.exp(np.mean(np.log(mag))) / np.mean(mag)))
    return round(float(np.mean(vals)), 4) if vals else 1.0


def report(audio: np.ndarray, rate: int, notes: list[dict]) -> dict:
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)
    peak = float(np.abs(mono).max()) if len(mono) else 0.0
    active = mono[np.abs(mono) > 0.01]
    return {
        "peak": round(peak, 3),
        "rms_active": round(float(np.sqrt(np.mean(active ** 2))), 4) if active.size else 0.0,
        "voiced_ratio": round(voiced_ratio(mono, rate), 3),
        "spectral_flatness": spectral_flatness(mono, rate),
        **pitch_accuracy(mono, rate, notes),
    }
