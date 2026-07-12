"""Content-based audio tagging + semantic embeddings via CLAP.

Filenames lie or say nothing ("loop_final_2.wav") — CLAP (contrastive
language-audio pretraining, laion/clap-htsat-unfused via the transformers
already installed for XTTS) hears the audio itself. One model provides:

- zero-shot CONTENT TAGS against a curated music-production vocabulary
  (kick, snare, synth pad, vocal chop, riser…) stored in the sample analysis
- a joint text↔audio EMBEDDING space: the chat retrieval embeds the user's
  request and ranks samples by what they SOUND like, not what they're named.

This is the modern successor to YAMNet-class tagging: YAMNet's 521 AudioSet
event classes (2019, TensorFlow) are generic environmental sounds; CLAP is
music-caption trained, vocabulary-free, and does retrieval embeddings with
the same weights. ~600 MB, cached by HF hub, GPU-accelerated, lazy-loaded.

Everything degrades gracefully: no model / no GPU / disabled via
MITY_DISABLE_AUDIO_TAGGING=1 → analysis simply omits content tags.
"""
from __future__ import annotations

import logging
import os

import numpy as np

log = logging.getLogger(__name__)

_MODEL_ID = "laion/clap-htsat-unfused"
_CLAP_RATE = 48000
_MAX_SECONDS = 10.0          # CLAP window; longer samples use their start

# music-production vocabulary for zero-shot tagging (label → stored tag)
LABELS = {
    "a kick drum hit": "kick",
    "a snare drum hit": "snare",
    "hi-hat cymbals": "hihat",
    "a crash cymbal": "cymbal",
    "a full drum loop groove": "drum-loop",
    "hand percussion like congas and bongos": "percussion",
    "a deep 808 sub bass": "808",
    "an electric bass guitar line": "bassline",
    "a synthesizer bass line": "synth-bass",
    "an electric guitar riff": "electric-guitar",
    "an acoustic guitar": "acoustic-guitar",
    "a piano melody": "piano",
    "an electric piano or rhodes": "electric-piano",
    "a hammond organ": "organ",
    "a synthesizer lead melody": "synth-lead",
    "a warm synthesizer pad": "synth-pad",
    "an orchestral string section": "strings",
    "a brass section": "brass",
    "a flute melody": "flute",
    "bells or chimes": "bells",
    "a plucked synthesizer arpeggio": "arp",
    "a person singing": "vocals",
    "chopped vocal samples": "vocal-chop",
    "a person speaking": "spoken",
    "a choir singing": "choir",
    "a riser or uplifter sound effect": "riser",
    "a cinematic impact or hit": "impact",
    "a whoosh or sweep sound effect": "sweep",
    "atmospheric ambient texture": "ambient",
    "vinyl crackle and noise": "noise",
}

_model = None
_processor = None
_label_embeds: np.ndarray | None = None
_failed: str | None = None


def available() -> bool:
    if os.environ.get("MITY_DISABLE_AUDIO_TAGGING"):
        return False
    if _failed:
        return False
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _get_clap():
    global _model, _processor, _failed
    if _model is not None:
        return _model, _processor
    if _failed:
        raise RuntimeError(_failed)
    try:
        import torch
        from transformers import ClapModel, ClapProcessor
        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info("loading CLAP (%s) on %s — first run downloads ~600 MB…",
                 _MODEL_ID, device)
        _model = ClapModel.from_pretrained(_MODEL_ID).to(device).eval()
        _processor = ClapProcessor.from_pretrained(_MODEL_ID)
    except Exception as e:  # noqa: BLE001
        _failed = f"CLAP unavailable: {e}"
        raise RuntimeError(_failed) from e
    return _model, _processor


def _label_matrix() -> np.ndarray:
    """Normalized text embeddings of the label vocabulary (computed once)."""
    global _label_embeds
    if _label_embeds is None:
        _label_embeds = _embed_texts(list(LABELS.keys()))
    return _label_embeds


def _embed_texts(texts: list[str]) -> np.ndarray:
    import torch
    model, processor = _get_clap()
    device = next(model.parameters()).device
    inputs = processor(text=texts, return_tensors="pt",
                       padding=True).to(device)
    with torch.inference_mode():
        emb = model.get_text_features(**inputs)
    emb = emb.cpu().numpy()
    return emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)


def embed_text(query: str) -> list[float] | None:
    """Normalized CLAP text embedding for a retrieval query."""
    try:
        return _embed_texts([query])[0].tolist()
    except Exception as e:  # noqa: BLE001
        log.debug("CLAP text embed failed: %s", e)
        return None


def tag_audio(mono: np.ndarray, rate: int,
              top_k: int = 3, min_score: float = 0.35) -> dict | None:
    """Zero-shot content tags + retrieval embedding for one sample.
    Returns {"content_tags": [...], "clap_embedding": [512 floats]} or None.
    """
    try:
        import torch
        from .audio_io import resample_linear
        model, processor = _get_clap()
        device = next(model.parameters()).device

        if rate != _CLAP_RATE:
            mono = resample_linear(
                mono.astype(np.float32)[:, None], rate, _CLAP_RATE)[:, 0]
        mono = mono[: int(_MAX_SECONDS * _CLAP_RATE)]
        if len(mono) < _CLAP_RATE // 10:
            return None

        inputs = processor(audios=[mono], sampling_rate=_CLAP_RATE,
                           return_tensors="pt").to(device)
        with torch.inference_mode():
            a = model.get_audio_features(**inputs).cpu().numpy()[0]
        a = a / (np.linalg.norm(a) + 1e-9)

        sims = _label_matrix() @ a
        order = np.argsort(-sims)
        tags = [list(LABELS.values())[i] for i in order[:top_k]
                if sims[i] >= min_score]
        # always keep the single best guess even under threshold
        if not tags:
            tags = [list(LABELS.values())[order[0]]]
        return {"content_tags": tags,
                "clap_embedding": [round(float(v), 5) for v in a]}
    except Exception as e:  # noqa: BLE001
        log.debug("CLAP tagging failed: %s", e)
        return None
