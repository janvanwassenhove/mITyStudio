"""On-demand installation of the heavyweight neural voice stack (torch + XTTS)
into the venv the backend is already running in.

The desktop bundle ships only the core requirements; this lets the Voices
screen install the optional voice engine with one click, picking the torch
build that matches the detected device (CUDA > MPS > CPU). The job runs in a
background thread writing to a log the UI polls — torch alone is a multi-GB
download, so this can take several minutes.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_config

log = logging.getLogger(__name__)

# module-level job state (one install at a time)
_lock = threading.Lock()
_state = {"installing": False, "returncode": None, "started_at": None,
          "finished_at": None}


def _log_path() -> Path:
    p = get_config().analysis_cache_dir / "voice-engine-install.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _requirements_path() -> Path:
    # requirements-voice.txt sits at the studio-api root, alongside app/ (dev),
    # or in backend/ next to app/ (packaged desktop) — both are parents[2].
    return Path(__file__).resolve().parents[2] / "requirements-voice.txt"


def _torch_command(device: str) -> list[str]:
    base = [sys.executable, "-m", "pip", "install", "--no-input",
            "torch", "torchaudio"]
    if device == "cuda":
        return base + ["--index-url", "https://download.pytorch.org/whl/cu124"]
    return base   # MPS/CPU wheels come from the default index


def _run(device: str) -> None:
    reqs = _requirements_path()
    steps: list[list[str]] = [_torch_command(device)]
    if reqs.exists():
        steps.append([sys.executable, "-m", "pip", "install", "--no-input",
                      "-r", str(reqs)])
    else:
        log.warning("requirements-voice.txt not found at %s", reqs)

    rc = 0
    with _log_path().open("w", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now(timezone.utc).isoformat()}] installing voice "
                 f"engine (device={device})\n")
        fh.write(f"requirements: {reqs}\n\n")
        fh.flush()
        for cmd in steps:
            fh.write(f"$ {' '.join(cmd)}\n")
            fh.flush()
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                  text=True)
            rc = proc.returncode
            if rc != 0:
                fh.write(f"\n[failed] exit code {rc}\n")
                break
        if rc == 0:
            fh.write("\n[done] voice engine installed. "
                     "Restart the app if previews don't work immediately.\n")

    with _lock:
        _state.update(installing=False, returncode=rc,
                      finished_at=datetime.now(timezone.utc).isoformat())
    if rc == 0:
        # the capability probes are cached — bust them so status flips to ready
        from .capabilities import detect_capabilities, voice_clone_available
        detect_capabilities.cache_clear()
        voice_clone_available.cache_clear()


def start_install() -> dict:
    """Kick off the install in the background. Idempotent while running."""
    from .capabilities import voice_clone_available
    if voice_clone_available():
        return {"started": False, "reason": "already_installed"}
    with _lock:
        if _state["installing"]:
            return {"started": False, "reason": "already_installing"}
        from .voice_wizard import detect_device
        device = detect_device().get("device", "cpu")
        _state.update(installing=True, returncode=None,
                      started_at=datetime.now(timezone.utc).isoformat(),
                      finished_at=None)
    threading.Thread(target=_run, args=(device,), daemon=True).start()
    return {"started": True, "device": device}


def install_status(log_lines: int = 60) -> dict:
    from .capabilities import voice_clone_available
    tail: list[str] = []
    p = _log_path()
    if p.exists():
        try:
            tail = p.read_text(encoding="utf-8", errors="replace").splitlines()[-log_lines:]
        except OSError:
            tail = []
    with _lock:
        st = dict(_state)
    return {"installed": voice_clone_available(),
            "installing": st["installing"],
            "returncode": st["returncode"],
            "started_at": st["started_at"],
            "finished_at": st["finished_at"],
            "log": tail}
