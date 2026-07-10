"""Detect optional external tools (FluidSynth, ffmpeg) without crashing.

The desktop app bootstraps its own copies and points at them via
MITY_FLUIDSYNTH_PATH / MITY_FFMPEG_PATH; PATH lookup is the dev fallback.
"""
from __future__ import annotations

import os
import shutil
from functools import lru_cache


def _tool(env_var: str, name: str) -> str | None:
    override = os.environ.get(env_var)
    if override and os.path.exists(override):
        return override
    return shutil.which(name)


@lru_cache(maxsize=1)
def detect_capabilities() -> dict:
    return {
        "fluidsynth": fluidsynth_path() is not None,
        "ffmpeg": ffmpeg_path() is not None,
    }


def fluidsynth_path() -> str | None:
    return _tool("MITY_FLUIDSYNTH_PATH", "fluidsynth")


def ffmpeg_path() -> str | None:
    return _tool("MITY_FFMPEG_PATH", "ffmpeg")
