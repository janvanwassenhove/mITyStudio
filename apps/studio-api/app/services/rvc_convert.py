"""RVC voice conversion: the final fidelity stage of the vocal pipeline.

A per-voice RVC model is trained (async, GPU) on the profile's source
recordings via Applio (tools/Applio, own venv). Once weights exist, every
rendered vocal stem is passed through the model — the sung output keeps its
melody and words but gains the trained voice's true timbre (this is the
ElevenLabs-class step: a model trained on THIS voice, not zero-shot).

Runs as a subprocess against the Applio venv, like FluidSynth — missing
models/tools degrade gracefully (the stem stays as-is with a warning).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ..config import get_config

log = logging.getLogger(__name__)


def _applio_dir() -> Path:
    return get_config().root / "tools" / "Applio"


def _applio_python() -> Path:
    return _applio_dir() / ".venv" / "Scripts" / "python.exe"


def rvc_available() -> bool:
    return _applio_python().exists() and (_applio_dir() / "core.py").exists()


def model_name_for_profile(profile) -> str:
    return f"voice_{profile.id[:12]}"


def find_model_files(profile) -> tuple[Path | None, Path | None]:
    """(weights .pth, faiss .index) for the profile's trained model —
    newest checkpoint wins. None if not trained yet."""
    logs = _applio_dir() / "logs" / model_name_for_profile(profile)
    if not logs.exists():
        return None, None
    weights = sorted(logs.glob("*.pth"), key=lambda p: p.stat().st_mtime)
    weights = [w for w in weights
               if not w.name.startswith(("D_", "G_"))]  # skip raw checkpoints
    index = sorted(logs.glob("*.index"), key=lambda p: p.stat().st_mtime)
    return (weights[-1] if weights else None,
            index[-1] if index else None)


def rvc_model_ready(profile) -> bool:
    return rvc_available() and find_model_files(profile)[0] is not None


def training_status(profile) -> dict:
    logs = _applio_dir() / "logs" / model_name_for_profile(profile)
    weights, index = find_model_files(profile)
    return {
        "profile_id": profile.id,
        "model_name": model_name_for_profile(profile),
        "rvc_installed": rvc_available(),
        "training_started": logs.exists(),
        "ready": weights is not None,
        "weights": weights.name if weights else None,
        "indexed": index is not None,
    }


def convert_stem(in_wav: Path, out_wav: Path, profile) -> list[str]:
    """Convert a vocal stem to the profile's trained voice. Returns warnings
    (empty on success). The input is left untouched on failure."""
    weights, index = find_model_files(profile)
    if weights is None:
        return [f"RVC model for {profile.name!r} not trained yet — "
                "using the cloned voice as-is"]
    cmd = [str(_applio_python()), "core.py", "infer",
           "--input_path", str(in_wav.resolve()),
           "--output_path", str(out_wav.resolve()),
           "--pth_path", str(weights.resolve()),
           "--index_path", str(index.resolve()) if index else "",
           "--f0_method", "rmvpe",
           "--pitch", "0",
           "--index_rate", "0.66",
           "--protect", "0.33",
           "--export_format", "WAV"]
    try:
        proc = subprocess.run(cmd, cwd=str(_applio_dir()),
                              capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return ["RVC conversion timed out — stem kept unconverted"]
    if proc.returncode != 0 or not out_wav.exists():
        tail = (proc.stderr or proc.stdout or "").strip()[-400:]
        log.warning("RVC conversion failed: %s", tail)
        return [f"RVC conversion failed ({tail[:120]}…) — stem kept unconverted"]
    return []
