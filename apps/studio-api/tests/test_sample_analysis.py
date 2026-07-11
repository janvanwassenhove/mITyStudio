"""Phase 8: sample analysis + search."""
from __future__ import annotations

import numpy as np
import soundfile as sf


def write_tone(path, seconds=1.0, freq=440.0, rate=22050, amp=0.5):
    t = np.linspace(0, seconds, int(seconds * rate), endpoint=False)
    sf.write(str(path), (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32), rate)


def test_analyse_sample(client, workspace):
    write_tone(workspace.samples_dir / "pad 1 - 120 BPM - Am.wav", seconds=2.0)
    client.post("/api/assets/rescan")
    asset = client.get("/api/assets/samples").json()[0]

    r = client.post(f"/api/assets/{asset['id']}/analyse")
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["duration"] == 2.0
    assert a["sample_rate"] == 22050
    assert a["channels"] == 1
    assert a["loudness_rms"] > 0.2
    assert a["peak_level"] > 0.4
    assert a["estimated_bpm"] == 120.0
    assert a["bpm_source"] == "filename"
    assert a["estimated_key"] == "A minor"
    assert a["silence_start"] < 0.01
    from app.services.sample_analysis import ANALYSIS_VERSION
    assert a["analysis_version"] == ANALYSIS_VERSION

    after = client.get(f"/api/assets/{asset['id']}").json()
    assert after["analysis_status"] == "analysed"
    assert "120 BPM" in after["generated_description"]


def test_analysis_never_touches_original(client, workspace):
    f = workspace.samples_dir / "kick.wav"
    write_tone(f, seconds=0.3, freq=60)
    before = f.read_bytes()
    client.post("/api/assets/rescan")
    asset = client.get("/api/assets/samples").json()[0]
    client.post(f"/api/assets/{asset['id']}/analyse")
    assert f.read_bytes() == before


def test_search(client, workspace):
    write_tone(workspace.samples_dir / "bass loop - 140 BPM.wav", seconds=2.0, freq=80)
    write_tone(workspace.samples_dir / "slow pad - 80 BPM.wav", seconds=2.0)
    client.post("/api/assets/rescan")
    for a in client.get("/api/assets/samples").json():
        client.post(f"/api/assets/{a['id']}/analyse")

    hits = client.get("/api/assets/search?bpm_min=120&bpm_max=160").json()
    assert len(hits) == 1
    assert "140" in hits[0]["filename"]

    hits = client.get("/api/assets/search?text=pad").json()
    assert len(hits) == 1
    assert "pad" in hits[0]["filename"]

    # tag search after user tagging
    asset = client.get("/api/assets/samples").json()[0]
    client.patch(f"/api/assets/{asset['id']}/metadata", json={"tags": ["dark"]})
    hits = client.get("/api/assets/search?tags=dark").json()
    assert len(hits) == 1
