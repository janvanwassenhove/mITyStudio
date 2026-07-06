"""Phases 12-14: SoundFont rendering, sample rendering, effects."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tests.test_midi_export import build_song
from tests.test_projects import make_project
from tests.test_sample_analysis import write_tone

REPO_SOUNDFONTS = Path(__file__).resolve().parents[3] / "soundfonts"


def _smallest_sf2() -> Path | None:
    if not REPO_SOUNDFONTS.exists():
        return None
    candidates = sorted(REPO_SOUNDFONTS.glob("*.sf2"), key=lambda p: p.stat().st_size)
    candidates += sorted(REPO_SOUNDFONTS.glob("*.SF2"), key=lambda p: p.stat().st_size)
    return candidates[0] if candidates else None


def _fluidsynth_available() -> bool:
    return shutil.which("fluidsynth") is not None


@pytest.mark.skipif(not _fluidsynth_available() or _smallest_sf2() is None,
                    reason="needs fluidsynth + a .sf2 in soundfonts/")
def test_instrument_stem_rendering(client, workspace):
    # place a real (small) soundfont in the isolated workspace
    sf2 = _smallest_sf2()
    shutil.copy2(sf2, workspace.soundfonts_dir / sf2.name)
    client.post("/api/assets/rescan")

    p = build_song(client)
    r = client.post(f"/api/projects/{p['id']}/render/instrument-stems")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["errors"] == []
    assert len(body["rendered"]) == 2

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert len(proj["stems"]) == 2
    for stem in proj["stems"]:
        path = workspace.root / stem["path"]
        assert path.exists() and path.stat().st_size > 1000
        assert stem["stem_type"] == "instrument"
        assert stem["asset_id"]

    # stems registered as assets
    stems = client.get("/api/assets?asset_type=rendered_stem").json()
    assert len(stems) == 2

    # second render skips up-to-date stems
    r2 = client.post(f"/api/projects/{p['id']}/render/instrument-stems").json()
    assert len(r2["rendered"]) == 0
    assert any("up to date" in s for s in r2["skipped"])

    # stem file serving works
    track_id = proj["stems"][0]["track_id"]
    f = client.get(f"/api/projects/{p['id']}/stems/{track_id}/file")
    assert f.status_code == 200


def test_instrument_render_without_soundfont_fails_gracefully(client):
    p = build_song(client)
    r = client.post(f"/api/projects/{p['id']}/render/instrument-stems")
    assert r.status_code == 200  # no crash
    body = r.json()
    assert body["rendered"] == []
    assert body["errors"]
    assert any("soundfont" in e.lower() or "fluidsynth" in e.lower()
               for e in body["errors"])


def test_sample_stem_rendering(client, workspace):
    write_tone(workspace.samples_dir / "loop.wav", seconds=1.0, freq=220, rate=44100)
    client.post("/api/assets/rescan")
    sample = client.get("/api/assets/samples").json()[0]

    p = make_project(client, bpm=120)
    p["sections"] = [{"name": "A", "start_bar": 0, "length_bars": 4}]
    p["tracks"] = [{
        "name": "Loops", "track_type": "sample",
        "clips": [
            {"clip_type": "sample", "start_beat": 4, "duration_beats": 8,
             "source_asset_id": sample["id"], "loop": True},
            {"clip_type": "sample", "start_beat": 0, "duration_beats": 2,
             "source_asset_id": sample["id"], "gain_db": -6,
             "fade_in_seconds": 0.1, "fade_out_seconds": 0.1},
        ]}]
    client.put(f"/api/projects/{p['id']}", json=p)

    r = client.post(f"/api/projects/{p['id']}/render/sample-stems")
    assert r.status_code == 200, r.text
    assert len(r.json()["rendered"]) == 1

    proj = client.get(f"/api/projects/{p['id']}").json()
    stem_path = workspace.root / proj["stems"][0]["path"]
    data, rate = sf.read(str(stem_path))
    assert rate == 44100
    # project is 16 beats @120bpm = 8s
    assert abs(len(data) / rate - 8.0) < 0.1
    # loop clip: audio present at beat 4 (2s) through beat 12 (6s)
    assert np.abs(data[int(3.0 * rate):int(5.5 * rate)]).max() > 0.05
    # silence after loop region ends (last 2 beats: 7-8s)
    assert np.abs(data[int(7.2 * rate):]).max() < 0.01

    # waveform metadata generated for timeline
    m = client.get(f"/api/projects/{p['id']}/playback-manifest").json()
    assert len(m["waveform_metadata"]) == 1
    assert len(m["waveform_metadata"][0]["peaks"]) > 50


def test_effects_chain(workspace):
    import numpy as np
    from app.models.song import Effect, EffectChain
    from app.services.render.effects import apply_effect_chain

    rate = 44100
    t = np.linspace(0, 1, rate, endpoint=False)
    audio = np.stack([np.sin(2 * np.pi * 220 * t)] * 2, axis=1).astype(np.float32) * 0.5

    chain = EffectChain(effects=[
        Effect(effect_type="gain", params={"gain_db": -6}),
        Effect(effect_type="distortion", params={"drive": 5}),
        Effect(effect_type="reverb", params={"mix": 0.3}),
        Effect(effect_type="eq", params={}),          # placeholder
        Effect(effect_type="compressor", params={}),  # placeholder
        Effect(effect_type="delay", params={"time_seconds": 0.1, "mix": 0.4}),
    ])
    out, warnings = apply_effect_chain(audio, rate, chain)
    assert out.shape == audio.shape
    assert not np.array_equal(out, audio)
    assert len([w for w in warnings if "placeholder" in w]) == 2

    # disabled effect is skipped
    chain2 = EffectChain(effects=[Effect(effect_type="gain", enabled=False,
                                         params={"gain_db": -20})])
    out2, _ = apply_effect_chain(audio, rate, chain2)
    assert np.array_equal(out2, audio)
