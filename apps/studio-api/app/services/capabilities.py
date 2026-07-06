"""Detect optional external tools (FluidSynth, ffmpeg) without crashing."""
from __future__ import annotations

import shutil
from functools import lru_cache


@lru_cache(maxsize=1)
def detect_capabilities() -> dict:
    return {
        "fluidsynth": shutil.which("fluidsynth") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
    }


def fluidsynth_path() -> str | None:
    return shutil.which("fluidsynth")


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")
