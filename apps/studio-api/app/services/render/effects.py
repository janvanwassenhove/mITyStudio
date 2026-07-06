"""EffectsProcessor: pure-numpy track effects applied to stems.

All seven effect types are real DSP:
gain, pan (constant-power), eq (FFT 3-band: low shelf / mid peak / high
shelf), compressor (frame-level envelope follower with attack/release,
threshold/ratio/makeup), delay (feedback taps), reverb (comb bank),
distortion (tanh drive).
"""
from __future__ import annotations

import logging

import numpy as np

from ...models.song import Effect, EffectChain

log = logging.getLogger(__name__)

PLACEHOLDER_EFFECTS: set[str] = set()  # none since the full-DSP upgrade


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


def _fx_eq(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    """FFT-based 3-band EQ: low shelf below low_freq, peak around mid_freq,
    high shelf above high_freq. Gains in dB. Zero-phase (offline render)."""
    low_gain = float(np.clip(params.get("low_gain_db", 0.0), -24, 24))
    mid_gain = float(np.clip(params.get("mid_gain_db", 0.0), -24, 24))
    high_gain = float(np.clip(params.get("high_gain_db", 0.0), -24, 24))
    if low_gain == mid_gain == high_gain == 0.0:
        return data
    low_f = float(np.clip(params.get("low_freq", 200.0), 20, 2000))
    mid_f = float(np.clip(params.get("mid_freq", 1000.0), 100, 8000))
    mid_q = float(np.clip(params.get("mid_q", 1.0), 0.2, 8.0))
    high_f = float(np.clip(params.get("high_freq", 4000.0), 500, 16000))

    n = len(data)
    freqs = np.fft.rfftfreq(n, 1 / rate)
    logf = np.log2(np.maximum(freqs, 1.0))
    # smooth shelves via sigmoid over log-frequency, peak via gaussian
    low_curve = low_gain / (1 + np.exp(4.0 * (logf - np.log2(low_f))))
    high_curve = high_gain / (1 + np.exp(-4.0 * (logf - np.log2(high_f))))
    mid_curve = mid_gain * np.exp(-0.5 * ((logf - np.log2(mid_f)) * mid_q) ** 2)
    curve = 10 ** ((low_curve + mid_curve + high_curve) / 20)

    out = np.empty_like(data)
    for ch in range(data.shape[1]):
        spec = np.fft.rfft(data[:, ch])
        out[:, ch] = np.fft.irfft(spec * curve, n=n)
    return out


def _fx_compressor(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    """Feed-forward compressor with frame-level (10 ms) envelope follower."""
    threshold_db = float(np.clip(params.get("threshold_db", -18.0), -60, 0))
    ratio = float(np.clip(params.get("ratio", 4.0), 1.0, 20.0))
    attack_s = float(np.clip(params.get("attack_seconds", 0.01), 0.001, 0.5))
    release_s = float(np.clip(params.get("release_seconds", 0.15), 0.01, 2.0))
    makeup_db = float(np.clip(params.get("makeup_db", 0.0), 0, 24))

    frame = max(int(0.01 * rate), 1)
    n_frames = int(np.ceil(len(data) / frame))
    if n_frames < 2:
        return data
    padded = np.zeros((n_frames * frame, data.shape[1]), dtype=np.float32)
    padded[:len(data)] = data
    rms = np.sqrt(np.mean(
        padded.reshape(n_frames, frame, -1).astype(np.float64) ** 2,
        axis=(1, 2))) + 1e-10
    level_db = 20 * np.log10(rms)
    over = np.maximum(level_db - threshold_db, 0.0)
    target_gain_db = -over * (1 - 1 / ratio)

    # attack/release smoothing (few thousand frames — cheap loop)
    a_coef = np.exp(-frame / (attack_s * rate))
    r_coef = np.exp(-frame / (release_s * rate))
    smoothed = np.empty_like(target_gain_db)
    g = 0.0
    for i, t in enumerate(target_gain_db):
        coef = a_coef if t < g else r_coef  # more reduction -> attack
        g = coef * g + (1 - coef) * t
        smoothed[i] = g

    gain = (10 ** ((smoothed + makeup_db) / 20)).astype(np.float32)
    per_sample = np.repeat(gain, frame)[:len(data)]
    return data * per_sample[:, None]


def _fx_robot(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    """Classic robot voice: ring modulation with a carrier + light
    quantization. carrier_hz 20-200 sets the metallic character."""
    carrier_hz = float(np.clip(params.get("carrier_hz", 55.0), 10, 400))
    mix = float(np.clip(params.get("mix", 1.0), 0.0, 1.0))
    crush = float(np.clip(params.get("crush", 0.15), 0.0, 1.0))
    t = np.arange(len(data)) / rate
    carrier = np.sin(2 * np.pi * carrier_hz * t)[:, None]
    wet = data * carrier
    if crush > 0:
        levels = 2 ** (12 - int(8 * crush))  # 12-bit .. 4-bit
        wet = np.round(wet * levels) / levels
    return (data * (1 - mix) + wet * mix).astype(np.float32)


def _fx_telephone(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    """Narrow band-pass (300-3400 Hz style) via FFT — old phone / megaphone."""
    low = float(np.clip(params.get("low_freq", 300.0), 50, 2000))
    high = float(np.clip(params.get("high_freq", 3400.0), 1000, 10000))
    drive = float(np.clip(params.get("drive", 1.5), 1.0, 10.0))
    n = len(data)
    freqs = np.fft.rfftfreq(n, 1 / rate)
    logf = np.log2(np.maximum(freqs, 1.0))
    curve = (1 / (1 + np.exp(-6.0 * (logf - np.log2(low))))
             * 1 / (1 + np.exp(6.0 * (logf - np.log2(high)))))
    out = np.empty_like(data)
    for ch in range(data.shape[1]):
        spec = np.fft.rfft(data[:, ch])
        out[:, ch] = np.fft.irfft(spec * curve, n=n)
    return (np.tanh(out * drive) / np.tanh(drive)).astype(np.float32)


def _fx_chorus(data: np.ndarray, rate: int, params: dict) -> np.ndarray:
    """Chorus: 2 modulated delay taps (5-25 ms) summed with the dry signal."""
    depth_ms = float(np.clip(params.get("depth_ms", 8.0), 1, 20))
    rate_hz = float(np.clip(params.get("rate_hz", 0.8), 0.05, 8.0))
    mix = float(np.clip(params.get("mix", 0.5), 0.0, 1.0))
    n = len(data)
    t = np.arange(n)
    base = int(0.015 * rate)
    wet = np.zeros_like(data)
    for phase in (0.0, np.pi / 2):
        mod = base + (depth_ms / 1000 * rate) * (
            0.5 + 0.5 * np.sin(2 * np.pi * rate_hz * t / rate + phase))
        idx = np.clip(t - mod.astype(int), 0, n - 1)
        wet += data[idx] * 0.5
    return (data * (1 - mix * 0.5) + wet * mix).astype(np.float32)


_PROCESSORS = {
    "gain": _fx_gain,
    "pan": _fx_pan,
    "eq": _fx_eq,
    "compressor": _fx_compressor,
    "delay": _fx_delay,
    "reverb": _fx_reverb,
    "distortion": _fx_distortion,
    "robot": _fx_robot,
    "telephone": _fx_telephone,
    "chorus": _fx_chorus,
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
