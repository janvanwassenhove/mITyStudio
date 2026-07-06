"""SampleRenderService: sample tracks → WAV stems.

Places sample clips on the timeline by start beat, supports one-shots, loops,
gain and fades; output stems are aligned to the full project duration.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ...config import get_config
from ...models.song import Clip, SongProject, StemRef, Track
from .. import asset_repo, timing
from ..audio_io import AudioReadError, read_audio, resample_linear, to_stereo, write_wav
from .soundfont_renderer import SAMPLE_RATE, _register_stem_asset, track_fingerprint

log = logging.getLogger(__name__)


def _render_clip(project: SongProject, clip: Clip, out: np.ndarray,
                 warnings: list[str]) -> None:
    asset = asset_repo.get_asset(clip.source_asset_id or "")
    if asset is None or asset.is_missing:
        warnings.append(f"clip {clip.id}: sample asset unavailable, skipped")
        return
    try:
        data, rate = read_audio(Path(asset.original_path))
    except AudioReadError as e:
        warnings.append(f"clip {clip.id}: {e}")
        return
    data = to_stereo(data)
    data = resample_linear(data, rate, SAMPLE_RATE)
    if clip.source_offset_seconds > 0:
        offset = int(clip.source_offset_seconds * SAMPLE_RATE)
        if clip.loop and len(data) > 0:
            offset %= len(data)   # loops keep phase across a split
        data = data[offset:]
        if len(data) == 0:
            warnings.append(f"clip {clip.id}: offset beyond sample end, skipped")
            return

    start = int(timing.beats_to_seconds(project, clip.start_beat) * SAMPLE_RATE)
    slot = int(timing.beats_to_seconds(project, clip.duration_beats) * SAMPLE_RATE)
    slot = min(slot, len(out) - start)
    if slot <= 0:
        warnings.append(f"clip {clip.id}: outside project duration, skipped")
        return

    if clip.loop and len(data) > 0:
        reps = int(np.ceil(slot / len(data)))
        data = np.tile(data, (reps, 1))[:slot]
    else:
        data = data[:slot]  # one-shot, truncated to its slot

    gain = 10 ** (clip.gain_db / 20)
    data = data * gain

    if clip.fade_in_seconds > 0:
        n = min(int(clip.fade_in_seconds * SAMPLE_RATE), len(data))
        data[:n] *= np.linspace(0, 1, n)[:, None]
    if clip.fade_out_seconds > 0:
        n = min(int(clip.fade_out_seconds * SAMPLE_RATE), len(data))
        data[-n:] *= np.linspace(1, 0, n)[:, None]

    out[start:start + len(data)] += data


def render_sample_track(project: SongProject, track: Track,
                        out_path: Path) -> list[str]:
    warnings: list[str] = []
    total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
    out = np.zeros((total, 2), dtype=np.float32)
    for clip in track.clips:
        if clip.clip_type != "sample":
            continue
        _render_clip(project, clip, out, warnings)
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 1.0:
        out /= peak  # per-stem safety normalization
        warnings.append(f"track {track.name!r}: stem peaked at {peak:.2f}, normalized")
    write_wav(out_path, out, SAMPLE_RATE)
    return warnings


def render_sample_stems(project: SongProject) -> dict:
    cfg = get_config()
    results: dict = {"rendered": [], "skipped": [], "errors": [], "warnings": []}
    sample_tracks = [t for t in project.tracks if t.track_type == "sample"
                     and any(c.clip_type == "sample" for c in t.clips)]
    if not sample_tracks:
        results["skipped"].append("no sample tracks with clips")
        return results

    from ..midi_export import _safe_name as _safe
    for track in sample_tracks:
        fp = track_fingerprint(project, track)
        existing = next((s for s in project.stems
                         if s.track_id == track.id and s.stem_type == "sample"), None)
        if existing and existing.source_fingerprint == fp \
                and (cfg.root / existing.path).exists():
            results["skipped"].append(f"{track.name}: up to date")
            continue
        out_path = cfg.stems_dir / project.id / f"sample_{_safe(track.name)}_{track.id[:8]}.wav"
        try:
            warnings = render_sample_track(project, track, out_path)
            results["warnings"].extend(warnings)
        except Exception as e:
            results["errors"].append(f"{track.name}: {e}")
            continue
        rel = out_path.relative_to(cfg.root).as_posix()
        project.stems = [s for s in project.stems
                         if not (s.track_id == track.id and s.stem_type == "sample")]
        stem = StemRef(track_id=track.id, stem_type="sample", path=rel,
                       source_fingerprint=fp)
        _register_stem_asset(stem, track.name, "rendered_stem")
        project.stems.append(stem)
        results["rendered"].append({"track": track.name, "path": rel})

    from .waveforms import update_waveform_cache
    update_waveform_cache(project)
    return results
