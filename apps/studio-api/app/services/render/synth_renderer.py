"""SynthRenderer: instrument tracks → WAV stems via the built-in synth engine.

Renders from the track's note events directly (no MIDI/FluidSynth), the same
way sample_renderer places sample clips on the timeline. This is the guaranteed
default when no SoundFont/FluidSynth is available, and the explicit choice when
a track has an assigned synth patch.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ...models.song import SongProject, Track
from .. import timing
from ..audio_io import write_wav
from . import synth_engine
from .soundfont_renderer import SAMPLE_RATE, InstrumentRenderer

log = logging.getLogger(__name__)


class SynthRenderer(InstrumentRenderer):
    def render_track(self, project: SongProject, track: Track,
                     midi_path: Path, out_path: Path) -> list[str]:
        cfg = track.instrument_config
        is_drum = cfg.is_drum_kit or track.track_type == "drums"
        patch_id = cfg.synth_patch or synth_engine.default_patch(track.track_type)
        if is_drum:
            patch_id = "drum_kit"
        patch = synth_engine.get_patch(patch_id)
        if patch is None:
            patch = synth_engine.get_patch(
                synth_engine.default_patch(track.track_type))

        total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
        out = np.zeros((total, 2), dtype=np.float32)
        notes = 0
        for clip in track.clips:
            if clip.clip_type != "midi":
                continue
            for note in clip.note_events:
                start_beat = clip.start_beat + note.start_beat
                dur = timing.beats_to_seconds(project, note.duration_beats)
                start = int(timing.beats_to_seconds(project, start_beat)
                            * SAMPLE_RATE)
                if start >= total:
                    continue
                mono = synth_engine.render_note(patch, note.midi_note, dur,
                                                note.velocity, SAMPLE_RATE)
                end = min(start + len(mono), total)
                seg = mono[:end - start]
                out[start:end, 0] += seg
                out[start:end, 1] += seg
                notes += 1

        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 1.0:
            out /= peak
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_wav(out_path, out, SAMPLE_RATE)
        return [f"rendered with built-in synth patch {patch.label!r} "
                f"({notes} notes)"]
