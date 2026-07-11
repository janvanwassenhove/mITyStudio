"""Phase 2: guided wizard — take QA, range detection, guides, consent audit,
device/tier, confidence."""
from __future__ import annotations

import numpy as np
import soundfile as sf

from tests.test_voice_and_vocals import upload_recording


def _write(path, audio, rate=22050):
    sf.write(str(path), audio.astype(np.float32), rate)


def test_take_qa_verdicts(workspace, tmp_path):
    from app.services.voice_wizard import qa_take
    rate = 22050
    t = np.linspace(0, 3, rate * 3, endpoint=False)

    good = 0.35 * np.sin(2 * np.pi * 220 * t)
    _write(tmp_path / "good.wav", good)
    assert qa_take(tmp_path / "good.wav")["verdict"] == "pass"

    clipped = np.clip(1.6 * np.sin(2 * np.pi * 220 * t), -1, 1)
    _write(tmp_path / "clip.wav", clipped)
    r = qa_take(tmp_path / "clip.wav")
    assert r["verdict"] == "fail"
    assert "clipping detected" in r["issues"]

    quiet = 0.004 * np.sin(2 * np.pi * 220 * t)
    _write(tmp_path / "quiet.wav", quiet)
    r = qa_take(tmp_path / "quiet.wav")
    assert r["verdict"] in ("warn", "fail")
    assert any("quiet" in i or "silence" in i for i in r["issues"])

    short = 0.35 * np.sin(2 * np.pi * 220 * t[: rate // 2])
    _write(tmp_path / "short.wav", short)
    assert "too short" in qa_take(tmp_path / "short.wav")["issues"]


def test_range_detection(workspace, tmp_path):
    from app.services.voice_wizard import detect_range
    rate = 22050
    # a sung 'scale': A2 (110) up to A4 (440) in steps
    freqs = [110 * 2 ** (i / 6) for i in range(13)]
    audio = np.concatenate([
        0.4 * np.sin(2 * np.pi * f * np.linspace(0, 0.5, rate // 2, endpoint=False))
        for f in freqs])
    _write(tmp_path / "scale.wav", audio)
    r = detect_range(tmp_path / "scale.wav")
    assert "error" not in r
    assert 43 <= r["low_midi"] <= 47      # ~A2
    assert 67 <= r["high_midi"] <= 71     # ~A4
    assert "–" in r["vocal_range"]


def test_wizard_endpoints(client, workspace):
    exercises = client.get("/api/voice/wizard/exercises").json()
    assert len(exercises) >= 5
    assert all({"id", "title", "coach", "guide"} <= set(e) for e in exercises)

    # every exercise carries a karaoke guide; note exercises expose timed cues
    by_id = {e["id"]: e for e in exercises}
    phrase = by_id["phrase"]["guide"]
    assert phrase["kind"] == "notes" and len(phrase["cues"]) == 5
    assert phrase["cues"][0]["note"] and phrase["cues"][0]["at"] == 0.0
    assert phrase["cues"][1]["at"] > phrase["cues"][0]["at"]  # cues advance

    # spoken exercises carry fixed text, localized by ?language=
    en = {e["id"]: e for e in client.get(
        "/api/voice/wizard/exercises?language=en").json()}
    nl = {e["id"]: e for e in client.get(
        "/api/voice/wizard/exercises?language=nl").json()}
    assert en["speech"]["guide"]["lines"] != nl["speech"]["guide"]["lines"]
    assert en["speech"]["guide"]["kind"] == "text"

    g = client.get(f"/api/voice/wizard/guide/{exercises[0]['id']}")
    assert g.status_code == 200
    assert g.headers["content-type"].startswith("audio/")
    assert client.get("/api/voice/wizard/guide/nope").status_code == 404

    d = client.get("/api/voice/device").json()
    assert d["device"] in ("cuda", "mps", "cpu")
    assert d["recommended_tier"] in ("quick", "full")
    assert d["tiers"] == {"quick": 60, "full": 200}

    rec = upload_recording(client)
    qa = client.post(f"/api/voice/recordings/{rec['id']}/qa").json()
    assert qa["verdict"] in ("pass", "warn", "fail")


def test_consent_audit_record(client, workspace):
    rec = upload_recording(client, name="take.wav")
    consent = upload_recording(client, name="consent.wav")
    r = client.post("/api/voice/profiles", json={
        "name": "Wizard Voice", "source_recording_ids": [rec["id"]],
        "consent_confirmed": True,
        "consent_notes": "verbal consent recorded in wizard",
        "consent_recording_id": consent["id"]})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["consent_recording_id"] == consent["id"]
    assert p["consent_recorded_at"]  # timestamped audit
    # persisted
    got = client.get(f"/api/voice/profiles/{p['id']}").json()
    assert got["consent_recording_id"] == consent["id"]
    # invalid consent clip rejected
    r2 = client.post("/api/voice/profiles", json={
        "name": "X", "source_recording_ids": [rec["id"]],
        "consent_confirmed": True, "consent_recording_id": "invented"})
    assert r2.status_code == 422


def test_confidence_endpoint(client, workspace):
    rec = upload_recording(client)
    p = client.post("/api/voice/profiles", json={
        "name": "V", "source_recording_ids": [rec["id"]],
        "consent_confirmed": True}).json()
    c = client.get(f"/api/voice/profiles/{p['id']}/confidence").json()
    assert 0 <= c["score"] <= 1
    assert c["minutes"] < 1
    assert any("5 minutes" in n for n in c["notes"])  # honest about tiny data


def test_train_tier_validation(client, workspace):
    rec = upload_recording(client)
    p = client.post("/api/voice/profiles", json={
        "name": "V", "source_recording_ids": [rec["id"]],
        "consent_confirmed": True}).json()
    # bad tier rejected before anything else
    assert client.post(f"/api/voice/profiles/{p['id']}/train?tier=turbo").status_code == 422
    # rvc stack not installed in the isolated test workspace → clean 503
    assert client.post(f"/api/voice/profiles/{p['id']}/train?tier=quick").status_code == 503