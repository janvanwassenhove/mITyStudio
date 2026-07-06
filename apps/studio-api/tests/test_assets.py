"""Asset scanner + registry tests: discovery, change detection, missing files,
metadata preservation, original-file immutability."""
from __future__ import annotations

import struct
import wave
from pathlib import Path


def make_wav(path: Path, seconds: float = 0.1, freq: float = 440.0,
             rate: int = 22050) -> None:
    import math
    n = int(seconds * rate)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(20000 * math.sin(2 * math.pi * freq * i / rate)))
            for i in range(n))
        w.writeframes(frames)


def test_scan_discovers_assets(client, workspace):
    make_wav(workspace.samples_dir / "kick.wav")
    (workspace.soundfonts_dir / "piano.sf2").write_bytes(b"RIFF-sf2-dummy")
    (workspace.scores_dir / "song.mid").write_bytes(b"MThd\x00\x00\x00\x06")

    stats = client.post("/api/assets/rescan").json()
    assert stats["new"] == 3

    samples = client.get("/api/assets/samples").json()
    assert len(samples) == 1
    assert samples[0]["filename"] == "kick.wav"
    assert client.get("/api/assets/soundfonts").json()[0]["extension"] == ".sf2"
    assert client.get("/api/assets/scores").json()[0]["filename"] == "song.mid"


def test_rescan_detects_changes_and_missing(client, workspace):
    f = workspace.samples_dir / "loop.wav"
    make_wav(f, freq=440)
    client.post("/api/assets/rescan")
    asset = client.get("/api/assets/samples").json()[0]
    old_hash = asset["content_hash"]

    # unchanged rescan
    stats = client.post("/api/assets/rescan").json()
    assert stats["unchanged"] == 1 and stats["new"] == 0

    # changed content
    make_wav(f, freq=880, seconds=0.2)
    stats = client.post("/api/assets/rescan").json()
    assert stats["changed"] == 1
    asset2 = client.get("/api/assets/samples").json()[0]
    assert asset2["content_hash"] != old_hash
    assert asset2["id"] == asset["id"]  # identity preserved

    # missing file: metadata kept, flagged
    f.unlink()
    stats = client.post("/api/assets/rescan").json()
    assert stats["missing"] == 1
    asset3 = client.get("/api/assets/samples").json()[0]
    assert asset3["is_missing"] is True

    # file comes back
    make_wav(f, freq=880, seconds=0.2)
    client.post("/api/assets/rescan")
    assert client.get("/api/assets/samples").json()[0]["is_missing"] is False


def test_user_metadata_survives_rescan(client, workspace):
    f = workspace.samples_dir / "snare.wav"
    make_wav(f)
    client.post("/api/assets/rescan")
    asset = client.get("/api/assets/samples").json()[0]

    r = client.patch(f"/api/assets/{asset['id']}/metadata",
                     json={"tags": ["drums", "snare"],
                           "user_description": "my favourite snare"})
    assert r.status_code == 200

    make_wav(f, freq=660)  # change the file, then rescan
    client.post("/api/assets/rescan")
    after = client.get(f"/api/assets/{asset['id']}").json()
    assert after["tags"] == ["drums", "snare"]
    assert after["user_description"] == "my favourite snare"
    assert after["analysis_status"] == "pending"


def test_scan_never_modifies_originals(client, workspace):
    f = workspace.samples_dir / "orig.wav"
    make_wav(f)
    before = f.read_bytes()
    mtime = f.stat().st_mtime_ns
    client.post("/api/assets/rescan")
    client.post("/api/assets/rescan")
    assert f.read_bytes() == before
    assert f.stat().st_mtime_ns == mtime


def test_serve_file(client, workspace):
    make_wav(workspace.samples_dir / "hat.wav")
    client.post("/api/assets/rescan")
    asset = client.get("/api/assets/samples").json()[0]
    r = client.get(f"/api/assets/{asset['id']}/file")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/")
