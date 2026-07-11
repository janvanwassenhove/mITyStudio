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
    import re
    import time

    logs = _applio_dir() / "logs" / model_name_for_profile(profile)
    weights, index = find_model_files(profile)

    # progress: epoch encoded in checkpoint names (voice_x_175e_21875s.pth)
    current_epoch = 0
    last_checkpoint_at = None
    if logs.exists():
        for w in logs.glob("*_*e_*s.pth"):
            m = re.search(r"_(\d+)e_", w.name)
            if m:
                current_epoch = max(current_epoch, int(m.group(1)))
        ckpts = list(logs.glob("G_*.pth"))
        if ckpts:
            last_checkpoint_at = max(c.stat().st_mtime for c in ckpts)

    # stage from the training job log (track the block for this model)
    stage = None
    job_log = get_config().root / "tools" / "rvc-training.log"
    if job_log.exists():
        model = model_name_for_profile(profile)
        in_model = False
        for line in job_log.read_text(encoding="utf-8",
                                      errors="replace").splitlines():
            if "=== training" in line:
                in_model = model in line
                if in_model:
                    stage = "preparing"
            elif in_model:
                if "COMPLETE" in line:
                    stage = "complete"
                    in_model = False
                elif "FAILED" in line:
                    stage = "failed"
                    in_model = False
                elif "--- " in line:
                    stage = line.split("--- ")[1].split(":")[0].strip()

    training_active = (last_checkpoint_at is not None
                       and time.time() - last_checkpoint_at < 45 * 60
                       and stage not in ("complete", "failed"))
    return {
        "profile_id": profile.id,
        "model_name": model_name_for_profile(profile),
        "rvc_installed": rvc_available(),
        "training_started": logs.exists(),
        "stage": stage,
        "current_epoch": current_epoch,
        "total_epochs": 200,
        "training_active": training_active,
        "ready": weights is not None,
        "weights": weights.name if weights else None,
        "indexed": index is not None,
    }


def convert_stem(in_wav: Path, out_wav: Path, profile,
                 autotune: bool = True) -> list[str]:
    """Convert a vocal stem to the profile's trained voice. Returns warnings
    (empty on success). The input is left untouched on failure.

    autotune: RVC's f0 tracking adds pitch noise (~2× the source's cents
    error, measured). Our melodies are semitone-exact, so snapping RVC's f0
    toward the nearest semitone recovers pitch fidelity for singing. Disable
    for spoken-word/rap material where natural pitch must survive."""
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
    if autotune:
        cmd += ["--f0_autotune", "True", "--f0_autotune_strength", "0.8"]
    try:
        proc = subprocess.run(cmd, cwd=str(_applio_dir()),
                              capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return ["RVC conversion timed out — stem kept unconverted"]
    if proc.returncode != 0 or not out_wav.exists():
        tail = (proc.stderr or proc.stdout or "").strip()[-400:]
        log.warning("RVC conversion failed: %s", tail)
        return [f"RVC conversion failed ({tail[:120]}…) — stem kept unconverted"]
    # defensive: RVC can "succeed" yet emit silence (e.g. on long, sparse
    # input). Treat a silent result as a failure so the caller keeps the
    # audible cloned voice instead of writing a dead stem.
    try:
        import numpy as np
        import soundfile as sf
        data, _ = sf.read(str(out_wav), dtype="float32")
        if data.size and float(np.abs(data).max()) < 0.005:
            log.warning("RVC produced silence for %s", profile.name)
            return ["RVC produced a silent result — keeping the cloned voice"]
    except Exception:  # noqa: BLE001
        pass
    return []
