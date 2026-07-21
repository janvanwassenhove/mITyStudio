"""Detect optional external tools (FluidSynth, ffmpeg) without crashing.

The desktop app bootstraps its own copies and points at them via
MITY_FLUIDSYNTH_PATH / MITY_FFMPEG_PATH; PATH lookup is the dev fallback.
"""
from __future__ import annotations

import importlib.util
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
        # The AI voice-cloning stack (XTTS/torch) is a heavyweight optional
        # add-on the desktop bundle does not ship by default — probe for it
        # cheaply (find_spec does NOT import torch) so the UI can explain its
        # absence instead of hard-failing "voice engine not installed".
        "voice_clone": voice_clone_available(),
        # local face identification for voice profiles (OpenCV YuNet+SFace);
        # false until the ~37 MB models are downloaded on demand
        "face_id": face_id_available(),
    }


def face_id_available() -> bool:
    try:
        from .face_id import available
        return available()
    except Exception:  # noqa: BLE001 — a missing model must not 500 /health
        return False


@lru_cache(maxsize=1)
def voice_clone_available() -> bool:
    # honour the same kill-switch the engine selection uses (tests set this)
    if os.environ.get("MITY_DISABLE_CLONE_ENGINE"):
        return False
    try:
        return all(importlib.util.find_spec(m) is not None
                   for m in ("torch", "TTS"))
    except Exception:  # noqa: BLE001 — a broken partial install shouldn't 500
        return False


def fluidsynth_path() -> str | None:
    return _tool("MITY_FLUIDSYNTH_PATH", "fluidsynth")


def ffmpeg_path() -> str | None:
    return _tool("MITY_FFMPEG_PATH", "ffmpeg")
