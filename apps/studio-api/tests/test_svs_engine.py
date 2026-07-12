"""SVS (DiffSinger voicebank) engine — driver tested end-to-end against a
tiny fake ONNX voicebank: the fake vocoder synthesizes a sine at the input
f0, so phonemization, duration math, ONNX plumbing AND pitch placement are
all verified without a real (multi-hundred-MB) bank."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("onnxruntime")
torch = pytest.importorskip("torch")
pytest.importorskip("onnx")   # torch.onnx.export needs it (test-only dep)


def _build_fake_bank(root):
    """voices/svs/testbank with acoustic.onnx + vocoder — real ONNX models."""
    import torch.nn as nn

    bank = root / "voices" / "svs" / "testbank"
    bank.mkdir(parents=True)

    class Acoustic(nn.Module):
        def forward(self, tokens, durations, f0, speedup):
            # consume every input or torch.onnx.export prunes it from the
            # graph (real banks declare all of these)
            mel = f0.unsqueeze(-1).repeat(1, 1, 128) * 0.001
            return (mel + tokens.float().sum() * 0
                    + durations.float().sum() * 0 + speedup.float() * 0)

    class Vocoder(nn.Module):
        HOP = 512

        def forward(self, mel, f0):
            # sine at f0, frame-expanded — pitch-accurate synthetic singing
            per = f0.repeat_interleave(self.HOP, dim=1)
            phase = torch.cumsum(2 * torch.pi * per / 44100.0, dim=1)
            return 0.5 * torch.sin(phase) + mel.sum() * 0

    torch.onnx.export(
        Acoustic(),
        (torch.zeros(1, 3, dtype=torch.int64),
         torch.ones(1, 3, dtype=torch.int64),
         torch.full((1, 10), 220.0), torch.tensor([50], dtype=torch.int64)),
        str(bank / "acoustic.onnx"),
        input_names=["tokens", "durations", "f0", "speedup"],
        output_names=["mel"],
        dynamic_axes={"tokens": {1: "n"}, "durations": {1: "n"},
                      "f0": {1: "t"}, "mel": {1: "t"}})
    voc = bank / "vocoder"
    voc.mkdir()
    torch.onnx.export(
        Vocoder(),
        (torch.zeros(1, 10, 128), torch.full((1, 10), 220.0)),
        str(voc / "vocoder.onnx"),
        input_names=["mel", "f0"], output_names=["waveform"],
        dynamic_axes={"mel": {1: "t"}, "f0": {1: "t"},
                      "waveform": {1: "s"}})
    (voc / "vocoder.yaml").write_text(
        "sample_rate: 44100\nhop_size: 512\nmodel: vocoder.onnx\n",
        encoding="utf-8")

    (bank / "phonemes.txt").write_text(
        "\n".join(["SP", "hh", "ah", "l", "ow", "w", "er", "d", "s",
                   "ih", "ng"]), encoding="utf-8")
    (bank / "dsconfig.yaml").write_text(
        "name: TestBank\nacoustic: acoustic.onnx\nphonemes: phonemes.txt\n",
        encoding="utf-8")
    (bank / "dsdict-en.yaml").write_text("""
symbols:
- {symbol: ah, type: vowel}
- {symbol: ow, type: vowel}
- {symbol: er, type: vowel}
- {symbol: ih, type: vowel}
entries:
- {grapheme: hello, phonemes: [hh, ah, l, ow]}
- {grapheme: world, phonemes: [w, er, l, d]}
- {grapheme: sing, phonemes: [s, ih, ng]}
""", encoding="utf-8")
    return bank


def test_bank_discovery_and_phonemization(client, workspace, monkeypatch):
    monkeypatch.delenv("MITY_DISABLE_SVS", raising=False)
    _build_fake_bank(workspace.root)
    from app.services import svs_engine

    banks = svs_engine.find_banks()
    assert len(banks) == 1
    bank = banks[0]
    assert bank.name == "TestBank"
    assert bank.tokens["SP"] == 0
    assert "ah" in bank.vowels

    # "hello world" = 3 syllables → 3 notes, vowel-anchored phoneme groups
    groups = svs_engine.line_note_phonemes(bank, "hello world",
                                           ["hel", "lo", "world"])
    assert groups is not None and len(groups) == 3
    assert groups[0][0] == "hh"                # onset consonant kept
    flat = [p for g in groups for p in g]
    assert flat == ["hh", "ah", "l", "ow", "w", "er", "l", "d"]

    # unknown word → None (line falls back to the clone chain)
    assert svs_engine.line_note_phonemes(bank, "xyzzy", ["xyz"]) is None

    st = svs_engine.svs_status()
    assert st["banks"] and st["banks"][0]["name"] == "TestBank"


def test_svs_sings_at_the_right_pitch(client, workspace, monkeypatch):
    """Full engine render on a real project: the fake vocoder outputs a sine
    at the driver's f0 curve — measured pitch must match the melody."""
    monkeypatch.delenv("MITY_DISABLE_SVS", raising=False)
    _build_fake_bank(workspace.root)
    from app.models.song import (LyricsLine, Section, SongProject, Track)
    from app.services import svs_engine
    from app.services.vocal_engine import available_engine_tier, get_engine

    p = SongProject(title="svs", bpm=120, key="C major", style="pop")
    s = Section(name="V", start_bar=0, length_bars=4)
    p.sections = [s]
    t = Track(name="Lead Vocal", track_type="lead_vocal")
    p.tracks = [t]
    p.lyrics.lines.append(LyricsLine(section_id=s.id, text="hello world"))
    from app.services.music_gen import generate_vocal_melody
    clip = generate_vocal_melody(p, s, ["hello world"])
    t.clips.append(clip)

    # no profile → SVS engine selected, tier 4
    engine = get_engine("mock", None)
    assert isinstance(engine, svs_engine.SvsSingingEngine)
    assert available_engine_tier(None) == 4

    out = workspace.root / "stems" / "svs_test.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = engine.render(p, t, out)
    assert r.stem_path is not None
    assert any("SVS engine" in line for line in r.render_log)

    import soundfile as sf
    data, rate = sf.read(str(out), dtype="float32")
    mono = data[:, 0]
    assert float(np.abs(mono).max()) > 0.1     # audible

    # measure pitch inside the first note's span vs its melody frequency
    n0 = clip.note_events[0]
    f_target = 440.0 * 2 ** ((n0.midi_note - 69) / 12)
    a = int((clip.start_beat + n0.start_beat) * 0.5 * rate)   # 120bpm
    b = a + int(n0.duration_beats * 0.5 * rate)
    seg = mono[a + 800:b]                       # skip the onset consonant
    zc = np.where(np.diff(np.sign(seg)) > 0)[0]
    measured = rate / np.diff(zc).mean()
    assert abs(measured - f_target) / f_target < 0.05, \
        f"sang {measured:.1f} Hz, melody wants {f_target:.1f} Hz"


def test_svs_unsupported_language_falls_back(client, workspace, monkeypatch):
    """Lyrics outside the bank's dictionary must not silence the song —
    render_vocal_stems retries with the clone chain (PSOLA/mock here)."""
    monkeypatch.delenv("MITY_DISABLE_SVS", raising=False)
    _build_fake_bank(workspace.root)
    from tests.test_voice_and_vocals import make_vocal_song
    from app.services import project_repo, vocal_engine

    p = make_vocal_song(client)                # lyrics NOT in the tiny dict
    project = project_repo.load_project(p["id"])
    r = vocal_engine.render_vocal_stems(project)
    assert r["errors"] == []
    assert any("clone engine" in line for line in r["render_log"])
    stem = next(s for s in project.stems if s.stem_type == "vocal")
    assert stem.engine_tier == 3               # honest tier after fallback
