"""True singing-voice synthesis (SVS): DiffSinger voicebanks as the vocal
source — the quality rung above speech-to-singing.

The XTTS chain reshapes SPOKEN audio onto notes; a DiffSinger voicebank was
TRAINED to sing, so sustained vowels, transitions and phrasing come out
naturally. The studio drives any voicebank in the OpenUtau DiffSinger format
dropped into voices/svs/<bank>/ (the same drop-a-file philosophy as
soundfonts — the user obtains banks from their creators under the creators'
licenses; nothing is redistributed):

    voices/svs/MyBank/
        dsconfig.yaml       acoustic.onnx      phonemes.txt
        dsdict*.yaml        (optional embedded vocoder/)
    voices/svs/nsf_hifigan/ (shared vocoder, downloadable on demand)

We already know exactly WHAT to sing (1 note per syllable + phoneme dicts),
so only the acoustic model + vocoder are needed: tokens/durations/f0 are
built here — no variance/duration predictors, no OpenUtau process. The sung
lines then go through the SAME dense RVC stage as the clone engine, so the
result sings in the USER'S trained voice.

Everything degrades gracefully: no bank / no vocoder / no onnxruntime →
engine unavailable and the clone chain takes over.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..config import get_config
from ..models.song import SongProject, Track
from .audio_io import resample_linear, write_wav
from .vocal_engine import (SAMPLE_RATE, SingingVoiceEngine, VocalRenderResult,
                           build_lyrics_alignment)

log = logging.getLogger(__name__)

VOCODER_URL = ("https://github.com/xunmengshe/OpenUtau/releases/download/"
               "0.0.0.0/nsf_hifigan.oudep")

_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ']+")


def svs_dir() -> Path:
    return get_config().voices_dir / "svs"


def available() -> bool:
    if os.environ.get("MITY_DISABLE_SVS"):
        return False
    try:
        import onnxruntime  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


# ---------------------------------------------------------------------------
# voicebank + vocoder discovery/loading
# ---------------------------------------------------------------------------

def _read_yaml(path: Path) -> dict:
    import yaml
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


@dataclass
class Vocoder:
    dir: Path
    sample_rate: int = 44100
    hop_size: int = 512
    model_path: Path | None = None
    _session: object = field(default=None, repr=False)

    @property
    def frame_sec(self) -> float:
        return self.hop_size / self.sample_rate

    @classmethod
    def load(cls, d: Path) -> "Vocoder | None":
        cfgf = d / "vocoder.yaml"
        cfg = _read_yaml(cfgf) if cfgf.exists() else {}
        model = None
        name = cfg.get("model")
        if name and (d / name).exists():
            model = d / name
        else:
            cand = sorted(d.glob("*.onnx"))
            model = cand[0] if cand else None
        if model is None:
            return None
        return cls(dir=d, sample_rate=int(cfg.get("sample_rate", 44100)),
                   hop_size=int(cfg.get("hop_size", 512)), model_path=model)

    def session(self):
        if self._session is None:
            import onnxruntime as ort
            self._session = ort.InferenceSession(
                str(self.model_path), providers=["CPUExecutionProvider"])
        return self._session


@dataclass
class SvsBank:
    dir: Path
    name: str
    cfg: dict
    tokens: dict[str, int]                 # phoneme -> token id
    dsdict: dict[str, list[str]]           # word -> phonemes
    vowels: set[str]
    acoustic_path: Path
    vocoder: Vocoder | None
    _session: object = field(default=None, repr=False)

    def session(self):
        if self._session is None:
            import onnxruntime as ort
            self._session = ort.InferenceSession(
                str(self.acoustic_path), providers=["CPUExecutionProvider"])
        return self._session

    @classmethod
    def load(cls, d: Path) -> "SvsBank | None":
        cfg = _read_yaml(d / "dsconfig.yaml")
        ac = d / str(cfg.get("acoustic", "acoustic.onnx"))
        if not ac.exists():
            cand = sorted(d.glob("*acoustic*.onnx")) or sorted(d.glob("*.onnx"))
            ac = cand[0] if cand else ac
        if not ac.exists():
            return None

        # token list: phonemes.txt (one per line, index = id) or phonemes.json
        tokens: dict[str, int] = {}
        ph = d / str(cfg.get("phonemes", "phonemes.txt"))
        if ph.exists() and ph.suffix == ".txt":
            for i, line in enumerate(
                    ph.read_text(encoding="utf-8").splitlines()):
                if line.strip():
                    tokens[line.strip()] = i
        elif ph.with_suffix(".json").exists():
            import json
            tokens = {k: int(v) for k, v in json.loads(
                ph.with_suffix(".json").read_text(encoding="utf-8")).items()}
        if not tokens:
            return None

        # pronunciation dictionary + phoneme types (vowel detection)
        dsdict: dict[str, list[str]] = {}
        vowels: set[str] = set()
        for df in sorted(d.glob("dsdict*.yaml")):
            data = _read_yaml(df)
            for e in data.get("entries") or []:
                g = str(e.get("grapheme", "")).lower().strip()
                phs = [str(p) for p in (e.get("phonemes") or [])]
                if g and phs and g not in dsdict:
                    dsdict[g] = phs
            for s in data.get("symbols") or []:
                if str(s.get("type", "")) == "vowel":
                    vowels.add(str(s.get("symbol")))
        if not vowels:   # fallback: ARPAbet-ish vowels present in the tokens
            vowels = {t for t in tokens
                      if t[:2].lower() in ("aa", "ae", "ah", "ao", "aw", "ax",
                                           "ay", "eh", "er", "ey", "ih", "iy",
                                           "ow", "oy", "uh", "uw")}
        name = str(cfg.get("name") or d.name)
        vocoder = None
        for vd in (d / "vocoder", d):
            v = Vocoder.load(vd) if vd.exists() else None
            if v is not None and v.model_path != ac:
                vocoder = v
                break
        return cls(dir=d, name=name, cfg=cfg, tokens=tokens, dsdict=dsdict,
                   vowels=vowels, acoustic_path=ac, vocoder=vocoder)


def shared_vocoder() -> Vocoder | None:
    d = svs_dir() / "nsf_hifigan"
    if d.exists():
        v = Vocoder.load(d)
        if v:
            return v
        sub = next((s for s in d.iterdir() if s.is_dir()), None)
        if sub:
            return Vocoder.load(sub)
    return None


def find_banks() -> list[SvsBank]:
    root = svs_dir()
    if not root.exists() or not available():
        return []
    banks = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name == "nsf_hifigan":
            continue
        bank = SvsBank.load(d)
        if bank is not None:
            if bank.vocoder is None:
                bank.vocoder = shared_vocoder()
            if bank.vocoder is not None:
                banks.append(bank)
            else:
                log.info("SVS bank %s found but no vocoder installed", d.name)
    return banks


def default_bank() -> SvsBank | None:
    banks = find_banks()
    return banks[0] if banks else None


def svs_status() -> dict:
    """For the Voices screen: what's installed, what's missing."""
    root = svs_dir()
    bank_dirs = [d.name for d in root.iterdir()
                 if d.is_dir() and d.name != "nsf_hifigan"] \
        if root.exists() else []
    banks = find_banks()
    return {
        "runtime_available": available(),
        "vocoder_installed": shared_vocoder() is not None
        or any(b.vocoder and b.vocoder.dir != svs_dir() / "nsf_hifigan"
               for b in banks),
        "bank_dirs": bank_dirs,
        "banks": [{"name": b.name, "dir": b.dir.name,
                   "phonemes": len(b.tokens), "words": len(b.dsdict)}
                  for b in banks],
        "svs_dir": str(root),
        "vocoder_url": VOCODER_URL,
    }


def install_vocoder() -> dict:
    """Download the shared NSF-HiFiGAN vocoder (~50 MB, one time)."""
    import io
    import urllib.request
    import zipfile
    dest = svs_dir() / "nsf_hifigan"
    if shared_vocoder() is not None:
        return {"installed": True, "already": True}
    dest.mkdir(parents=True, exist_ok=True)
    log.info("downloading NSF-HiFiGAN vocoder…")
    req = urllib.request.Request(VOCODER_URL,
                                 headers={"User-Agent": "mITyStudio"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)
    # oudep zips may nest a folder — flatten one level if needed
    if not any(dest.glob("*.onnx")):
        sub = next((s for s in dest.iterdir() if s.is_dir()), None)
        if sub:
            for f in sub.iterdir():
                f.rename(dest / f.name)
    ok = shared_vocoder() is not None
    return {"installed": ok}


# ---------------------------------------------------------------------------
# phonemization: lyric line + per-note syllables -> phonemes per note
# ---------------------------------------------------------------------------

def _word_phonemes(bank: SvsBank, word: str) -> list[str] | None:
    w = word.lower().strip("'")
    return bank.dsdict.get(w) or bank.dsdict.get(word.lower())


def _split_by_vowels(bank: SvsBank, phs: list[str],
                     n_parts: int) -> list[list[str]]:
    """Split a word's phonemes into n syllable groups, one vowel each;
    consonants attach forward (onset-preferred, like singers phrase)."""
    v_idx = [i for i, p in enumerate(phs) if p in bank.vowels]
    if len(v_idx) == 0:
        return [phs] + [[] for _ in range(n_parts - 1)]
    # merge/pad vowel groups to exactly n_parts
    while len(v_idx) > n_parts:
        v_idx.pop()           # extra vowels sing within the earlier notes
    groups: list[list[str]] = []
    start = 0
    for k, vi in enumerate(v_idx):
        end = len(phs) if k == len(v_idx) - 1 else v_idx[k + 1]
        groups.append(phs[start:end])
        start = end
    while len(groups) < n_parts:
        groups.append([])     # melisma: extra notes re-sing the last vowel
    return groups


def line_note_phonemes(bank: SvsBank, text: str,
                       note_syls: list[str]) -> list[list[str]] | None:
    """Phonemes for each of the line's notes (1 note per syllable). None if
    a word is missing from the bank's dictionary (caller falls back)."""
    from .lyric_text import word_syllables
    words = _WORD_RE.findall(text)
    per_word: list[tuple[int, list[str]]] = []   # (syllable count, phonemes)
    for w in words:
        phs = _word_phonemes(bank, w)
        if phs is None:
            return None
        per_word.append((max(len(word_syllables(w)), 1), phs))
    if sum(n for n, _ in per_word) != len(note_syls):
        # melody split differs (edited lyrics) — distribute by totals
        total = sum(n for n, _ in per_word)
        if total == 0:
            return None
        # simple proportional re-split: give each word its share of notes
        result: list[list[str]] = []
        remaining = len(note_syls)
        for k, (n, phs) in enumerate(per_word):
            take = remaining if k == len(per_word) - 1 else \
                max(round(n / total * len(note_syls)), 1)
            take = min(take, remaining)
            result.extend(_split_by_vowels(bank, phs, max(take, 1)))
            remaining -= take
        return result[:len(note_syls)] if len(result) >= len(note_syls) \
            else None
    out: list[list[str]] = []
    for n, phs in per_word:
        out.extend(_split_by_vowels(bank, phs, n))
    return out


# ---------------------------------------------------------------------------
# the singing engine
# ---------------------------------------------------------------------------

_HEAD_SEC = 0.10   # SP padding around each line (OpenUtau does the same)
_TAIL_SEC = 0.15
_CONS_SEC = 0.055  # onset consonant length (lead the beat)


class SvsUnsupportedError(RuntimeError):
    """The bank couldn't sing this material (e.g. wrong-language lyrics) —
    the caller should fall back to the clone engine."""


class SvsSingingEngine(SingingVoiceEngine):
    """DiffSinger voicebank sings the melody; the user's trained RVC model
    supplies the timbre. profile may be None → the bank's own voice."""

    def __init__(self, bank: SvsBank, profile=None) -> None:
        self.bank = bank
        self.profile = profile

    # -- one line ----------------------------------------------------------
    def _sing_line(self, text: str, line_notes: list[dict],
                   style: dict) -> tuple[np.ndarray, float] | None:
        bank = self.bank
        voc = bank.vocoder
        frame = voc.frame_sec
        sp = bank.tokens.get("SP")
        if sp is None:
            return None
        note_phs = line_note_phonemes(
            bank, text, [nd.get("syl") or "la" for nd in line_notes])
        if note_phs is None:
            return None

        line_start = line_notes[0]["start"]
        # phoneme sequence with frame durations + per-note vowel frame spans
        tokens: list[int] = [sp]
        durs: list[int] = [max(int(_HEAD_SEC / frame), 1)]
        note_spans: list[tuple[int, int, float]] = []  # frame span + freq
        cursor = durs[0]
        for i, nd in enumerate(line_notes):
            phs = [p for p in note_phs[i] if p in bank.tokens]
            # legato: a note holds until the next one starts (micro-gaps are
            # sung through); real rests (>250 ms) become explicit SP silence
            if i + 1 < len(line_notes):
                gap = line_notes[i + 1]["start"] - nd["end"]
                note_len = (line_notes[i + 1]["start"] - nd["start"]
                            if 0 < gap < 0.25 else nd["end"] - nd["start"])
                rest_len = gap if gap >= 0.25 else 0.0
            else:
                note_len = nd["end"] - nd["start"]
                rest_len = 0.0
            note_len = max(note_len, 0.08)
            vowel_pos = next((k for k, p in enumerate(phs)
                              if p in bank.vowels), len(phs))
            onset, rest = phs[:vowel_pos], phs[vowel_pos:]
            onset_frames = [max(int(_CONS_SEC / frame), 1) for _ in onset]
            body = max(int(note_len / frame), 2)
            if rest:
                # vowel takes the note; trailing consonants borrow its end
                coda = rest[1:]
                coda_frames = [max(int(_CONS_SEC / frame), 1) for _ in coda]
                vowel_frames = max(body - sum(coda_frames), 2)
                seq: list[str] = onset + rest
                fr = onset_frames + [vowel_frames] + coda_frames
            else:   # no vowel matched: hold whatever there is
                seq = onset or ["SP"]
                fr = onset_frames if onset else [body]
                fr[-1] = max(body, fr[-1])
            for p, f in zip(seq, fr):
                tokens.append(bank.tokens.get(p, sp))
                durs.append(f)
            note_spans.append((cursor + sum(onset_frames),
                               cursor + sum(fr), float(nd["freq"])))
            cursor += sum(fr)
            if rest_len > 0:   # explicit breath-length silence inside a line
                rf = max(int(rest_len / frame), 1)
                tokens.append(sp)
                durs.append(rf)
                cursor += rf
        tokens.append(sp)
        durs.append(max(int(_TAIL_SEC / frame), 1))

        total = sum(durs)
        # expressive f0 curve: continuous, portamento + delayed vibrato
        f0 = np.full(total, note_spans[0][2], dtype=np.float32)
        prev = None
        for (a, b, freq) in note_spans:
            t = (np.arange(total) - a) * frame
            seg = slice(max(a - int(0.05 / frame), 0), b)
            if prev is not None:
                gl = np.exp(-np.maximum(t[seg], 0) / 0.05)
                f0[seg] = freq + (prev - freq) * gl
            else:
                f0[seg] = freq
            dur_s = (b - a) * frame
            if dur_s > 0.35:
                tt = np.maximum(t[a:b], 0)
                on = np.clip((tt - 0.35 * dur_s) / (0.3 * dur_s), 0, 1)
                f0[a:b] *= 1 + style.get("vib", 0.018) * on * np.sin(
                    2 * np.pi * style.get("vib_rate", 5.3) * tt)
            f0[b:] = freq
            prev = freq
        rng = np.random.default_rng(total)
        f0 *= 1 + np.cumsum(rng.standard_normal(total)) * 0.0006

        # acoustic → mel → vocoder, probing what the model actually accepts
        import onnxruntime  # noqa: F401
        sess = self.bank.session()
        names = {i.name for i in sess.get_inputs()}
        feeds: dict = {
            "tokens": np.asarray([tokens], dtype=np.int64),
            "durations": np.asarray([durs], dtype=np.int64),
            "f0": f0[None, :].astype(np.float32),
        }
        if "languages" in names:
            feeds["languages"] = np.zeros((1, len(tokens)), dtype=np.int64)
        if "depth" in names:
            feeds["depth"] = np.asarray([1.0], dtype=np.float32)
        if "steps" in names:
            feeds["steps"] = np.asarray([20], dtype=np.int64)
        if "speedup" in names:
            feeds["speedup"] = np.asarray([50], dtype=np.int64)
        for curve, dflt in (("gender", 0.0), ("velocity", 1.0)):
            if curve in names:
                feeds[curve] = np.full((1, total), dflt, dtype=np.float32)
        feeds = {k: v for k, v in feeds.items() if k in names}
        missing = names - set(feeds)
        if missing:
            log.warning("SVS bank %s needs unsupported inputs %s",
                        self.bank.name, missing)
            return None
        mel = sess.run(None, feeds)[0]

        vsess = voc.session()
        vnames = {i.name for i in vsess.get_inputs()}
        vfeeds = {"mel": mel.astype(np.float32),
                  "f0": f0[None, :].astype(np.float32)}
        vfeeds = {k: v for k, v in vfeeds.items() if k in vnames}
        wav = vsess.run(None, vfeeds)[0].astype(np.float32).squeeze()

        if voc.sample_rate != SAMPLE_RATE:
            wav = resample_linear(wav[:, None], voc.sample_rate,
                                  SAMPLE_RATE)[:, 0]
        # trim the head SP so the first VOWEL lands on the beat — its onset
        # consonants (sung inside the head pad) lead the beat like a singer
        head = int(_HEAD_SEC / frame) * int(round(frame * SAMPLE_RATE))
        onset0 = 0
        for p in note_phs[0]:
            if p in self.bank.vowels:
                break
            if p in self.bank.tokens:
                onset0 += 1
        lead = int(onset0 * _CONS_SEC * SAMPLE_RATE)
        start = max(head - lead, 0)
        return wav[start:], max(line_start - lead / SAMPLE_RATE, 0.0)

    # -- whole track ---------------------------------------------------------
    def render(self, project: SongProject, track: Track,
               out_path) -> VocalRenderResult:
        from .vocal_clone import (_STYLES, _breath, _lines_with_notes,
                                  resolve_delivery, rvc_convert_segments)
        result = VocalRenderResult(stem_path=None)
        pairs = _lines_with_notes(project, track)
        total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
        style_name = resolve_delivery(
            getattr(track, "vocal_style", "sing") or "sing", project.style)
        style = _STYLES.get(style_name, _STYLES["sing"])

        segments: list[tuple[int, np.ndarray]] = []
        sung = 0
        fell_back = 0
        prev_end = -10.0
        for text, line_notes in pairs:
            try:
                r = self._sing_line(text, line_notes, style)
            except Exception as e:  # noqa: BLE001
                log.warning("SVS line failed (%s) — %r", e, text[:40])
                r = None
            if r is None:
                fell_back += 1
                continue
            wav, start_s = r
            i0 = int(start_s * SAMPLE_RATE)
            n = min(len(wav), total - i0)
            if n <= 0:
                continue
            sl = wav[:n] * style.get("gain", 1.0)
            edge = min(int(0.02 * SAMPLE_RATE), n)
            sl[:edge] *= np.linspace(0, 1, edge)
            sl[n - edge:n] *= np.linspace(1, 0, edge)
            segments.append((i0, sl.astype(np.float32)))
            if start_s - prev_end > 0.45:
                b = _breath(SAMPLE_RATE, i0)
                bp = i0 - int(0.24 * SAMPLE_RATE)
                if bp >= 0:
                    segments.append((bp, b))
            prev_end = line_notes[-1]["end"]
            sung += 1

        if sung == 0:
            raise SvsUnsupportedError(
                f"bank {self.bank.name!r} couldn't sing any of the "
                f"{len(pairs)} lines (dictionary/language mismatch)")

        from .rvc_convert import rvc_model_ready
        placed = segments
        if sung and self.profile is not None \
                and rvc_model_ready(self.profile):
            converted = rvc_convert_segments(segments, self.profile, result)
            if converted is not None:
                placed = converted
                result.render_log.append(
                    f"RVC conversion applied (trained "
                    f"{self.profile.name!r} model)")

        out = np.zeros(total, dtype=np.float32)
        for i0, sl in placed:
            n = min(len(sl), total - i0)
            if n > 0:
                out[i0:i0 + n] += sl[:n]
        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 0.005:
            out *= 0.85 / peak
        write_wav(out_path, np.repeat(out[:, None], 2, axis=1), SAMPLE_RATE)
        result.stem_path = out_path
        result.render_log.append(
            f"SVS engine (DiffSinger bank {self.bank.name!r}) sang "
            f"{sung}/{len(pairs)} lines")
        if fell_back:
            result.warnings.append(
                f"{fell_back} line(s) missing from the bank's dictionary — "
                "they stay silent on this track (use a bank for the lyrics' "
                "language, or the clone engine)")
        result.alignment = build_lyrics_alignment(project, track)
        return result
