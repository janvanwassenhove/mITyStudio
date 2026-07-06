"""Phase 7: score import (MIDI fixture built with mido)."""
from __future__ import annotations

import mido


def make_midi(path, bpm=100, notes=((60, 0, 480), (64, 480, 480), (67, 960, 960))):
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Piano", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    track.append(mido.Message("program_change", program=0, channel=0, time=0))
    last = 0
    events = []
    for note, start, dur in notes:
        events.append((start, "on", note))
        events.append((start + dur, "off", note))
    events.sort()
    for t, kind, note in events:
        msg = mido.Message("note_on" if kind == "on" else "note_off",
                           note=note, velocity=90 if kind == "on" else 0,
                           channel=0, time=t - last)
        track.append(msg)
        last = t
    mid.save(str(path))


def test_midi_import(client, workspace):
    make_midi(workspace.scores_dir / "tune.mid", bpm=100)
    client.post("/api/assets/rescan")
    score = client.get("/api/assets/scores").json()[0]

    r = client.post(f"/api/scores/{score['id']}/import", json={})
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["supported"] is True
    assert result["detected_tempo"] == 100.0
    assert result["time_signature"] == "4/4"
    assert len(result["detected_tracks"]) == 1
    t = result["detected_tracks"][0]
    assert t["name"] == "Piano"
    assert t["note_count"] == 3
    assert t["notes"][0]["midi_note"] == 60
    assert t["notes"][2]["duration_beats"] == 2.0


def test_midi_import_creates_project(client, workspace):
    make_midi(workspace.scores_dir / "tune.mid", bpm=140)
    client.post("/api/assets/rescan")
    score = client.get("/api/assets/scores").json()[0]

    r = client.post(f"/api/scores/{score['id']}/import",
                    json={"create_project": True, "title": "Imported Tune"})
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    project = client.get(f"/api/projects/{pid}").json()
    assert project["title"] == "Imported Tune"
    assert project["bpm"] == 140.0
    assert len(project["tracks"]) == 1
    assert len(project["tracks"][0]["clips"][0]["note_events"]) == 3
    assert project["source_assets"] == [score["id"]]

    m = client.get(f"/api/projects/{pid}/playback-manifest").json()
    assert len(m["midi_note_metadata"]) == 3


def test_unsupported_formats_get_placeholder(client, workspace):
    (workspace.scores_dir / "song.gp5").write_bytes(b"gp5-dummy")
    (workspace.scores_dir / "sheet.pdf").write_bytes(b"%PDF-1.4 dummy")
    client.post("/api/assets/rescan")
    for score in client.get("/api/assets/scores").json():
        r = client.post(f"/api/scores/{score['id']}/import", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["supported"] is False
        assert body["warnings"]
        # creating a project from unsupported score fails clearly
        r2 = client.post(f"/api/scores/{score['id']}/import",
                         json={"create_project": True})
        assert r2.status_code == 422
