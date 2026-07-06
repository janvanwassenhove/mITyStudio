"""Phase 24: end-to-end workflow — scan → chat-create song → place sample →
render all stems → manifest with karaoke timing → export WAV (+MP3) → package.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tests.test_sample_analysis import write_tone

REPO_SOUNDFONTS = Path(__file__).resolve().parents[3] / "soundfonts"


def _sf2() -> Path | None:
    if not REPO_SOUNDFONTS.exists():
        return None
    c = sorted(list(REPO_SOUNDFONTS.glob("*.sf2")) + list(REPO_SOUNDFONTS.glob("*.SF2")),
               key=lambda p: p.stat().st_size)
    return c[0] if c else None


needs_renderer = pytest.mark.skipif(
    shutil.which("fluidsynth") is None or _sf2() is None,
    reason="needs fluidsynth + a .sf2 in soundfonts/")


@needs_renderer
def test_full_workflow(client, workspace):
    # 1. assets: soundfont + sample
    shutil.copy2(_sf2(), workspace.soundfonts_dir / "test.sf2")
    write_tone(workspace.samples_dir / "riser - 120 BPM.wav", seconds=1.5,
               freq=500, rate=44100)
    stats = client.post("/api/assets/rescan").json()
    assert stats["new"] == 2
    sample = client.get("/api/assets/samples").json()[0]
    client.post(f"/api/assets/{sample['id']}/analyse")

    # 2. create project via chat
    p = client.post("/api/projects", json={"title": "E2E Song"}).json()
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "create a rock song at 120 bpm in A minor"})
    assert any(o["applied"] for o in r.json()["operations"])
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "add lyrics about freedom"})
    assert any(o["applied"] for o in r.json()["operations"])

    # 3. add the sample on a sample track (structured op path)
    from app.models.operations import ChatOperation
    from app.services import operation_applier, project_repo
    project = project_repo.load_project(p["id"])
    results = operation_applier.apply_operations(project, [
        ChatOperation(op_type="select_sample",
                      params={"sample_asset_id": sample["id"],
                              "section": "Intro", "loop": True})])
    assert results[0].applied, results[0].error
    project_repo.save_project(project)

    # 4. render everything
    assert client.post(f"/api/projects/{p['id']}/midi/export").json()["count"] > 3
    inst = client.post(f"/api/projects/{p['id']}/render/instrument-stems").json()
    assert inst["rendered"] and not inst["errors"]
    samp = client.post(f"/api/projects/{p['id']}/render/sample-stems").json()
    assert samp["rendered"]
    voc = client.post(f"/api/projects/{p['id']}/vocals/render").json()
    assert voc["rendered"]

    # 5. manifest: everything on one timeline with karaoke timing
    m = client.get(f"/api/projects/{p['id']}/playback-manifest").json()
    stem_types = {s["stem_type"] for s in m["stems"]}
    assert stem_types == {"instrument", "sample", "vocal"}
    assert m["lyrics_alignment"]
    assert m["waveform_metadata"]
    assert m["midi_note_metadata"]
    assert m["duration_seconds"] > 30

    # 6. export combined mix
    formats = ["wav", "mp3"] if shutil.which("ffmpeg") else ["wav"]
    job = client.post(f"/api/projects/{p['id']}/export/mix",
                      json={"formats": formats}).json()
    assert job["status"] == "completed", job["errors"]
    wav_file = next(f for f in job["output_files"] if f.endswith(".wav"))
    data, rate = sf.read(str(workspace.root / wav_file))
    assert len(data) / rate == pytest.approx(m["duration_seconds"], abs=0.5)
    assert np.abs(data).max() > 0.05
    if "mp3" in formats:
        assert any(f.endswith(".mp3") for f in job["output_files"])

    # 7. package
    pkg = client.post(f"/api/projects/{p['id']}/export/package").json()
    assert pkg["status"] == "completed"
    assert pkg["output_files"][0].endswith(".zip")
