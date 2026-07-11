"""Singing-quality metrics: sanity on synthetic signals."""
import numpy as np

from app.services.singing_metrics import (pitch_accuracy, report,
                                          spectral_flatness, voiced_ratio)

RATE = 22050


def _tone(freq: float, dur: float) -> np.ndarray:
    t = np.arange(int(dur * RATE)) / RATE
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_voiced_ratio_tone_vs_noise():
    assert voiced_ratio(_tone(220, 2.0), RATE) > 0.9
    rng = np.random.default_rng(0)
    assert voiced_ratio((rng.standard_normal(RATE) * 0.3).astype(np.float32),
                        RATE) < 0.4
    assert voiced_ratio(np.zeros(RATE, np.float32), RATE) == 0.0


def test_pitch_accuracy_on_target_and_off():
    audio = _tone(220, 1.0)   # A3
    on = pitch_accuracy(audio, RATE, [{"start": 0, "end": 1.0, "freq": 220.0}])
    assert on["median_cents_error"] is not None and on["median_cents_error"] < 20
    assert on["within_50_cents"] > 0.9
    off = pitch_accuracy(audio, RATE, [{"start": 0, "end": 1.0, "freq": 261.6}])
    assert off["median_cents_error"] > 100   # a major third off


def test_pitch_accuracy_folds_octaves():
    audio = _tone(440, 1.0)   # A4 sung against an A3 target = register choice
    r = pitch_accuracy(audio, RATE, [{"start": 0, "end": 1.0, "freq": 220.0}])
    assert r["median_cents_error"] < 20


def test_spectral_flatness_orders_tone_below_noise():
    tone = spectral_flatness(_tone(220, 1.0), RATE)
    rng = np.random.default_rng(1)
    noise = 0.4 * rng.standard_normal(RATE).astype(np.float32)
    # make the noise loosely periodic so frames count as voiced
    noisy_tone = (_tone(150, 1.0) + noise).astype(np.float32)
    assert tone < spectral_flatness(noisy_tone, RATE)


def test_report_shape():
    r = report(_tone(220, 1.0), RATE,
               [{"start": 0, "end": 1.0, "freq": 220.0}])
    for key in ("peak", "rms_active", "voiced_ratio", "spectral_flatness",
                "median_cents_error", "within_50_cents"):
        assert key in r
