"""Per-clip fade in/out envelopes for MIDI (instrument & vocal) stems.

Sample clips apply their fades while being placed (sample_renderer); MIDI
clips render through FluidSynth / the singing engines into a whole-track
stem, so their fades are applied afterwards as gain ramps over each clip's
time window. Fade values live on the Clip model and are part of the track
fingerprint — changing them re-renders the stem automatically.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ...models.song import SongProject, Track
from .. import timing
from ..audio_io import AudioReadError, read_audio, write_wav

log = logging.getLogger(__name__)


def apply_midi_clip_fades(project: SongProject, track: Track,
                          stem_path: Path) -> list[str]:
    """Apply fade_in/fade_out of the track's MIDI clips to its rendered stem.
    Returns log lines (empty when no clip has fades)."""
    faded = [c for c in track.clips
             if c.clip_type == "midi"
             and ((c.fade_in_seconds or 0) > 0 or (c.fade_out_seconds or 0) > 0)]
    if not faded or not stem_path.exists():
        return []
    try:
        data, rate = read_audio(stem_path)
    except AudioReadError as e:
        return [f"{track.name}: fades skipped ({e})"]
    n = len(data)
    for c in faded:
        t0 = timing.beats_to_seconds(project, c.start_beat)
        t1 = timing.beats_to_seconds(project, c.start_beat + c.duration_beats)
        s0 = max(int(t0 * rate), 0)
        s1 = min(int(t1 * rate), n)
        if s1 <= s0:
            continue
        span = s1 - s0
        fi = min(int((c.fade_in_seconds or 0) * rate), span)
        fo = min(int((c.fade_out_seconds or 0) * rate), span)
        if fi > 0:
            data[s0:s0 + fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
        if fo > 0:
            data[s1 - fo:s1] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    write_wav(stem_path, data, rate)
    return [f"{track.name}: applied fades to {len(faded)} clip(s)"]
