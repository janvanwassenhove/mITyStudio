"""Built-in synth engine — pure-numpy tone generation, zero external binaries.

This is the baked-in default instrument set: a full band + drum kit that always
works even with no SoundFont and no FluidSynth installed. SoundFonts remain an
optional upgrade (see soundfont_renderer._select_renderer for the priority).

Patches are declarative (`Patch` dataclass) so the exact same set can be:
  - rendered offline to WAV stems (`render_note`, via SynthRenderer),
  - listed for the chat agent + asset browser (`synth_catalog`),
  - and mirrored by the browser's real-time WebAudio synth (`synth_patch_specs`
    is the single source of truth the frontend reads — no duplicated tables).

Oscillators use PolyBLEP band-limiting on the saw/square edges so rendered
stems stay clean; filtering is FFT-based (no scipy dependency).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

SAMPLE_RATE = 44100
_VIBRATO_HZ = 5.0


# --- primitives ------------------------------------------------------------

def _midi_to_freq(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def _polyblep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    """Band-limited step residual, evaluated near each discontinuity."""
    out = np.zeros_like(t)
    m1 = t < dt
    x = t[m1] / dt[m1]
    out[m1] = x + x - x * x - 1.0
    m2 = t > (1.0 - dt)
    x = (t[m2] - 1.0) / dt[m2]
    out[m2] = x * x + x + x + 1.0
    return out


def _osc(kind: str, freq, n: int, sr: int) -> np.ndarray:
    """One oscillator. `freq` may be a scalar or a per-sample array (vibrato)."""
    if np.isscalar(freq):
        freq = np.full(n, float(freq), dtype=np.float64)
    dt = freq / sr
    phase = np.cumsum(dt) % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * phase)
    if kind == "triangle":
        return 4.0 * np.abs(phase - 0.5) - 1.0
    if kind == "saw":
        return (2.0 * phase - 1.0) - _polyblep(phase, dt)
    if kind == "square":
        v = np.where(phase < 0.5, 1.0, -1.0)
        v = v + _polyblep(phase, dt) - _polyblep((phase + 0.5) % 1.0, dt)
        return v
    raise ValueError(f"unknown oscillator {kind!r}")


def _adsr(gate_n: int, a: float, d: float, s: float, r: float,
          sr: int) -> np.ndarray:
    """Amplitude envelope over `gate_n` held samples plus a release tail."""
    a_n = max(1, int(round(a * sr)))
    d_n = max(1, int(round(d * sr)))
    r_n = max(1, int(round(r * sr)))
    seg = np.zeros(max(gate_n, 1), dtype=np.float32)
    if gate_n <= a_n:
        level = gate_n / a_n
        seg[:] = np.linspace(0.0, level, gate_n, endpoint=False)
    else:
        seg[:a_n] = np.linspace(0.0, 1.0, a_n, endpoint=False)
        rem = gate_n - a_n
        if rem <= d_n:
            level = 1.0 - (rem / d_n) * (1.0 - s)
            seg[a_n:] = np.linspace(1.0, level, rem, endpoint=False)
        else:
            seg[a_n:a_n + d_n] = np.linspace(1.0, s, d_n, endpoint=False)
            seg[a_n + d_n:] = s
            level = s
    rel = np.linspace(level, 0.0, r_n, endpoint=True).astype(np.float32)
    return np.concatenate([seg, rel])


def _lowpass(x: np.ndarray, cutoff: float, sr: int, order: int = 2) -> np.ndarray:
    """FFT-domain lowpass (Butterworth-ish magnitude), vectorized, no scipy."""
    if cutoff <= 0 or cutoff >= sr / 2 or len(x) < 4:
        return x
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    h = 1.0 / np.sqrt(1.0 + (f / cutoff) ** (2 * order))
    return np.fft.irfft(spec * h, len(x)).astype(np.float32)


def _highpass(x: np.ndarray, cutoff: float, sr: int) -> np.ndarray:
    return (x - _lowpass(x, cutoff, sr, order=1)).astype(np.float32)


def _karplus(freq: float, n: int, sr: int, decay: float = 0.996) -> np.ndarray:
    """Plucked-string tone (Karplus-Strong), vectorized one period at a time."""
    length = max(2, int(round(sr / max(freq, 1.0))))
    buf = np.random.uniform(-1.0, 1.0, length).astype(np.float32)
    periods = int(np.ceil(n / length)) + 1
    chunks = []
    for _ in range(periods):
        chunks.append(buf.copy())
        buf = decay * 0.5 * (buf + np.roll(buf, -1))
    return np.concatenate(chunks)[:n]


def _fm(freq: float, n: int, sr: int, ratio: float, index: float) -> np.ndarray:
    """2-operator FM with a decaying modulation index (bell/e-piano attack)."""
    t = np.arange(n) / sr
    idx = index * np.exp(-t * 6.0)
    mod = np.sin(2 * np.pi * freq * ratio * t)
    return np.sin(2 * np.pi * freq * t + idx * mod)


def _freq_curve(freq: float, n: int, sr: int, vibrato: float) -> np.ndarray:
    """Per-sample frequency with optional vibrato (cents depth)."""
    if vibrato <= 0:
        return np.full(n, freq, dtype=np.float64)
    t = np.arange(n) / sr
    ratio = 2.0 ** ((vibrato / 1200.0) * np.sin(2 * np.pi * _VIBRATO_HZ * t))
    return freq * ratio


# --- patches ---------------------------------------------------------------

@dataclass
class Patch:
    id: str
    label: str
    category: str
    track_types: tuple[str, ...]
    kind: str = "osc"                       # osc | fm | pluck | drums
    osc: str = "saw"
    voices: int = 1
    detune: float = 0.0                     # unison spread, cents
    sub: float = 0.0                        # sub-octave sine mix
    adsr: tuple[float, float, float, float] = (0.005, 0.12, 0.7, 0.15)
    cutoff: float = 0.0                     # lowpass Hz (0 = open)
    vibrato: float = 0.0                    # cents depth (rate fixed 5 Hz)
    fm_ratio: float = 1.0
    fm_index: float = 0.0
    gain: float = 0.9


PATCHES: dict[str, Patch] = {p.id: p for p in [
    Patch("synth_saw_lead", "Saw Lead", "Synth Lead", ("synth", "lead"),
          osc="saw", voices=2, detune=12, adsr=(0.004, 0.1, 0.8, 0.12),
          cutoff=6500, vibrato=8),
    Patch("synth_square_lead", "Square Lead", "Synth Lead", ("synth",),
          osc="square", voices=1, adsr=(0.004, 0.1, 0.8, 0.12), cutoff=5000,
          vibrato=6),
    Patch("synth_pad_warm", "Warm Pad", "Synth Pad", ("fx", "synth"),
          osc="saw", voices=3, detune=18, adsr=(0.4, 0.6, 0.85, 0.6),
          cutoff=3200, vibrato=4, gain=0.7),
    Patch("keys_epiano", "Electric Piano", "Piano & Keys", ("keys",),
          kind="fm", fm_ratio=1.0, fm_index=3.0, adsr=(0.003, 1.2, 0.0, 0.3),
          cutoff=7000),
    Patch("keys_piano", "Synth Piano", "Piano & Keys", ("keys",),
          osc="triangle", voices=2, detune=4, sub=0.2,
          adsr=(0.002, 1.4, 0.0, 0.25), cutoff=7500),
    Patch("organ_synth", "Drawbar Organ", "Organ", ("keys",),
          kind="organ", adsr=(0.01, 0.05, 0.95, 0.08), cutoff=6000),
    Patch("bass_synth", "Synth Bass", "Bass", ("bass",),
          osc="square", sub=0.5, adsr=(0.004, 0.15, 0.7, 0.1), cutoff=2200),
    Patch("bass_pluck", "Plucked Bass", "Bass", ("bass",),
          kind="pluck", adsr=(0.002, 0.05, 0.6, 0.12), cutoff=2500),
    Patch("guitar_pluck", "Plucked Guitar", "Guitar", ("guitar",),
          kind="pluck", adsr=(0.002, 0.05, 0.5, 0.2), cutoff=4500),
    Patch("strings_ensemble", "String Ensemble", "Strings", ("strings",),
          osc="saw", voices=3, detune=14, adsr=(0.25, 0.4, 0.9, 0.4),
          cutoff=4200, vibrato=6, gain=0.75),
    Patch("brass_synth", "Synth Brass", "Brass", ("brass",),
          osc="saw", voices=2, detune=10, adsr=(0.05, 0.2, 0.85, 0.18),
          cutoff=4800, vibrato=5),
    Patch("drum_kit", "Synth Drum Kit", "Drum Kits", ("drums",),
          kind="drums"),
]}

DEFAULT_PATCH: dict[str, str] = {
    "drums": "drum_kit", "bass": "bass_synth", "guitar": "guitar_pluck",
    "keys": "keys_epiano", "synth": "synth_saw_lead",
    "strings": "strings_ensemble", "brass": "brass_synth",
    "fx": "synth_pad_warm",
}


def default_patch(track_type: str) -> str:
    return DEFAULT_PATCH.get(track_type, "synth_saw_lead")


def get_patch(patch_id: str) -> Patch | None:
    return PATCHES.get(patch_id)


# --- synthesis -------------------------------------------------------------

def _unison(patch: Patch, freq: float, n: int, sr: int) -> np.ndarray:
    """Sum `voices` detuned oscillators (with vibrato), plus optional sub."""
    voices = max(1, patch.voices)
    out = np.zeros(n, dtype=np.float64)
    for v in range(voices):
        if voices > 1:
            cents = patch.detune * (v / (voices - 1) - 0.5)
        else:
            cents = 0.0
        vf = freq * 2.0 ** (cents / 1200.0)
        out += _osc(patch.osc, _freq_curve(vf, n, sr, patch.vibrato), n, sr)
    out /= voices
    if patch.sub > 0:
        out += patch.sub * _osc("sine", freq * 0.5, n, sr)
    return out


def _organ(freq: float, n: int, sr: int) -> np.ndarray:
    """Additive drawbar: fundamental + octave + fifth + 2nd octave."""
    drawbars = [(1.0, 1.0), (2.0, 0.6), (3.0, 0.4), (4.0, 0.25)]
    out = np.zeros(n, dtype=np.float64)
    for mult, amp in drawbars:
        out += amp * _osc("sine", freq * mult, n, sr)
    return out / sum(a for _, a in drawbars)


def _drum_hit(midi: int, sr: int) -> np.ndarray:
    """Synthesized GM drum voice keyed by note number."""
    def env(n, decay):
        return np.exp(-np.arange(n) / (decay * sr)).astype(np.float32)

    if midi in (35, 36):                       # kick
        n = int(0.35 * sr)
        pitch = 120.0 * np.exp(-np.arange(n) / (0.03 * sr)) + 45.0
        body = np.sin(2 * np.pi * np.cumsum(pitch) / sr)
        return (body * env(n, 0.12)).astype(np.float32)
    if midi in (38, 40):                       # snare
        n = int(0.22 * sr)
        tone = np.sin(2 * np.pi * 190.0 * np.arange(n) / sr) * env(n, 0.05)
        noise = _highpass(np.random.uniform(-1, 1, n), 1500, sr) * env(n, 0.09)
        return (0.5 * tone + 0.9 * noise).astype(np.float32)
    if midi in (42, 44):                       # closed hi-hat
        n = int(0.06 * sr)
        return (_highpass(np.random.uniform(-1, 1, n), 7000, sr)
                * env(n, 0.02)).astype(np.float32)
    if midi == 46:                             # open hi-hat
        n = int(0.35 * sr)
        return (_highpass(np.random.uniform(-1, 1, n), 6500, sr)
                * env(n, 0.14)).astype(np.float32)
    if midi in (49, 51, 57, 59):               # crash / ride
        n = int(0.9 * sr)
        return (_lowpass(np.random.uniform(-1, 1, n), 9000, sr)
                * env(n, 0.4)).astype(np.float32)
    if midi == 39:                             # hand clap
        n = int(0.18 * sr)
        base = _highpass(np.random.uniform(-1, 1, n), 1200, sr)
        e = env(n, 0.06)
        for off in (int(0.01 * sr), int(0.02 * sr), int(0.03 * sr)):
            e[off:] += env(n - off, 0.05)
        return (base * np.clip(e, 0, 1.5)).astype(np.float32)
    if 41 <= midi <= 50:                       # toms
        n = int(0.3 * sr)
        base = {45: 110, 47: 150, 48: 190, 50: 230}.get(midi, 160)
        pitch = base * np.exp(-np.arange(n) / (0.06 * sr)) + base * 0.6
        return (np.sin(2 * np.pi * np.cumsum(pitch) / sr)
                * env(n, 0.13)).astype(np.float32)
    n = int(0.1 * sr)                          # generic percussion click
    return (_highpass(np.random.uniform(-1, 1, n), 3000, sr)
            * env(n, 0.04)).astype(np.float32)


def render_note(patch: Patch, midi: int, dur_s: float, velocity: int,
                sr: int = SAMPLE_RATE) -> np.ndarray:
    """Synthesize a single note to a mono float32 buffer."""
    amp = (velocity / 127.0) ** 1.1 * patch.gain
    if patch.kind == "drums":
        return (_drum_hit(int(midi), sr) * amp).astype(np.float32)

    freq = _midi_to_freq(midi)
    gate_n = max(1, int(round(dur_s * sr)))
    env = _adsr(gate_n, *patch.adsr, sr)
    n = len(env)

    if patch.kind == "pluck":
        sig = _karplus(freq, n, sr)
    elif patch.kind == "fm":
        sig = _fm(freq, n, sr, patch.fm_ratio, patch.fm_index)
    elif patch.kind == "organ":
        sig = _organ(freq, n, sr)
    else:
        sig = _unison(patch, freq, n, sr)

    if patch.cutoff > 0:
        sig = _lowpass(sig, patch.cutoff, sr)
    return (sig * env * amp).astype(np.float32)


# --- catalog / specs (agent + frontend + browser) --------------------------

_CATEGORY_ORDER = ["Piano & Keys", "Organ", "Guitar", "Bass", "Strings",
                   "Brass", "Synth Lead", "Synth Pad", "Drum Kits"]


def synth_catalog() -> list[dict]:
    """Built-in patches grouped like sf2_parser.instrument_catalog(), with a
    `synth:<id>` sentinel asset_id and a `synth_patch` field the agent/UI use."""
    by_cat: dict[str, list[dict]] = {}
    for p in PATCHES.values():
        by_cat.setdefault(p.category, []).append({
            "label": p.label, "asset_id": f"synth:{p.id}",
            "soundfont": "Built-in synth", "bank": 0, "program": 0,
            "synth_patch": p.id,
        })
    ordered = _CATEGORY_ORDER + [c for c in by_cat if c not in _CATEGORY_ORDER]
    return [{"category": c, "presets": sorted(by_cat[c],
                                              key=lambda x: x["label"].lower())}
            for c in ordered if c in by_cat]


def synth_patch_specs() -> list[dict]:
    """Full DSP params of every patch — the single source of truth the
    browser's WebAudio synth reads so both engines stay in sync."""
    return [{**asdict(p), "adsr": list(p.adsr),
             "track_types": list(p.track_types)} for p in PATCHES.values()]
