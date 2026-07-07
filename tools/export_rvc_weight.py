"""Export the small RVC inference weight from a trained G_*.pth checkpoint.

Usage (Applio venv, from tools/Applio):
  .venv/Scripts/python.exe ../export_rvc_weight.py <model_name>

Writes logs/<model>/<model>_final.pth — the file the studio's RVC converter
looks for. CPU-only, safe to run while another model trains.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import torch

APPLIO = Path(__file__).resolve().parent / "Applio"
os.chdir(APPLIO)
sys.path.insert(0, str(APPLIO))

from rvc.train.process.extract_model import extract_model  # noqa: E402


class HP:
    def __init__(self, d: dict):
        for k, v in d.items():
            setattr(self, k, HP(v) if isinstance(v, dict) else v)


def main(model_name: str) -> None:
    logs = APPLIO / "logs" / model_name
    g = sorted(logs.glob("G_*.pth"), key=lambda p: p.stat().st_mtime)
    if not g:
        print(f"no G_*.pth checkpoint in {logs}")
        sys.exit(1)
    ckpt_file = g[-1]
    print("loading", ckpt_file.name)
    ckpt = torch.load(str(ckpt_file), map_location="cpu", weights_only=False)
    state = ckpt["model"] if "model" in ckpt else ckpt
    epoch = ckpt.get("iteration", 0)

    with open(logs / "config.json", encoding="utf-8") as f:
        hps = HP(json.load(f))
    sr = hps.data.sample_rate

    out = logs / f"{model_name}_final.pth"
    extract_model(
        ckpt=state, sr=sr, name=model_name, model_path=str(out),
        epoch=epoch, step=ckpt.get("global_step", 0) or 0, hps=hps,
        overtrain_info="", vocoder="HiFi-GAN", pitch_guidance=True,
        version="v2",
    )
    if out.exists():
        print("exported", out, f"({out.stat().st_size / 1e6:.1f} MB)")
    else:
        print("export failed — no output written")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
