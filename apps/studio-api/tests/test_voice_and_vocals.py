"""Phases 15-18: voice upload, consent-gated profiles, mock vocal render,
lyrics alignment."""
from __future__ import annotations

import io
import wave

import numpy as np
import soundfile as sf

from tests.test_projects import make_project


def _wav_bytes(seconds=0.5, rate=16000) -> bytes:
    buf = io.BytesIO()
    t = np.linspace(0, seconds, int(seconds * rate), endpoint=False)
    data = (0.4 * np.sin(2 * np.pi * 200 * t) * 32767).astype(np.int16)
    with wave.open(buf, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    return buf.getvalue()


def upload_recording(client, name="take1.wav", source="upload"):
    r = client.post("/api/voice/recordings/upload",
                    files={"file": (name, _wav_bytes(), "audio/wav")},
                    data={"source": source})
    assert r.status_code == 201, r.text
    return r.json()


def test_voice_upload_and_registration(client, workspace):
    asset = upload_recording(client, source="live_recording")
    assert asset["asset_type"] == "voice_recording"
    assert asset["source"] == "live_recording"
    assert "0.50s" in asset["generated_description"]
    # saved under voices/recordings
    assert asset["relative_path"].startswith("voices/recordings/")
    assert (workspace.root / asset["relative_path"]).exists()
    # listed and previewable
    listed = client.get("/api/assets/voice-recordings").json()
    assert len(listed) == 1
    f = client.get(f"/api/assets/{asset['id']}/file")
    assert f.status_code == 200

    # rejects junk
    r = client.post("/api/voice/recordings/upload",
                    files={"file": ("x.exe", b"MZ", "application/x-msdownload")})
    assert r.status_code == 422


def test_voice_profile_requires_consent(client):
    rec = upload_recording(client)
    r = client.post("/api/voice/profiles", json={
        "name": "My Voice", "source_recording_ids": [rec["id"]],
        "consent_confirmed": False})
    assert r.status_code == 403

    r = client.post("/api/voice/profiles", json={
        "name": "My Voice", "source_recording_ids": [rec["id"]],
        "consent_confirmed": True,
        "consent_notes": "self-recording, consent given 2026-07-06"})
    assert r.status_code == 201
    profile = r.json()
    assert profile["consent_confirmed"] is True
    assert profile["source_recording_ids"] == [rec["id"]]

    # appears in asset library as voice_profile
    assets = client.get("/api/assets?asset_type=voice_profile").json()
    assert len(assets) == 1

    # profile referencing unknown recording rejected
    r = client.post("/api/voice/profiles", json={
        "name": "Fake", "source_recording_ids": ["invented"],
        "consent_confirmed": True})
    assert r.status_code == 422


def make_vocal_song(client):
    p = make_project(client, bpm=120)
    client.post(f"/api/projects/{p['id']}/chat",
                json={"message": "create a pop song"})
    client.post(f"/api/projects/{p['id']}/chat",
                json={"message": "add lyrics about the stars"})
    return client.get(f"/api/projects/{p['id']}").json()


def test_mock_vocal_render_and_alignment(client, workspace):
    p = make_vocal_song(client)
    assert any(t["track_type"] == "lead_vocal" for t in p["tracks"])

    r = client.post(f"/api/projects/{p['id']}/vocals/render")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rendered"]) == 1
    assert body["errors"] == []

    proj = client.get(f"/api/projects/{p['id']}").json()
    vocal_stems = [s for s in proj["stems"] if s["stem_type"] == "vocal"]
    assert len(vocal_stems) == 1
    stem_path = workspace.root / vocal_stems[0]["path"]
    data, rate = sf.read(str(stem_path))
    assert np.abs(data).max() > 0.01  # audible, not silence
    # registered as vocal_stem asset
    assert client.get("/api/assets?asset_type=vocal_stem").json()

    # lyrics alignment in manifest with correct structure and ordering
    m = client.get(f"/api/projects/{p['id']}/playback-manifest").json()
    align = m["lyrics_alignment"]
    assert len(align) >= 4
    for line in align:
        assert line["end_time"] > line["start_time"] >= 0
        assert line["words"]
        for w in line["words"]:
            assert w["end_time"] >= w["start_time"]
        assert 0 <= line["confidence"] <= 1
    # words linked to melody notes
    linked = [w for l in align for w in l["words"] if w["linked_note_id"]]
    assert linked
    # alignment times within song duration
    assert align[-1]["end_time"] <= m["duration_seconds"] + 0.01
