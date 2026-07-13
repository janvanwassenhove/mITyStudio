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
    acoustic_path: Path
    search_dirs: tuple                     # dirs to find dicts/embeddings in
    vocoder: Vocoder | None
    _session: object = field(default=None, repr=False)
    _dsdict: dict | None = field(default=None, repr=False)
    _phdict: dict | None = field(default=None, repr=False)
    _vowels: set | None = field(default=None, repr=False)
    _spk: object = field(default=0, repr=False)   # 0 = not loaded
    _auxes: dict | None = field(default=None, repr=False)

    @property
    def lang_prefixed(self) -> bool:
        return any("/" in t for t in self.tokens)

    # heavy fields are parsed lazily — 40-bank packs scatter big multilingual
    # dictionaries that would make discovery crawl if read up front
    def _ensure_dicts(self) -> None:
        if self._dsdict is not None:
            return
        dsdict: dict[str, list[str]] = {}
        vowels: set[str] = set()
        for sd in self.search_dirs:
            for df in Path(sd).glob("dsdict*.yaml"):
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
        if not vowels:
            vowels = {t for t in self.tokens
                      if t.split("/")[-1][:2] in (
                          "aa", "ae", "ah", "ao", "aw", "ax", "ay", "eh",
                          "er", "ey", "ih", "iy", "ow", "oy", "uh", "uw")}
        self._dsdict, self._vowels = dsdict, vowels

    @property
    def dsdict(self) -> dict:
        self._ensure_dicts()
        return self._dsdict

    @property
    def vowels(self) -> set:
        self._ensure_dicts()
        return self._vowels

    @property
    def phdict(self) -> dict:
        if self._phdict is None:
            phdict: dict[str, dict[str, str]] = {}
            for sd in self.search_dirs:
                for f in Path(sd).glob("dictionary-*.txt"):
                    lang = f.stem.split("-", 1)[1]
                    mapping = {}
                    for line in f.read_text(encoding="utf-8").splitlines():
                        parts = line.split("\t") if "\t" in line \
                            else line.split()
                        if len(parts) >= 2:
                            mapping[parts[0].strip().lower()] = parts[1].strip()
                    if mapping:
                        phdict[lang] = mapping
            self._phdict = phdict
        return self._phdict

    @property
    def spk_embed(self):
        if self._spk is 0:  # noqa: F632 — sentinel identity check is intended
            cand: list[Path] = [self.dir / f"{sp}.emb"
                                for sp in (self.cfg.get("speakers") or [])]
            embs = [e for sd in self.search_dirs for e in Path(sd).glob("*.emb")]
            cand += [e for e in embs if "standard" in e.stem.lower()] + embs
            self._spk = next((np.fromfile(p, dtype=np.float32)
                              for p in cand if p.exists()), None)
        return self._spk

    def session(self):
        if self._session is None:
            import onnxruntime as ort
            self._session = ort.InferenceSession(
                str(self.acoustic_path), providers=["CPUExecutionProvider"])
        return self._session

    def aux(self, kind: str) -> "AuxModel | None":
        """The bank's own duration/pitch/variance predictor (lazy; None when
        the bank doesn't ship it — heuristics take over per stage)."""
        if self._auxes is None:
            self._auxes = {}
        if kind not in self._auxes:
            self._auxes[kind] = _load_aux(self.dir, f"ds{kind}", kind)
        return self._auxes[kind]


@dataclass
class AuxModel:
    """One of the bank's auxiliary predictors (dsdur / dspitch /
    dsvariance): a linguistic encoder + a predictor, in openvpi's two-stage
    ONNX layout. These are the models that make DiffSinger sound HUMAN —
    trained phoneme durations, expressive pitch and voice-quality curves.
    Skipping them (early driver versions fed zeros) produces garbled,
    non-human output on banks whose acoustic model expects them."""
    dir: Path
    cfg: dict
    linguistic_path: Path
    predictor_path: Path
    spk_path: Path | None
    _ling: object = field(default=None, repr=False)
    _pred: object = field(default=None, repr=False)
    _spk: object = field(default=0, repr=False)

    def ling(self):
        if self._ling is None:
            import onnxruntime as ort
            self._ling = ort.InferenceSession(
                str(self.linguistic_path), providers=["CPUExecutionProvider"])
        return self._ling

    def pred(self):
        if self._pred is None:
            import onnxruntime as ort
            self._pred = ort.InferenceSession(
                str(self.predictor_path), providers=["CPUExecutionProvider"])
        return self._pred

    @property
    def spk(self):
        if self._spk is 0:  # noqa: F632 — sentinel identity check intended
            self._spk = (np.fromfile(self.spk_path, dtype=np.float32)
                         if self.spk_path and self.spk_path.exists() else None)
        return self._spk


def _load_aux(bank_dir: Path, sub: str, predictor_key: str) -> AuxModel | None:
    """Load <bank>/<sub>/dsconfig.yaml (dsdur/dspitch/dsvariance). Model
    paths are relative to that yaml (shared-model packs point at ../../)."""
    d = bank_dir / sub
    cfg = _read_yaml(d / "dsconfig.yaml") if (d / "dsconfig.yaml").exists() \
        else {}
    if not cfg:
        return None
    ling = d / str(cfg.get("linguistic", "linguistic.onnx"))
    pred = d / str(cfg.get(predictor_key, f"{predictor_key}.onnx"))
    if not ling.exists() or not pred.exists():
        return None
    spk = None
    for sp in (cfg.get("speakers") or []):
        cand = d / f"{sp}.emb"
        if cand.exists():
            spk = cand
            break
    if spk is None:
        embs = sorted(d.glob("*.emb"))
        pref = next((e for e in embs if "standard" in e.stem.lower()), None)
        spk = pref or (embs[0] if embs else None)
    return AuxModel(dir=d, cfg=cfg, linguistic_path=ling,
                    predictor_path=pred, spk_path=spk)


def _load_bank(d: Path) -> tuple[SvsBank | None, str]:
    """(bank, "") on success, (None, reason) on failure. Only cheap metadata
    is read here; dictionaries/embeddings load lazily on first sing."""
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

    search_dirs = tuple(str(sd) for sd in
                        (d, ac.parent, d / "dsmain", d / "dsdur",
                         d / "dspitch", d / "dsacoustic") if sd.exists())

    # vocoder: named in dsconfig → look in the usual folders (glob, not rglob)
    vocoder = None
    want = str(cfg.get("vocoder", ""))
    voc_dirs = [d / want, d / "dsvocoder", d / "vocoder", d,
                ac.parent / "dsvocoder", ac.parent]
    seen_voc: set[Path] = set()
    for vd in voc_dirs:
        if not vd.exists() or vd in seen_voc:
            continue
        seen_voc.add(vd)
        v = Vocoder.load(vd)
        if v is None or v.model_path == ac:
            continue
        vcfg = _read_yaml(vd / "vocoder.yaml") if (vd / "vocoder.yaml").exists() else {}
        if not want or str(vcfg.get("name", "")) == want \
                or want in v.model_path.name:
            vocoder = v
            break
        vocoder = vocoder or v
    name = str(cfg.get("name") or d.name)
    return SvsBank(dir=d, name=name, cfg=cfg, tokens=tokens,
                   languages=languages, acoustic_path=ac,
                   search_dirs=search_dirs, vocoder=vocoder), ""


_shared_vocoder_cache: list = []   # [] = not computed, [v|None] = computed


def shared_vocoder() -> Vocoder | None:
    if _shared_vocoder_cache:
        return _shared_vocoder_cache[0]
    d = svs_dir() / "nsf_hifigan"
    v = None
    if d.exists():
        v = Vocoder.load(d)
        if v is None:
            sub = next((s for s in d.iterdir() if s.is_dir()), None)
            if sub:
                v = Vocoder.load(sub)
    _shared_vocoder_cache.append(v)
    return v


# sub-model / asset folders that never hold an ACOUSTIC bank config — don't
# descend into them (image folders especially make a full walk very slow)
_SKIP_DIRS = {"images", "dsdur", "dspitch", "dsvariance", "dsvocoder",
              "dsacoustic", "extras", "0_PHONEMIZERS", "__pycache__"}


def _bank_config_dirs() -> list[Path]:
    """Directories under voices/svs/ holding an ACOUSTIC dsconfig.yaml.
    A bounded, directory-only walk (depth ≤3) — NOT rglob, which stat()s
    every image file in every bank and is pathologically slow at scale."""
    root = svs_dir()
    if not root.exists():
        return []
    out: list[Path] = []

    def walk(d: Path, depth: int):
        cfg = d / "dsconfig.yaml"
        if cfg.exists() and "acoustic" in _read_yaml(cfg):
            out.append(d)
            return                       # a bank dir; don't recurse into it
        if depth <= 0:
            return
        try:
            for child in d.iterdir():
                if child.is_dir() and child.name not in _SKIP_DIRS \
                        and child.name != "nsf_hifigan":
                    walk(child, depth - 1)
        except OSError:
            pass

    walk(root, 3)
    return sorted(out)


_bank_cache: dict | None = None   # {"sig": ..., "banks": [...], "problems": {}}


def _svs_signature() -> tuple:
    """Cheap fingerprint of the voices/svs tree — dir names + mtimes — so the
    (relatively expensive) bank scan only re-runs when files change."""
    root = svs_dir()
    if not root.exists():
        return ()
    try:
        return tuple(sorted((p.name, int(p.stat().st_mtime))
                            for p in root.iterdir()))
    except OSError:
        return ()


def find_banks(problems: dict[str, str] | None = None) -> list[SvsBank]:
    """Loaded voicebanks, cached until the svs/ tree changes. Loading 40+
    banks reads many small files, so re-scanning per request would make the
    Voices screen and every render crawl."""
    global _bank_cache
    if not available():
        return []
    sig = _svs_signature()
    if _bank_cache is None or _bank_cache["sig"] != sig:
        banks, probs = [], {}
        for d in _bank_config_dirs():
            bank, reason = _load_bank(d)
            if bank is None:
                probs[d.name] = reason
                log.info("SVS bank %s not loadable: %s", d.name, reason)
                continue
            if bank.vocoder is None:
                bank.vocoder = shared_vocoder()
            if bank.vocoder is None:
                probs[d.name] = ("no vocoder (bank has none embedded and the "
                                 "shared one is not installed)")
                continue
            banks.append(bank)
        _bank_cache = {"sig": sig, "banks": banks, "problems": probs}
    if problems is not None:
        problems.update(_bank_cache["problems"])
    return _bank_cache["banks"]


def default_bank() -> SvsBank | None:
    banks = find_banks()
    return banks[0] if banks else None


def bank_by_dir(dir_name: str) -> SvsBank | None:
    if not dir_name:
        return None
    return next((b for b in find_banks() if b.dir.name == dir_name), None)


def preview_bank(dir_name: str, text: str = "la la la la",
                 out_path: Path | None = None) -> Path | None:
    """Render a short sung phrase in a voicebank's OWN voice (no RVC) so the
    user can audition it. Returns the WAV path, or None if unavailable."""
    bank = bank_by_dir(dir_name) or default_bank()
    if bank is None:
        return None
    # a simple rising 5-note phrase, ~1.8 s
    words = (text.split() or ["la"])[:5]
    while len(words) < 3:
        words.append(words[-1])
    freqs = [220.0, 246.94, 261.63, 293.66, 329.63]
    notes, t = [], 0.0
    for i, w in enumerate(words):
        dur = 0.4
        notes.append({"syl": w, "start": t, "end": t + dur,
                      "freq": freqs[min(i, len(freqs) - 1)]})
        t += dur
    eng = SvsSingingEngine(bank, profile=None)
    r = eng._sing_line(" ".join(words), notes,
                       {"vib": 0.02, "vib_rate": 5.3}, "en")
    if r is None:
        return None
    wav, _start = r
    out = out_path or (get_config().analysis_cache_dir / "svs"
                       / f"preview_{bank.dir.name[:16]}.wav")
    out.parent.mkdir(parents=True, exist_ok=True)
    peak = float(np.abs(wav).max()) or 1.0
    write_wav(out, (wav * (0.9 / peak))[:, None], SAMPLE_RATE)
    return out


def svs_status() -> dict:
    """For the Voices screen: what's installed, what's missing, and WHY a
    dropped bank folder didn't load."""
    problems: dict[str, str] = {}
    banks = find_banks(problems)
    return {
        "runtime_available": available(),
        "vocoder_installed": shared_vocoder() is not None,
        "bank_dirs": [d.name for d in _bank_config_dirs()],
        # NB: only cheap fields here — b.dsdict/b.phdict are lazy and would
        # parse every bank's dictionaries if touched during a listing
        "banks": [{"name": b.name, "dir": b.dir.name,
                   "phonemes": len(b.tokens),
                   "languages": sorted(b.languages) or ["en"],
                   "words": 0}
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
    _shared_vocoder_cache.clear()   # re-probe after download
    dest.mkdir(parents=True, exist_ok=True)
    log.info("downloading NSF-HiFiGAN vocoder…")
    req = urllib.request.Request(VOCODER_URL,
                                 headers={"User-Agent": "mITyStudio"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)
    _shared_vocoder_cache.clear()
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

# ONNX declared type string -> numpy dtype, so feeds match whatever a bank
# wants (banks vary: some declare steps/speedup as int64, variance as float)
_ONNX_DTYPES = {
    "tensor(int64)": np.int64, "tensor(int32)": np.int32,
    "tensor(float)": np.float32, "tensor(float16)": np.float16,
    "tensor(double)": np.float64, "tensor(bool)": np.bool_,
}


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
    @staticmethod
    def _run(sess, cand: dict) -> dict:
        """Run an ONNX session feeding exactly its declared inputs from the
        candidate dict (rank-aware scalars, dtype-cast). Returns outputs by
        name. Raises if a declared input has no candidate."""
        ins = {i.name: i for i in sess.get_inputs()}
        feeds = {}
        for name, spec in ins.items():
            if cand.get(name) is None:
                raise RuntimeError(f"no candidate for model input {name!r}")
            v = np.asarray(cand[name])
            rank = len(spec.shape)
            if v.ndim == 0 and rank:
                v = v.reshape([1] * rank)
            feeds[name] = v.astype(_ONNX_DTYPES.get(spec.type, v.dtype))
        outs = sess.run(None, feeds)
        return {o.name: outs[k] for k, o in enumerate(sess.get_outputs())}

    def _sing_line(self, text: str, line_notes: list[dict], style: dict,
                   lang: str = "en") -> tuple[np.ndarray, float] | None:
        """The full DiffSinger pipeline, exactly as OpenUtau drives it:
        the bank's OWN models predict phoneme durations (dsdur), expressive
        pitch (dspitch) and voice-quality curves (dsvariance) before the
        acoustic model sings. Each stage falls back to a heuristic when the
        bank doesn't ship that model — but when present they are what makes
        the output sound like a human singer instead of garbled vowels."""
        bank = self.bank
        voc = bank.vocoder
        frame = voc.frame_sec
        sp = bank.tokens["SP"]
        note_phs = line_note_phonemes(
            bank, text, [nd.get("syl") or "la" for nd in line_notes], lang)
        if note_phs is None:
            return None

        line_start = line_notes[0]["start"]
        head_f = max(int(_HEAD_SEC / frame), 1)
        tail_f = max(int(_TAIL_SEC / frame), 1)

        tokens: list[int] = [sp]
        tok_names: list[str] = ["SP"]
        durs: list[int] = [head_f]                     # heuristic ph_dur
        # words: (token count, frames, midi|None) — the dur model needs the
        # word grid; notes: (midi, rest, frames) — the pitch model needs it
        words: list[list] = [[1, head_f, None]]
        notes_arr: list[list] = [[60.0, True, head_f]]
        cursor = head_f
        for i, nd in enumerate(line_notes):
            phs = [p for p in note_phs[i] if p in bank.tokens]
            midi = 69.0 + 12.0 * float(np.log2(nd["freq"] / 440.0))
            # legato: a note holds until the next starts (micro-gaps sung
            # through); real rests (>250 ms) become explicit SP silence
            if i + 1 < len(line_notes):
                gap = line_notes[i + 1]["start"] - nd["end"]
                note_len = (line_notes[i + 1]["start"] - nd["start"]
                            if 0 < gap < 0.25 else nd["end"] - nd["start"])
                rest_len = gap if gap >= 0.25 else 0.0
            else:
                note_len = nd["end"] - nd["start"]
                rest_len = 0.0
            note_len = max(note_len, 0.08)
            body = max(int(note_len / frame), 2)
            notes_arr.append([midi, False, body])
            if not phs:
                # melisma: this note re-sings the previous word's vowel —
                # extend that word (and its last phoneme) instead of a gap
                if len(words) > 1 and words[-1][2] is not None:
                    words[-1][1] += body
                    durs[-1] += body
                    cursor += body
                    continue
                phs = ["SP"]
            vowel_pos = next((k for k, p in enumerate(phs)
                              if p in bank.vowels), len(phs))
            onset, rest = phs[:vowel_pos], phs[vowel_pos:]
            onset_frames = [max(int(_CONS_SEC / frame), 1) for _ in onset]
            if rest:
                coda = rest[1:]
                coda_frames = [max(int(_CONS_SEC / frame), 1) for _ in coda]
                vowel_frames = max(body - sum(onset_frames)
                                   - sum(coda_frames), 2)
                seq: list[str] = onset + rest
                fr = onset_frames + [vowel_frames] + coda_frames
            else:
                seq = onset
                fr = onset_frames
                fr[-1] = max(body - sum(onset_frames[:-1]), fr[-1])
            for p, f in zip(seq, fr):
                tokens.append(bank.tokens.get(p, sp))
                tok_names.append(p)
                durs.append(f)
            words.append([len(seq), sum(fr), midi])
            cursor += sum(fr)
            if rest_len > 0:
                rf = max(int(rest_len / frame), 1)
                tokens.append(sp)
                tok_names.append("SP")
                durs.append(rf)
                words.append([1, rf, None])
                notes_arr.append([midi, True, rf])
                cursor += rf
        tokens.append(sp)
        tok_names.append("SP")
        durs.append(tail_f)
        words.append([1, tail_f, None])
        notes_arr.append([notes_arr[-1][0], True, tail_f])

        n_tok = len(tokens)
        tokens_np = np.asarray([tokens], dtype=np.int64)
        langs_np = np.asarray(
            [[_token_language(bank, p) for p in tok_names]], dtype=np.int64)

        def spk_tile(emb, n):
            return np.tile(emb[None, None, :], (1, n, 1)).astype(np.float32)

        # ---- stage 1: phoneme durations (dsdur) -------------------------
        dur_aux = bank.aux("dur")
        if dur_aux is not None:
            try:
                ling = self._run(dur_aux.ling(), {
                    "tokens": tokens_np, "languages": langs_np,
                    "word_div": np.asarray([[w[0] for w in words]],
                                           dtype=np.int64),
                    "word_dur": np.asarray([[w[1] for w in words]],
                                           dtype=np.int64),
                    "ph_dur": np.asarray([durs], dtype=np.int64),
                })
                # per-token midi: word midi, rests borrow their neighbour
                ph_midi, k = [], 0
                for w in words:
                    ph_midi += [w[2]] * w[0]
                    k += w[0]
                last = next((m for m in ph_midi if m is not None), 60.0)
                ph_midi = [(m if m is not None else last) for m in ph_midi]
                emb = dur_aux.spk if dur_aux.spk is not None \
                    else bank.spk_embed
                pred = self._run(dur_aux.pred(), {
                    "encoder_out": ling["encoder_out"],
                    "x_masks": ling.get("x_masks",
                                        np.zeros((1, n_tok), dtype=bool)),
                    "ph_midi": np.asarray([[int(round(m)) for m in ph_midi]],
                                          dtype=np.int64),
                    "spk_embed": spk_tile(emb, n_tok)
                    if emb is not None else None,
                })
                raw = np.maximum(
                    np.asarray(pred["ph_dur_pred"], dtype=np.float64)
                    .reshape(-1), 1e-3)
                # rescale within each word so word timing stays EXACTLY on
                # the notes; the model decides the consonant/vowel balance
                new_durs: list[int] = []
                pos = 0
                for w in words:
                    seg = raw[pos:pos + w[0]]
                    pos += w[0]
                    scaled = np.maximum(
                        np.round(seg / seg.sum() * w[1]).astype(int), 1)
                    scaled[int(np.argmax(scaled))] += w[1] - int(scaled.sum())
                    new_durs += [int(x) for x in scaled]
                if sum(new_durs) == sum(d for d in durs):
                    durs = new_durs
            except Exception as e:  # noqa: BLE001 — keep heuristic durations
                log.debug("dsdur failed (%s) — heuristic durations", e)

        total = sum(durs)
        durs_np = np.asarray([durs], dtype=np.int64)

        # base pitch grid in semitones (the pitch model refines it; the
        # fallback curve is built from the same grid)
        base_semi = np.zeros(total, dtype=np.float32)
        pos = 0
        last_midi = notes_arr[0][0]
        for midi, rest, frames in notes_arr:
            if not rest:
                last_midi = midi
            base_semi[pos:pos + frames] = last_midi
            pos += frames

        # ---- stage 2: expressive pitch (dspitch) ------------------------
        f0 = None
        pitch_aux = bank.aux("pitch")
        if pitch_aux is not None:
            try:
                ling = self._run(pitch_aux.ling(), {
                    "tokens": tokens_np, "languages": langs_np,
                    "ph_dur": durs_np,
                    "word_div": np.asarray([[w[0] for w in words]],
                                           dtype=np.int64),
                    "word_dur": np.asarray([[w[1] for w in words]],
                                           dtype=np.int64),
                })
                emb = pitch_aux.spk if pitch_aux.spk is not None \
                    else bank.spk_embed
                pred = self._run(pitch_aux.pred(), {
                    "encoder_out": ling["encoder_out"],
                    "x_masks": ling.get("x_masks",
                                        np.zeros((1, n_tok), dtype=bool)),
                    "ph_dur": durs_np,
                    "note_midi": np.asarray([[n[0] for n in notes_arr]],
                                            dtype=np.float32),
                    "note_rest": np.asarray([[n[1] for n in notes_arr]],
                                            dtype=bool),
                    "note_dur": np.asarray([[n[2] for n in notes_arr]],
                                           dtype=np.int64),
                    "pitch": base_semi[None, :],
                    "expr": np.ones((1, total), dtype=np.float32),
                    "retake": np.ones((1, total), dtype=bool),
                    "spk_embed": spk_tile(emb, total)
                    if emb is not None else None,
                    "steps": np.asarray(10, dtype=np.int64),
                })
                semi = np.asarray(pred["pitch_pred"],
                                  dtype=np.float32).reshape(-1)[:total]
                f0 = (440.0 * np.power(2.0, (semi - 69.0) / 12.0)) \
                    .astype(np.float32)
            except Exception as e:  # noqa: BLE001 — fallback curve below
                log.debug("dspitch failed (%s) — heuristic pitch", e)

        if f0 is None:
            # fallback: portamento + delayed vibrato on the note grid
            f0 = 440.0 * np.power(2.0, (base_semi - 69.0) / 12.0)
            pos = 0
            prev = None
            for midi, rest, frames in notes_arr:
                if not rest:
                    freq = 440.0 * 2 ** ((midi - 69.0) / 12.0)
                    tt = np.arange(frames) * frame
                    if prev is not None:
                        f0[pos:pos + frames] = freq + (prev - freq) * np.exp(
                            -tt / 0.05)
                    dur_s = frames * frame
                    if dur_s > 0.35:
                        on = np.clip((tt - 0.35 * dur_s) / (0.3 * dur_s),
                                     0, 1)
                        f0[pos:pos + frames] *= 1 + style.get("vib", 0.018) \
                            * on * np.sin(2 * np.pi
                                          * style.get("vib_rate", 5.3) * tt)
                    prev = freq
                pos += frames
            f0 = f0.astype(np.float32)
        semi_final = (69.0 + 12.0 * np.log2(np.maximum(f0, 1.0) / 440.0)) \
            .astype(np.float32)

        # ---- stage 3: voice-quality curves (dsvariance) -----------------
        sess = self.bank.session()
        inputs = {i.name: i for i in sess.get_inputs()}
        needed = [c for c in ("energy", "breathiness", "voicing", "tension")
                  if c in inputs]
        curves: dict[str, np.ndarray] = {}
        var_aux = bank.aux("variance") if needed else None
        if var_aux is not None:
            try:
                ling = self._run(var_aux.ling(), {
                    "tokens": tokens_np, "languages": langs_np,
                    "ph_dur": durs_np,
                    "word_div": np.asarray([[w[0] for w in words]],
                                           dtype=np.int64),
                    "word_dur": np.asarray([[w[1] for w in words]],
                                           dtype=np.int64),
                })
                emb = var_aux.spk if var_aux.spk is not None \
                    else bank.spk_embed
                vp = var_aux.pred()
                n_var = sum(1 for o in vp.get_outputs()
                            if o.name.endswith("_pred"))
                pred = self._run(vp, {
                    "encoder_out": ling["encoder_out"],
                    "x_masks": ling.get("x_masks",
                                        np.zeros((1, n_tok), dtype=bool)),
                    "ph_dur": durs_np,
                    "pitch": semi_final[None, :],
                    "energy": np.zeros((1, total), dtype=np.float32),
                    "breathiness": np.zeros((1, total), dtype=np.float32),
                    "voicing": np.zeros((1, total), dtype=np.float32),
                    "tension": np.zeros((1, total), dtype=np.float32),
                    "retake": np.ones((1, total, max(n_var, 1)), dtype=bool),
                    "spk_embed": spk_tile(emb, total)
                    if emb is not None else None,
                    "steps": np.asarray(10, dtype=np.int64),
                })
                for name, arr in pred.items():
                    if name.endswith("_pred"):
                        curves[name[:-5]] = np.asarray(
                            arr, dtype=np.float32).reshape(1, -1)[:, :total]
            except Exception as e:  # noqa: BLE001 — zeros below
                log.debug("dsvariance failed (%s) — neutral curves", e)

        # ---- stage 4: acoustic → mel → vocoder --------------------------
        feeds: dict = {
            "tokens": tokens_np,
            "durations": durs_np,
            "f0": f0[None, :],
            "languages": langs_np,
        }
        if "spk_embed" in inputs:
            if bank.spk_embed is None:
                log.warning("bank %s wants spk_embed but no .emb found",
                            bank.name)
                return None
            feeds["spk_embed"] = spk_tile(bank.spk_embed, total)
        for curve in ("gender", "velocity", "energy", "breathiness",
                      "voicing", "tension"):
            if curve in inputs:
                feeds[curve] = curves.get(
                    curve, np.zeros((1, total), dtype=np.float32))
        feeds["depth"] = np.asarray(
            float(self.bank.cfg.get("max_depth", 1.0)), dtype=np.float32)
        feeds["steps"] = np.asarray(32, dtype=np.int64)
        feeds["speedup"] = np.asarray(50, dtype=np.int64)
        try:
            mel = self._run(sess, feeds)["mel"]
        except RuntimeError as e:
            log.warning("SVS bank %s: %s", self.bank.name, e)
            return None

        vsess = voc.session()
        vnames = {i.name for i in vsess.get_inputs()}
        vfeeds = {"mel": mel.astype(np.float32), "f0": f0[None, :]}
        vfeeds = {k: v for k, v in vfeeds.items() if k in vnames}
        wav = vsess.run(None, vfeeds)[0].astype(np.float32).squeeze()

        if voc.sample_rate != SAMPLE_RATE:
            wav = resample_linear(wav[:, None], voc.sample_rate,
                                  SAMPLE_RATE)[:, 0]
        # trim the head SP: the first word starts exactly on the beat
        head = head_f * int(round(frame * SAMPLE_RATE))
        return wav[head:], line_start

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
