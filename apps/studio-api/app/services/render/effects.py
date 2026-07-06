"""EffectsProcessor: pure-numpy track effects applied to stems.

Implemented: gain, pan, delay, reverb (Schroeder-style comb+allpass),
distortion (tanh drive). Placeholders (documented, act as identity with a
warning): eq, compressor.
"""
from __future__ import annotations

import logging

import numpy as np

from ...models.song import Effect, EffectChain

log = logging.getLogger(__name__)

PLACEHOLDER_EFFECTS = {"eq", "compressor"}


def _fx_gain(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    return data * float(10 ** (params.get("gain_db", 0.0) / 20))


def _fx_pan(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    # constant-power pan, position -1..1
    pos = float(np.clip(params.get("position", 0.0), -1, 1))
    angle = (pos + 1) * np.pi / 4
    out = data.copy()
    out[:, 0] *= np.cos(angle) * np.sqrt(2)
    out[:, 1] *= np.sin(angle) * np.sqrt(2)
    return out


def _fx_delay(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    time_s = float(np.clip(params.get("time_seconds", 0.3), 0.01, 2.0))
    feedback = float(np.clip(params.get("feedback", 0.35), 0.0, 0.9))
    mix = float(np.clip(params.get("mix", 0.3), 0.0, 1.0))
    d = int(time_s * rate)
    if d <= 0 or d >= len(data):
        return data
    wet = np.zeros_like(data)
    buf = data.copy()
    amp = 1.0
    offset = d
    while offset < len(data) and amp > 0.01:
        amp *= feedback if offset > d else 1.0
        wet[offset:] += buf[:len(data) - offset] * (amp if offset > d else feedback)
        # single feedback tap chain
        offset += d
        amp *= feedback
    return data * (1 - mix) + (data + wet) * mix


def _fx_reverb(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    mix = float(np.clip(params.get("mix", 0.25), 0.0, 1.0))
    decay = float(np.clip(params.get("decay", 0.5), 0.1, 0.95))
    wet = np.zeros_like(data)
    # 4 parallel comb delays (prime-ish ms) with decaying feedback
    for ms in (29.7, 37.1, 41.1, 43.7):
        d = int(ms / 1000 * rate)
        if d == 0 or d >= len(data):
            continue
        comb = np.zeros_like(data)
        comb[d:] = data[:-d]
        g = decay
        acc = comb * g
        for _ in range(3):
            shifted = np.zeros_like(acc)
            shifted[d:] = acc[:-d]
            g *= decay
            acc += shifted * g
        wet += acc
    wet /= 4.0
    return data * (1 - mix) + wet * mix


def _fx_distortion(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    drive = float(np.clip(params.get("drive", 3.0), 1.0, 30.0))
    mix = float(np.clip(params.get("mix", 1.0), 0.0, 1.0))
    wet = np.tanh(data * drive) / np.tanh(drive)
    return data * (1 - mix) + wet * mix


_PROCESSORS = {
    "gain": _fx_gain,
    "pan": _fx_pan,
    "delay": _fx_delay,
    "reverb": _fx_reverb,
    "distortion": _fx_distortion,
}


def apply_effect_chain(data: np.ndarray, rate: int,
                       chain: EffectChain) -> tuple[np.ndarray, list[str]]:
    """Apply enabled effects in order. Returns (audio, warnings)."""
    warnings: list[str] = []
    for effect in chain.effects:
        if not effect.enabled:
            continue
        if effect.effect_type in PLACEHOLDER_EFFECTS:
            warnings.append(
                f"effect {effect.effect_type!r} is a documented placeholder "
                "in v1 and was applied as identity")
            continue
        proc = _PROCESSORS.get(effect.effect_type)
        if proc is None:
            warnings.append(f"unknown effect {effect.effect_type!r} skipped")
            continue
        try:
            data = proc(data, rate, effect.params).astype(np.float32)
        except Exception as e:
            warnings.append(f"effect {effect.effect_type!r} failed: {e}")
    return data, warnings
