"""Full-studio features: vocal effects (robot etc.), AI voice from recording,
recorded takes on vocal tracks, section 'all' generation, clip offset,
model listing."""
from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from tests.test_projects import make_project
from tests.test_sample_analysis import write_tone
from tests.test_voice_and_vocals import upload_recording


# --- new effects ------------------------------------------------------------

def test_vocal_effects_robot_telephone_chorus(workspace):
    from app.models.song import Effect, EffectChain
    from app.services.render.effects import apply_effect_chain

    rate = 44100
    t = np.linspace(0, 1, rate, endpoint=False)
    audio = np.stack([np.sin(2 * np.pi * 220 * t)] * 2, axis=1).astype(np.float32) * 0.5

    for etype, params in (("robot", {"carrier_hz": 50}),
                          ("telephone", {}),
                          ("chorus", {})):
        out, warnings = apply_effect_chain(
            audio, rate, EffectChain(effects=[Effect(effect_type=etype,
                                                     params=params)]))
        assert out.shape == audio.shape, etype
        assert not np.allclose(out, audio), f"{etype} did not change audio"
        assert warnings == [], etype

    # robot ring-mod creates sidebands: energy at 220±50 Hz
    out, _ = apply_effect_chain(audio, rate, EffectChain(effects=[
        Effect(effect_type="robot", params={"carrier_hz": 50, "crush": 0})]))
    spec = np.abs(np.fft.rfft(out[:, 0]))
    assert spec[270] > spec[220] * 2  # sideband dominates original


# --- AI voice from recording -------------------------------------------------

def _make_voice_project(client, workspace, with_profile: bool):
    # a pitched 'voice' recording (200 Hz tone) → consented profile
    rec = upload_recording(client, name="voice.wav")
    profile_id = None
    if with_profile:
        r = client.post("/api/voice/profiles", json={
            "name": "My AI Voice", "source_recording_ids": [rec["id"]],
            "consent_confirmed": True, "consent_notes": "self, 2026-07-06"})
        profile_id = r.json()["id"]

    p = make_project(client, bpm=120)
    p["sections"] = [{"name": "A", "start_bar": 0, "length_bars": 2}]
    p["tracks"] = [{
        "name": "Lead", "track_type": "lead_vocal",
        "voice_profile_id": profile_id,
        "clips": [{"clip_type": "midi", "start_beat": 0, "duration_beats": 8,
                   "note_events": [
                       {"midi_note": 60, "start_beat": 0, "duration_beats": 2,
                        "lyric_syllable": "la"},
                       {"midi_note": 64, "start_beat": 2, "duration_beats": 2,
                        "lyric_syllable": "lo"},
                   ]}]}]
    r = client.put(f"/api/projects/{p['id']}", json=p)
    assert r.status_code == 200, r.text
    return r.json(), rec


def test_recording_voice_engine(client, workspace):
    p, _ = _make_voice_project(client, workspace, with_profile=True)
    r = client.post(f"/api/projects/{p['id']}/vocals/render")
    body = r.json()
    assert body["errors"] == []
    assert any("recording-voice engine" in log for log in body["render_log"]), \
        body["render_log"]

    proj = client.get(f"/api/projects/{p['id']}").json()
    stem = workspace.root / proj["stems"][0]["path"]
    data, rate = sf.read(str(stem))
    assert np.abs(data).max() > 0.05  # audible

    # pitch of first note region ≈ C4 (261.6 Hz) even though source was 200 Hz
    from app.services.sample_analysis import _estimate_pitch
    seg = data[: rate, 0] if data.ndim > 1 else data[:rate]
    note, freq = _estimate_pitch(seg.astype(np.float32), rate)
    assert freq is not None and abs(freq - 261.6) < 15, (note, freq)


def test_formant_engine_without_profile(client, workspace):
    p, _ = _make_voice_project(client, workspace, with_profile=False)
    r = client.post(f"/api/projects/{p['id']}/vocals/render")
    assert any("formant engine" in log for log in r.json()["render_log"])


def test_recorded_take_mixed_into_vocal_stem(client, workspace):
    p, rec = _make_voice_project(client, workspace, with_profile=False)
    # place the recording as a take at beat 4 (2.0 s @ 120 bpm)
    proj = client.get(f"/api/projects/{p['id']}").json()
    proj["tracks"][0]["clips"].append({
        "clip_type": "sample", "start_beat": 4, "duration_beats": 4,
        "source_asset_id": rec["id"]})
    # remove melody so only the take makes sound
    proj["tracks"][0]["clips"][0]["note_events"] = []
    assert client.put(f"/api/projects/{p['id']}", json=proj).status_code == 200

    r = client.post(f"/api/projects/{p['id']}/vocals/render")
    assert any("recorded take" in log for log in r.json()["render_log"])
    proj = client.get(f"/api/projects/{p['id']}").json()
    data, rate = sf.read(str(workspace.root / proj["stems"][0]["path"]))
    assert np.abs(data[: int(1.8 * rate)]).max() < 0.01   # silence before take
    assert np.abs(data[int(2.0 * rate):int(2.4 * rate)]).max() > 0.05  # take audible


# --- clip source offset (split support) --------------------------------------

def test_sample_clip_source_offset(client, workspace):
    # 1 s of silence then 1 s of tone; offset 1 s should start at the tone
    rate = 44100
    t = np.linspace(0, 1, rate, endpoint=False)
    audio = np.concatenate([np.zeros(rate), 0.5 * np.sin(2 * np.pi * 440 * t)])
    sf.write(str(workspace.samples_dir / "padded.wav"), audio.astype(np.float32), rate)
    client.post("/api/assets/rescan")
    sample = client.get("/api/assets/samples").json()[0]

    p = make_project(client, bpm=120)
    p["sections"] = [{"name": "A", "start_bar": 0, "length_bars": 1}]
    p["tracks"] = [{"name": "S", "track_type": "sample",
                    "clips": [{"clip_type": "sample", "start_beat": 0,
                               "duration_beats": 2,
                               "source_asset_id": sample["id"],
                               "source_offset_seconds": 1.0}]}]
    client.put(f"/api/projects/{p['id']}", json=p)
    client.post(f"/api/projects/{p['id']}/render/sample-stems")
    proj = client.get(f"/api/projects/{p['id']}").json()
    data, srate = sf.read(str(workspace.root / proj["stems"][0]["path"]))
    # with offset applied, sound starts immediately
    assert np.abs(data[: srate // 4]).max() > 0.05


# --- section "all" generation -------------------------------------------------

def test_generate_for_all_sections(client, workspace):
    from app.models.operations import ChatOperation
    from app.models.song import Section, SongProject
    from app.services import operation_applier

    project = SongProject(title="t", sections=[
        Section(name="A", start_bar=0, length_bars=4),
        Section(name="B", start_bar=4, length_bars=4),
        Section(name="C", start_bar=8, length_bars=4),
    ])
    results = operation_applier.apply_operations(project, [
        ChatOperation(op_type="generate_chords",
                      params={"section": "all", "track": "Piano",
                              "track_type": "keys"})])
    assert results[0].applied, results[0].error
    piano = project.tracks[0]
    assert len(piano.clips) == 3
    assert {c.section_id for c in piano.clips} == {s.id for s in project.sections}


# --- model listing -------------------------------------------------------------

def test_models_endpoint(client, workspace, monkeypatch):
    for env in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "OPENAI_API_KEY",
                "MITY_LLM_API_KEY"):
        monkeypatch.delenv(env, raising=False)

    r = client.get("/api/settings/llm/models?provider=mock").json()
    assert r == {"models": ["mock"], "source": "static"}

    r = client.get("/api/settings/llm/models?provider=anthropic").json()
    assert r["source"] == "fallback"
    assert "claude-sonnet-5" in r["models"]

    r = client.get("/api/settings/llm/models?provider=openai").json()
    assert r["source"] == "fallback"
    assert any(m.startswith("gpt-") for m in r["models"])

    assert client.get("/api/settings/llm/models?provider=nope").status_code == 422
