"""Waveform peak metadata for timeline visualization.

Peaks are stored in projects/{id}/waveforms.json and served through the
PlaybackManifest — the frontend never decodes audio to draw waveforms.
"""
from __future__ import annotations

import json
import logging

import numpy as np

from ...config import get_config
from ...models.song import SongProject
from ..audio_io import AudioReadError, read_audio

log = logging.getLogger(__name__)

PEAK_BUCKETS = 200


def update_waveform_cache(project: SongProject) -> None:
    cfg = get_config()
    out = []
    for stem in project.stems:
        path = cfg.root / stem.path
        if not path.exists():
            continue
        try:
            data, rate = read_audio(path)
        except AudioReadError as e:
            log.warning("waveform: %s", e)
            continue
        mono = np.abs(data).max(axis=1)
        n = len(mono)
        if n == 0:
            continue
        bucket = max(1, n // PEAK_BUCKETS)
        usable = (n // bucket) * bucket
        peaks = mono[:usable].reshape(-1, bucket).max(axis=1)
        out.append({
            "track_id": stem.track_id,
            "path": stem.path,
            "peaks": [round(float(p), 3) for p in peaks[:PEAK_BUCKETS]],
            "duration_seconds": round(n / rate, 3),
        })
    path = cfg.projects_dir / project.id / "waveforms.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out), encoding="utf-8")
