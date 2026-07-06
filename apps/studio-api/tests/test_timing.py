"""Phase 4: timing service + PlaybackManifest."""
from __future__ import annotations

import pytest

from tests.test_projects import make_project


def test_beats_to_seconds_conversion(workspace):
    from app.models.song import SongProject
    from app.services import timing

    p = SongProject(title="t", bpm=120)
    assert timing.beats_to_seconds(p, 4) == pytest.approx(2.0)
    assert timing.seconds_to_beats(p, 2.0) == pytest.approx(4.0)
    assert timing.bars_to_beats(p, 2) == pytest.approx(8.0)

    p34 = SongProject(title="t", bpm=90, time_signature="3/4")
    assert timing.bars_to_beats(p34, 4) == pytest.approx(12.0)
    assert timing.beats_to_seconds(p34, 3) == pytest.approx(2.0)


def test_manifest_full_timing(client):
    p = make_project(client, bpm=120)
    p["sections"] = [
        {"name": "Intro", "start_bar": 0, "length_bars": 4},
        {"name": "Verse", "start_bar": 4, "length_bars": 8},
    ]
    p["tracks"] = [{
        "name": "Keys", "track_type": "keys",
        "clips": [{
            "clip_type": "midi", "start_beat": 16, "duration_beats": 8,
            "note_events": [
                {"midi_note": 60, "start_beat": 0, "duration_beats": 2},
                {"midi_note": 64, "start_beat": 2, "duration_beats": 2},
            ]}]}]
    client.put(f"/api/projects/{p['id']}", json=p)

    m = client.get(f"/api/projects/{p['id']}/playback-manifest").json()
    assert m["bpm"] == 120
    assert m["total_bars"] == 12
    assert m["duration_seconds"] == pytest.approx(24.0)  # 48 beats @ 120

    verse = m["sections"][1]
    assert verse["start_beat"] == 16
    assert verse["start_seconds"] == pytest.approx(8.0)
    assert verse["end_seconds"] == pytest.approx(24.0)

    clip = m["clips"][0]
    assert clip["start_seconds"] == pytest.approx(8.0)
    assert clip["end_seconds"] == pytest.approx(12.0)

    notes = m["midi_note_metadata"]
    assert notes[0]["start_seconds"] == pytest.approx(8.0)
    assert notes[1]["start_seconds"] == pytest.approx(9.0)
    assert notes[1]["pitch"] == "E4"

    assert m["markers"][1]["label"] == "Verse"


def test_manifest_empty_project(client):
    p = make_project(client)
    m = client.get(f"/api/projects/{p['id']}/playback-manifest").json()
    assert m["total_bars"] == 0
    assert m["duration_seconds"] == 0
    assert m["sections"] == []
    assert m["clips"] == []
    assert m["lyrics_alignment"] == []
