"""Train per-voice RVC models from the studio's voice profiles (async job).

Run with the Applio venv python from the tools/Applio directory:
  tools/Applio/.venv/Scripts/python.exe tools/train_rvc.py

For every consented voice profile with source recordings it:
  1. builds a dataset folder (decoded wav copies — originals untouched)
  2. Applio preprocess → extract (rmvpe f0 + contentvec) → train → index
  3. leaves weights in tools/Applio/logs/voice_<profile>/ where the studio's
     RVC converter picks them up automatically on the next vocal render.

Progress is written to tools/rvc-training.log. Checkpoints save every
25 epochs, so partially-trained voices already improve renders.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLIO = ROOT / "tools" / "Applio"
PYTHON = APPLIO / ".venv" / "Scripts" / "python.exe"
LOG = ROOT / "tools" / "rvc-training.log"

SAMPLE_RATE = "40000"
EPOCHS = "200"
BATCH = "4"           # fits an 8 GB RTX 3050
SAVE_EVERY = "25"


def log(msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(args: list[str], step: str) -> bool:
    log(f"--- {step}: {' '.join(args[2:6])} …")
    proc = subprocess.run([str(PYTHON), "core.py", *args], cwd=str(APPLIO),
                          capture_output=True, text=True)
    tail = (proc.stdout or "")[-600:] + (proc.stderr or "")[-600:]
    if proc.returncode != 0:
        log(f"{step} FAILED (rc={proc.returncode}): {tail}")
        return False
    log(f"{step} done")
    return True


def profiles() -> list[dict]:
    with urllib.request.urlopen("http://127.0.0.1:8000/api/voice/profiles") as r:
        return json.load(r)


def recording_paths(profile: dict) -> list[Path]:
    out = []
    with urllib.request.urlopen("http://127.0.0.1:8000/api/assets/voice-recordings") as r:
        recs = {a["id"]: a for a in json.load(r)}
    for rid in profile["source_recording_ids"]:
        a = recs.get(rid)
        if a and not a["is_missing"]:
            out.append(Path(a["original_path"]))
    return out


def prepare_dataset(model: str, sources: list[Path]) -> Path:
    ds = ROOT / "tools" / "rvc-datasets" / model
    ds.mkdir(parents=True, exist_ok=True)
    for i, src in enumerate(sources):
        dest = ds / f"take_{i}.wav"
        if dest.exists():
            continue
        if src.suffix.lower() == ".wav":
            shutil.copy2(src, dest)
        else:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                            "-ar", "44100", "-ac", "1", str(dest)], check=True)
    return ds


def train_voice(profile: dict) -> None:
    model = f"voice_{profile['id'][:12]}"
    weights = list((APPLIO / "logs" / model).glob("*.pth"))
    if any(not w.name.startswith(("D_", "G_")) for w in weights):
        log(f"{model} already has weights — skipping")
        return
    sources = recording_paths(profile)
    if not sources:
        log(f"{model}: no usable recordings, skipping")
        return
    log(f"=== training {model} ({profile['name']}) from "
        f"{len(sources)} recording(s) ===")
    ds = prepare_dataset(model, sources)

    if not run(["preprocess", "--model_name", model,
                "--dataset_path", str(ds),
                "--sample_rate", SAMPLE_RATE,
                "--cut_preprocess", "Automatic",
                "--cpu_cores", "4",
                "--process_effects", "True",
                "--noise_reduction", "False",
                "--chunk_len", "3.0",
                "--overlap_len", "0.3",
                "--normalization_mode", "post"], "preprocess"):
        return
    if not run(["extract", "--model_name", model,
                "--f0_method", "rmvpe",
                "--sample_rate", SAMPLE_RATE,
                "--cpu_cores", "4",
                "--gpu", "0",
                "--embedder_model", "contentvec",
                "--include_mutes", "2"], "extract"):
        return
    if not run(["train", "--model_name", model,
                "--sample_rate", SAMPLE_RATE,
                "--total_epoch", EPOCHS,
                "--batch_size", BATCH,
                "--save_every_epoch", SAVE_EVERY,
                "--save_every_weights", "True",
                "--save_only_latest", "True",
                "--gpu", "0",
                "--vocoder", "HiFi-GAN",
                "--pretrained", "True",
                "--custom_pretrained", "False",
                "--cache_data_in_gpu", "False",
                "--checkpointing", "False",
                "--overtraining_detector", "False",
                "--overtraining_threshold", "50",
                "--cleanup", "False",
                "--index_algorithm", "Auto"], "train"):
        return
    run(["index", "--model_name", model, "--index_algorithm", "Auto"], "index")
    log(f"=== {model} COMPLETE ===")


def main() -> None:
    log("RVC training job starting")
    for p in profiles():
        if p.get("consent_confirmed") and p.get("source_recording_ids"):
            train_voice(p)
    log("RVC training job finished")


if __name__ == "__main__":
    main()
