"""True singing-voice synthesis (SVS): DiffSinger voicebanks as the vocal
source — the quality rung above speech-to-singing.

The XTTS chain reshapes SPOKEN audio onto notes; a DiffSinger voicebank was
TRAINED to sing, so sustained vowels, transitions and phrasing come out
naturally. The studio drives any voicebank in the OpenUtau DiffSinger format
dropped into voices/svs/ (the same drop-a-file philosophy as soundfonts —
the user obtains banks from their creators under the creators' licenses;
nothing is redistributed). Banks are discovered recursively, so the
character folder inside an unzipped release works as-is.

We already know exactly WHAT to sing (1 note per syllable + phoneme dicts),
so only the acoustic model + vocoder are needed: tokens/durations/f0 and the
variance-curve inputs are built here — no OpenUtau process. English lyrics
are phonemized with CMUdict (ARPAbet), mapped through the bank's
dictionary-en.txt and language-prefixed for multilingual banks. The sung
lines then go through the SAME dense RVC stage as the clone engine, so the
result sings in the USER'S trained voice.

Everything degrades gracefully: no bank / no vocoder / no onnxruntime →
engine unavailable and the clone chain takes over; per-bank load problems
are reported to the Voices screen instead of failing silently.
"""
from __future__ import annotations

import json
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
_STRESS_RE = re.compile(r"\d")

# breath/silence symbols must never count as vowels for onset detection
_NON_VOWEL_SYMBOLS = {"AP", "SP", "exh", "axh", "cl", "vf", "gs", "pau"}


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
# English G2P: CMUdict → ARPAbet (the lingua franca of EN voicebanks)
# ---------------------------------------------------------------------------

_cmu: dict | None = None


def _g2p_en(word: str) -> list[str] | None:
    global _cmu
    if _cmu is None:
        try:
            import cmudict
            _cmu = cmudict.dict()
        except Exception:  # noqa: BLE001
            _cmu = {}
    prons = _cmu.get(word.lower())
    if not prons:
        return None
    return [_STRESS_RE.sub("", p).lower() for p in prons[0]]


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
        if name and (d / str(name)).exists():
            model = d / str(name)
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
    languages: dict[str, int]              # 'en' -> language id (may be {})
    dsdict: dict[str, list[str]]           # word/grapheme -> phonemes
    phdict: dict[str, dict[str, str]]      # lang -> arpabet -> bank phoneme
    vowels: set[str]
    acoustic_path: Path
    spk_embed: np.ndarray | None           # (D,) speaker embedding
    vocoder: Vocoder | None
    _session: object = field(default=None, repr=False)

    @property
    def lang_prefixed(self) -> bool:
        return any("/" in t for t in self.tokens)

    def session(self):
        if self._session is None:
            import onnxruntime as ort
            self._session = ort.InferenceSession(
                str(self.acoustic_path), providers=["CPUExecutionProvider"])
        return self._session


def _load_bank(d: Path) -> tuple[SvsBank | None, str]:
    """(bank, "") on success, (None, reason) on failure."""
    cfgf = d / "dsconfig.yaml"
    cfg = _read_yaml(cfgf)
    if "acoustic" not in cfg:
        return None, "dsconfig.yaml has no 'acoustic' model entry"
    ac = d / str(cfg["acoustic"])
    if not ac.exists():
        return None, f"acoustic model missing: {cfg['acoustic']}"

    # phoneme token map: .json dict or .txt list
    tokens: dict[str, int] = {}
    ph = d / str(cfg.get("phonemes", "phonemes.txt"))
    if ph.exists():
        if ph.suffix == ".json":
            data = json.loads(ph.read_text(encoding="utf-8"))
            tokens = {str(k): int(v) for k, v in data.items()}
        else:
            for i, line in enumerate(
                    ph.read_text(encoding="utf-8").splitlines()):
                if line.strip():
                    tokens[line.strip()] = i
    if not tokens:
        return None, f"phoneme list missing/empty: {cfg.get('phonemes')}"
    if "SP" not in tokens:
        return None, "phoneme list has no SP (pause) symbol"

    languages: dict[str, int] = {}
    if cfg.get("use_lang_id"):
        lf = d / str(cfg.get("languages", "languages.json"))
        if lf.exists():
            languages = {str(k): int(v) for k, v in json.loads(
                lf.read_text(encoding="utf-8")).items()}

    # dsdict(s): word entries + symbol types (vowels); search near the
    # acoustic model too (multilingual banks keep them in dsmain/)
    dsdict: dict[str, list[str]] = {}
    vowels: set[str] = set()
    for df in {*d.glob("dsdict*.yaml"), *ac.parent.glob("dsdict*.yaml")}:
        data = _read_yaml(df)
        for e in data.get("entries") or []:
            g = str(e.get("grapheme", "")).lower().strip()
            phs = [str(p) for p in (e.get("phonemes") or [])]
            if g and phs and g not in dsdict:
                dsdict[g] = phs
        for sym in data.get("symbols") or []:
            if str(sym.get("type", "")) == "vowel":
                s = str(sym.get("symbol"))
                if s not in _NON_VOWEL_SYMBOLS:
                    vowels.add(s)
    if not vowels:   # fallback: ARPAbet-ish vowel names among the tokens
        vowels = {t for t in tokens
                  if t.split("/")[-1][:2] in ("aa", "ae", "ah", "ao", "aw",
                                              "ax", "ay", "eh", "er", "ey",
                                              "ih", "iy", "ow", "oy", "uh",
                                              "uw")}

    # per-language phoneme mapping files (dictionary-en.txt: arpabet → bank)
    phdict: dict[str, dict[str, str]] = {}
    for f in {*d.glob("dictionary-*.txt"), *ac.parent.glob("dictionary-*.txt")}:
        lang = f.stem.split("-", 1)[1]
        mapping = {}
        for line in f.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t") if "\t" in line else line.split()
            if len(parts) >= 2:
                mapping[parts[0].strip().lower()] = parts[1].strip()
        if mapping:
            phdict[lang] = mapping

    # speaker embedding (multi-speaker banks REQUIRE spk_embed)
    spk = None
    embs = sorted(ac.parent.glob("*.emb")) + sorted(d.glob("*.emb"))
    preferred = next((e for e in embs if "standard" in e.stem.lower()), None)
    if preferred or embs:
        spk = np.fromfile(preferred or embs[0], dtype=np.float32)

    # vocoder: named in dsconfig → find its folder inside the bank
    vocoder = None
    want = str(cfg.get("vocoder", ""))
    for vy in sorted(d.rglob("vocoder.yaml")):
        v = Vocoder.load(vy.parent)
        if v is None or v.model_path == ac:
            continue
        vcfg = _read_yaml(vy)
        if not want or str(vcfg.get("name", "")) == want \
                or want in v.model_path.name:
            vocoder = v
            break
        vocoder = vocoder or v
    name = str(cfg.get("name") or d.name)
    return SvsBank(dir=d, name=name, cfg=cfg, tokens=tokens,
                   languages=languages, dsdict=dsdict, phdict=phdict,
                   vowels=vowels, acoustic_path=ac, spk_embed=spk,
                   vocoder=vocoder), ""


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


def _bank_config_dirs() -> list[Path]:
    """Directories under voices/svs/ holding an ACOUSTIC dsconfig.yaml —
    searched recursively so unzipped release folders work as dropped."""
    root = svs_dir()
    if not root.exists():
        return []
    out = []
    for cfgf in sorted(root.rglob("dsconfig.yaml")):
        if len(cfgf.relative_to(root).parts) > 4:
            continue
        if "acoustic" in _read_yaml(cfgf):
            out.append(cfgf.parent)
    return out


def find_banks(problems: dict[str, str] | None = None) -> list[SvsBank]:
    if not available():
        return []
    banks = []
    for d in _bank_config_dirs():
        bank, reason = _load_bank(d)
        if bank is None:
            if problems is not None:
                problems[d.name] = reason
            log.info("SVS bank %s not loadable: %s", d.name, reason)
            continue
        if bank.vocoder is None:
            bank.vocoder = shared_vocoder()
        if bank.vocoder is None:
            if problems is not None:
                problems[d.name] = "no vocoder (bank has none embedded and " \
                                   "the shared one is not installed)"
            continue
        banks.append(bank)
    return banks


def default_bank() -> SvsBank | None:
    banks = find_banks()
    return banks[0] if banks else None


def svs_status() -> dict:
    """For the Voices screen: what's installed, what's missing, and WHY a
    dropped bank folder didn't load."""
    problems: dict[str, str] = {}
    banks = find_banks(problems)
    return {
        "runtime_available": available(),
        "vocoder_installed": shared_vocoder() is not None,
        "bank_dirs": [d.name for d in _bank_config_dirs()],
        "banks": [{"name": b.name, "dir": b.dir.name,
                   "phonemes": len(b.tokens),
                   "languages": sorted(b.languages) or
                   (["en"] if "en" in b.phdict else []),
                   "words": len(b.dsdict)}
                  for b in banks],
        "problems": problems,
        "svs_dir": str(svs_dir()),
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
    if not any(dest.glob("*.onnx")):
        sub = next((s for s in dest.iterdir() if s.is_dir()), None)
        if sub:
            for f in sub.iterdir():
                f.rename(dest / f.name)
    return {"installed": shared_vocoder() is not None}


# ---------------------------------------------------------------------------
# phonemization: lyric line + per-note syllables -> phonemes per note
# ---------------------------------------------------------------------------

def _word_phonemes(bank: SvsBank, word: str,
                   lang: str = "en") -> list[str] | None:
    w = word.lower().strip("'")
    direct = bank.dsdict.get(w) or bank.dsdict.get(word.lower())
    if direct:
        return direct
    if lang == "en" or lang not in bank.languages and "en" in (
            bank.phdict or {"en": None}):
        arpa = _g2p_en(w)
        if arpa is None:
            return None
        mapping = bank.phdict.get("en", {})
        phs = [mapping.get(p, p) for p in arpa]
        if bank.lang_prefixed:
            phs = [p if p in bank.tokens else f"en/{p}" for p in phs]
        return phs if all(p in bank.tokens for p in phs) else None
    return None


def _split_by_vowels(bank: SvsBank, phs: list[str],
                     n_parts: int) -> list[list[str]]:
    """Split a word's phonemes into n syllable groups, one vowel each;
    consonants attach forward (onset-preferred, like singers phrase)."""
    v_idx = [i for i, p in enumerate(phs) if p in bank.vowels]
    if len(v_idx) == 0:
        return [phs] + [[] for _ in range(n_parts - 1)]
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


def line_note_phonemes(bank: SvsBank, text: str, note_syls: list[str],
                       lang: str = "en") -> list[list[str]] | None:
    """Phonemes for each of the line's notes (1 note per syllable). None if
    a word can't be phonemized (caller falls back)."""
    from .lyric_text import word_syllables
    words = _WORD_RE.findall(text)
    per_word: list[tuple[int, list[str]]] = []   # (syllable count, phonemes)
    for w in words:
        phs = _word_phonemes(bank, w, lang)
        if phs is None:
            return None
        per_word.append((max(len(word_syllables(w)), 1), phs))
    if sum(n for n, _ in per_word) != len(note_syls):
        total = sum(n for n, _ in per_word)
        if total == 0:
            return None
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


def _token_language(bank: SvsBank, phoneme: str) -> int:
    if "/" in phoneme:
        return bank.languages.get(phoneme.split("/", 1)[0], 0)
    return 0


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
    def _sing_line(self, text: str, line_notes: list[dict], style: dict,
                   lang: str = "en") -> tuple[np.ndarray, float] | None:
        bank = self.bank
        voc = bank.vocoder
        frame = voc.frame_sec
        sp = bank.tokens["SP"]
        note_phs = line_note_phonemes(
            bank, text, [nd.get("syl") or "la" for nd in line_notes], lang)
        if note_phs is None:
            return None

        line_start = line_notes[0]["start"]
        tokens: list[int] = [sp]
        tok_names: list[str] = ["SP"]
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
                coda = rest[1:]
                coda_frames = [max(int(_CONS_SEC / frame), 1) for _ in coda]
                vowel_frames = max(body - sum(coda_frames), 2)
                seq: list[str] = onset + rest
                fr = onset_frames + [vowel_frames] + coda_frames
            else:
                seq = onset or ["SP"]
                fr = onset_frames if onset else [body]
                fr[-1] = max(body, fr[-1])
            for p, f in zip(seq, fr):
                tokens.append(bank.tokens.get(p, sp))
                tok_names.append(p)
                durs.append(f)
            note_spans.append((cursor + sum(onset_frames),
                               cursor + sum(fr), float(nd["freq"])))
            cursor += sum(fr)
            if rest_len > 0:
                rf = max(int(rest_len / frame), 1)
                tokens.append(sp)
                tok_names.append("SP")
                durs.append(rf)
                cursor += rf
        tokens.append(sp)
        tok_names.append("SP")
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

        # acoustic → mel → vocoder, feeding exactly what the model declares
        sess = self.bank.session()
        inputs = {i.name: i for i in sess.get_inputs()}
        feeds: dict = {
            "tokens": np.asarray([tokens], dtype=np.int64),
            "durations": np.asarray([durs], dtype=np.int64),
            "f0": f0[None, :].astype(np.float32),
        }
        if "languages" in inputs:
            feeds["languages"] = np.asarray(
                [[_token_language(bank, p) for p in tok_names]],
                dtype=np.int64)
        if "spk_embed" in inputs:
            if bank.spk_embed is None:
                log.warning("bank %s wants spk_embed but no .emb found",
                            bank.name)
                return None
            feeds["spk_embed"] = np.tile(
                bank.spk_embed[None, None, :], (1, total, 1)).astype(
                np.float32)
        # neutral variance curves (0 = expression default in OpenUtau;
        # velocity is log2-scaled, so 0 means 1×)
        for curve in ("gender", "velocity", "energy", "breathiness",
                      "voicing", "tension"):
            if curve in inputs:
                feeds[curve] = np.zeros((1, total), dtype=np.float32)

        def scalar(name: str, value, dtype):
            rank = len(inputs[name].shape)
            arr = np.asarray(value, dtype=dtype)
            return arr.reshape([1] * rank) if rank else arr

        if "depth" in inputs:
            feeds["depth"] = scalar("depth", float(
                self.bank.cfg.get("max_depth", 1.0)), np.float32)
        if "steps" in inputs:
            feeds["steps"] = scalar("steps", 32, np.int64)
        if "speedup" in inputs:
            feeds["speedup"] = scalar("speedup", 50, np.int64)
        feeds = {k: v for k, v in feeds.items() if k in inputs}
        missing = set(inputs) - set(feeds)
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
        lang = (project.lyrics.language or "en").lower()

        segments: list[tuple[int, np.ndarray]] = []
        sung = 0
        fell_back = 0
        prev_end = -10.0
        for text, line_notes in pairs:
            try:
                r = self._sing_line(text, line_notes, style, lang)
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
