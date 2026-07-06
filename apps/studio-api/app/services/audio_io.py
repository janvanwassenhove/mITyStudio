"""Audio file reading with graceful fallback.

soundfile (libsndfile) covers wav/flac/ogg/aiff and often mp3; anything it
cannot read is decoded through ffmpeg to a temp wav when ffmpeg is available.
Always returns float32 samples in [-1, 1].
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from .capabilities import ffmpeg_path

log = logging.getLogger(__name__)


class AudioReadError(Exception):
    pass


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    """Returns (samples[frames, channels] float32, sample_rate)."""
    try:
        data, rate = sf.read(str(path), dtype="float32", always_2d=True)
        return data, rate
    except Exception as first_err:
        ff = ffmpeg_path()
        if ff is None:
            raise AudioReadError(
                f"cannot read {path.name}: {first_err} (ffmpeg not available "
                "for fallback decoding)") from first_err
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "decoded.wav"
            proc = subprocess.run(
                [ff, "-y", "-v", "error", "-i", str(path),
                 "-acodec", "pcm_f32le", str(tmp)],
                capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                raise AudioReadError(
                    f"cannot decode {path.name}: {proc.stderr.strip()[:300]}") from first_err
            data, rate = sf.read(str(tmp), dtype="float32", always_2d=True)
            return data, rate


def write_wav(path: Path, data: np.ndarray, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, rate, subtype="PCM_16")


def to_stereo(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        data = data[:, None]
    if data.shape[1] == 1:
        return np.repeat(data, 2, axis=1)
    if data.shape[1] > 2:
        return data[:, :2]
    return data


def resample_linear(data: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Simple linear-interpolation resampler (adequate for v1)."""
    if src_rate == dst_rate:
        return data
    n_src = data.shape[0]
    n_dst = int(round(n_src * dst_rate / src_rate))
    if n_src == 0 or n_dst == 0:
        return np.zeros((0, data.shape[1]), dtype=np.float32)
    x_src = np.linspace(0.0, 1.0, n_src, endpoint=False)
    x_dst = np.linspace(0.0, 1.0, n_dst, endpoint=False)
    out = np.empty((n_dst, data.shape[1]), dtype=np.float32)
    for ch in range(data.shape[1]):
        out[:, ch] = np.interp(x_dst, x_src, data[:, ch])
    return out
