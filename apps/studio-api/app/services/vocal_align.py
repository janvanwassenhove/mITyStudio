"""Forced alignment of cloned speech to its lyric text (torchaudio MMS_FA).

The singing pipeline must know exactly where each syllable lives inside the
XTTS-spoken line to map it onto its note. Guessing boundaries from text
proportions + energy valleys (the previous method) garbles words whenever the
guess is off. MMS_FA is a multilingual (1100+ languages, incl. en/nl/fr/de)
CTC forced aligner built into torchaudio: it returns per-character time spans,
giving us phoneme-accurate syllable cuts AND the vowel onset within each
syllable (so consonants can lead the beat like a real singer).

Heavy model (~1.2 GB, cached by torch hub) loaded lazily; every public entry
degrades to None so callers fall back to the heuristic cuts.
"""
from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

_bundle_model = None
_bundle_dict: dict | None = None
_align_failed: str | None = None

_VOWELS = set("aeiouy")


def _fold_char(ch: str) -> str:
    """Deterministic per-character fold to the aligner's a-z' alphabet.
    Per-char so that fold(word) == concat(fold(syllable)) always holds."""
    if ch == "ß":
        return "ss"
    d = unicodedata.normalize("NFD", ch)
    base = "".join(c for c in d if not unicodedata.combining(c)).lower()
    return "".join(c for c in base if c.isalpha() and c.isascii() or c == "'")


def _fold(text: str) -> str:
    return "".join(_fold_char(c) for c in text)


def _get_aligner():
    global _bundle_model, _bundle_dict, _align_failed
    if _bundle_model is not None:
        return _bundle_model, _bundle_dict
    if _align_failed:
        raise RuntimeError(_align_failed)
    try:
        import torch
        from torchaudio.pipelines import MMS_FA
        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info("loading MMS_FA forced aligner on %s "
                 "(first run downloads ~1.2 GB)…", device)
        _bundle_model = MMS_FA.get_model(with_star=False).to(device)
        _bundle_dict = MMS_FA.get_dict(star=None)
    except Exception as e:  # noqa: BLE001
        _align_failed = f"MMS_FA unavailable: {e}"
        raise RuntimeError(_align_failed) from e
    return _bundle_model, _bundle_dict


def _align_words(audio: np.ndarray, rate: int,
                 words: list[str]) -> list[list[tuple[float, float]]]:
    """Char-level spans per word: [[(start_s, end_s), …chars…], …words…].
    Words must already be folded (a-z' only, non-empty)."""
    import torch
    import torchaudio
    import torchaudio.functional as F

    model, dictionary = _get_aligner()
    device = next(model.parameters()).device

    wav = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))
    wav = wav.unsqueeze(0)
    if rate != 16000:
        wav = torchaudio.functional.resample(wav, rate, 16000)
    with torch.inference_mode():
        emission, _ = model(wav.to(device))
    emission = emission.cpu()

    tokens = [dictionary[c] for w in words for c in w]
    targets = torch.tensor([tokens], dtype=torch.int32)
    aligned, scores = F.forced_align(emission, targets, blank=0)
    spans = F.merge_tokens(aligned[0], scores[0])

    n_frames = emission.size(1)
    spf = (len(wav[0]) / 16000) / n_frames   # seconds per emission frame
    out: list[list[tuple[float, float]]] = []
    it = iter(spans)
    for w in words:
        chs = []
        for _ in w:
            s = next(it)
            chs.append((s.start * spf, s.end * spf))
        out.append(chs)
    return out


def align_syllables(audio: np.ndarray, rate: int, line_text: str,
                    syllables: list[str],
                    cache_path: Path | None = None) -> dict | None:
    """Phoneme-accurate syllable layout for one spoken line.

    Returns {"cuts": [n+1 sample indices], "vowel_at": [n sample indices]}
    where cuts are contiguous boundaries (midpoints between adjacent syllable
    spans, so whole phonemes stay in their segment) and vowel_at[i] is the
    sample where syllable i's first vowel starts (== cuts[i] when unknown).
    None when alignment is unavailable or the text doesn't match.
    """
    if cache_path is not None and cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if len(data.get("cuts", [])) == len(syllables) + 1:
                return data
        except (OSError, json.JSONDecodeError):
            pass

    from .lyric_text import WORD_RE, word_syllables
    raw_words = WORD_RE.findall(line_text)
    word_syls = [word_syllables(w) for w in raw_words]
    if [s for ws in word_syls for s in ws] != list(syllables):
        # melody used a different split (e.g. edited lyrics) — realign by
        # folding: give up only if even total text differs
        flat = _fold("".join(syllables))
        if flat != _fold("".join(raw_words)):
            return None
        # distribute this line's syllables over words by consuming chars
        word_syls, i = [], 0
        for w in raw_words:
            need, taken = len(_fold(w)), []
            while need > 0 and i < len(syllables):
                taken.append(syllables[i])
                need -= len(_fold(syllables[i]))
                i += 1
            word_syls.append(taken)

    folded = [_fold(w) for w in raw_words]
    keep = [(fw, ws) for fw, ws in zip(folded, word_syls) if fw]
    if not keep:
        return None
    try:
        char_spans = _align_words(audio, rate, [fw for fw, _ in keep])
    except Exception as e:  # noqa: BLE001
        log.debug("forced alignment failed: %s", e)
        return None

    # per-syllable (start, end, vowel_start) in seconds, via char allocation
    syl_spans: list[tuple[float, float, float]] = []
    for (fw, ws), chars in zip(keep, char_spans):
        pos = 0
        for syl in ws:
            n = len(_fold(syl))
            chs = chars[pos:pos + n] or chars[-1:]
            pos += n
            s0, s1 = chs[0][0], chs[-1][1]
            fs = _fold(syl)
            vidx = next((k for k, c in enumerate(fs) if c in _VOWELS), 0)
            vstart = chs[min(vidx, len(chs) - 1)][0]
            syl_spans.append((s0, s1, vstart))
    if len(syl_spans) != len(syllables):
        return None

    # contiguous cuts: midpoints between adjacent spans keep whole phonemes
    cuts = [0]
    for i in range(1, len(syl_spans)):
        mid = (syl_spans[i - 1][1] + syl_spans[i][0]) / 2
        cuts.append(max(int(mid * rate), cuts[-1] + 1))
    cuts.append(len(audio))
    vowel_at = [min(max(int(v * rate), cuts[i]), cuts[i + 1] - 1)
                for i, (_s0, _s1, v) in enumerate(syl_spans)]
    result = {"cuts": cuts, "vowel_at": vowel_at}

    if cache_path is not None:
        try:
            cache_path.write_text(json.dumps(result), encoding="utf-8")
        except OSError:
            pass
    return result
