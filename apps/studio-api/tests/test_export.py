"""Phases 20-21: combined mix export (WAV/MP3) and package export."""
from __future__ import annotations

import shutil

import numpy as np
import pytest
import soundfile as sf

from tests.test_projects import make_project
from tests.test_sample_analysis import write_tone
from tests.test_voice_and_vocals import make_vocal_song


def _ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def build_mixable_project(client, workspace):
    """Project with a sample track + vocal track (no FluidSynth needed)."""
    write_tone(workspace.samples_dir / "pad.wav", seconds=2.0, freq=330, rate=44100)
    client.post("/api/assets/rescan")
    sample = client.get("/api/assets/samples").json()[0]

    p = make_vocal_song(client)
    p["tracks"].append({
        "name": "Pad", "track_type": "sample",
        "volume": 0.8, "pan": -0.4,
        "effects": {"effects": [{"effect_type": "reverb", "params": {"mix": 0.2}}]},
        "clips": [{"clip_type": "sample", "start_beat": 0, "duration_beats": 16,
                   "source_asset_id": sample["id"], "loop": True}]})
    # keep only vocal + sample tracks so mixdown works without FluidSynth
    p["tracks"] = [t for t in p["tracks"]
                   if t["track_type"] in ("sample", "lead_vocal")]
    r = client.put(f"/api/projects/{p['id']}", json=p)
    assert r.status_code == 200, r.text
    return r.json()


def test_export_combined_wav(client, workspace):
    p = build_mixable_project(client, workspace)
    r = client.post(f"/api/projects/{p['id']}/export/mix",
                    json={"formats": ["wav"]})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "completed", job["errors"]
    assert len(job["output_files"]) == 1
    wav = workspace.root / job["output_files"][0]
    assert wav.exists()
    data, rate = sf.read(str(wav))
    assert rate == 44100
    assert data.shape[1] == 2
    assert np.abs(data).max() > 0.01     # combined audio, not silence
    assert np.abs(data).max() <= 1.0     # no clipping

    # stems were auto-rendered (sample + vocal)
    proj = client.get(f"/api/projects/{p['id']}").json()
    stem_types = {s["stem_type"] for s in proj["stems"]}
    assert {"sample", "vocal"} <= stem_types

    # registered as exported_mix asset
    mixes = client.get("/api/assets?asset_type=exported_mix").json()
    assert len(mixes) == 1

    # job listed
    jobs = client.get(f"/api/projects/{p['id']}/exports").json()
    assert jobs[0]["id"] == job["id"]

    # download endpoint works and blocks path traversal
    dl = client.get(f"/api/projects/{p['id']}/exports/download",
                    params={"path": job["output_files"][0]})
    assert dl.status_code == 200
    bad = client.get(f"/api/projects/{p['id']}/exports/download",
                     params={"path": "../../scores/x"})
    assert bad.status_code == 403


@pytest.mark.skipif(not _ffmpeg(), reason="ffmpeg not available")
def test_export_mp3(client, workspace):
    p = build_mixable_project(client, workspace)
    r = client.post(f"/api/projects/{p['id']}/export/mix",
                    json={"formats": ["wav", "mp3"]})
    job = r.json()
    assert job["status"] == "completed", job["errors"]
    exts = {f.rsplit(".", 1)[-1] for f in job["output_files"]}
    assert exts == {"wav", "mp3"}
    mp3 = next(f for f in job["output_files"] if f.endswith(".mp3"))
    assert (workspace.root / mp3).stat().st_size > 1000


def test_export_respects_mute_solo_volume(client, workspace):
    p = build_mixable_project(client, workspace)
    # mute everything except nothing -> all muted = no stems in mix
    for t in p["tracks"]:
        t["mute"] = True
    client.put(f"/api/projects/{p['id']}", json=p)
    job = client.post(f"/api/projects/{p['id']}/export/mix",
                      json={"formats": ["wav"]}).json()
    assert job["status"] == "failed"
    assert any("no stems" in e for e in job["errors"])

    # unmute, then compare full volume vs low volume mix loudness
    p = client.get(f"/api/projects/{p['id']}").json()
    for t in p["tracks"]:
        t["mute"] = False
        t["volume"] = 1.0
    p["mix_settings"]["normalize"] = False
    client.put(f"/api/projects/{p['id']}", json=p)
    job1 = client.post(f"/api/projects/{p['id']}/export/mix",
                       json={"formats": ["wav"]}).json()
    d1, _ = sf.read(str(workspace.root / job1["output_files"][0]))

    p = client.get(f"/api/projects/{p['id']}").json()
    for t in p["tracks"]:
        t["volume"] = 0.1
    client.put(f"/api/projects/{p['id']}", json=p)
    job2 = client.post(f"/api/projects/{p['id']}/export/mix",
                       json={"formats": ["wav"]}).json()
    d2, _ = sf.read(str(workspace.root / job2["output_files"][0]))
    assert np.abs(d2).max() < np.abs(d1).max() * 0.3

    # solo: only the pad plays
    p = client.get(f"/api/projects/{p['id']}").json()
    pad = next(t for t in p["tracks"] if t["name"] == "Pad")
    pad["solo"] = True
    client.put(f"/api/projects/{p['id']}", json=p)
    job3 = client.post(f"/api/projects/{p['id']}/export/mix",
                       json={"formats": ["wav"]}).json()
    assert job3["status"] == "completed"
    assert any("excluded" in w for w in job3["warnings"])

    # previous exports were not overwritten
    files = {f for j in (job1, job2, job3) for f in j["output_files"]}
    assert len(files) == 3


def test_package_export(client, workspace):
    p = build_mixable_project(client, workspace)
    client.post(f"/api/projects/{p['id']}/export/mix", json={"formats": ["wav"]})
    client.post(f"/api/projects/{p['id']}/midi/export")

    r = client.post(f"/api/projects/{p['id']}/export/package")
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "completed", job["errors"]
    zip_rel = job["output_files"][0]
    zip_path = workspace.root / zip_rel
    assert zip_path.exists()

    import zipfile
    names = zipfile.ZipFile(zip_path).namelist()
    assert "project.json" in names
    assert "lyrics.txt" in names
    assert "lyrics_alignment.json" in names
    assert any(n.startswith("stems/") for n in names)
    assert any(n.startswith("mix/") and n.endswith(".wav") for n in names)
    assert any(n.startswith("midi/") for n in names)
