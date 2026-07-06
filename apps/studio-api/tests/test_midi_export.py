"""Phase 11: MIDI generation from SongProject."""
from __future__ import annotations

import mido

from tests.test_projects import make_project


def build_song(client):
    p = make_project(client, bpm=140)
    p["sections"] = [{"name": "Verse", "start_bar": 0, "length_bars": 4}]
    p["tracks"] = [
        {"name": "Keys", "track_type": "keys",
         "clips": [{"clip_type": "midi", "start_beat": 0, "duration_beats": 16,
                    "note_events": [
                        {"midi_note": 60, "start_beat": 0, "duration_beats": 2, "velocity": 100},
                        {"midi_note": 64, "start_beat": 2, "duration_beats": 2, "velocity": 90},
                    ]}]},
        {"name": "Drums", "track_type": "drums",
         "instrument_config": {"is_drum_kit": True},
         "clips": [{"clip_type": "midi", "start_beat": 0, "duration_beats": 16,
                    "note_events": [
                        {"midi_note": 36, "start_beat": 0, "duration_beats": 0.25, "velocity": 110},
                        {"midi_note": 38, "start_beat": 1, "duration_beats": 0.25, "velocity": 110},
                    ]}]},
    ]
    r = client.put(f"/api/projects/{p['id']}", json=p)
    assert r.status_code == 200, r.text
    return r.json()


def test_midi_export(client, workspace):
    p = build_song(client)
    r = client.post(f"/api/projects/{p['id']}/midi/export")
    assert r.status_code == 200, r.text
    files = r.json()["midi_files"]
    assert len(files) == 3  # 2 tracks + full song

    keys_track = next(t for t in p["tracks"] if t["name"] == "Keys")
    midi_path = workspace.root / files[keys_track["id"]]
    assert midi_path.exists()

    mid = mido.MidiFile(str(midi_path))
    assert round(mido.tempo2bpm(next(
        m.tempo for t in mid.tracks for m in t if m.type == "set_tempo"))) == 140
    notes = [m for t in mid.tracks for m in t if m.type == "note_on" and m.velocity > 0]
    assert len(notes) == 2
    assert notes[0].note == 60
    # duration: 2 beats at 480 tpb = 960 ticks
    offs = [m for t in mid.tracks for m in t if m.type == "note_off"]
    assert offs[0].time == 960

    # drum track on channel 9
    drums_track = next(t for t in p["tracks"] if t["name"] == "Drums")
    dmid = mido.MidiFile(str(workspace.root / files[drums_track["id"]]))
    dnotes = [m for t in dmid.tracks for m in t if m.type == "note_on" and m.velocity > 0]
    assert all(m.channel == 9 for m in dnotes)

    # project references outputs
    proj = client.get(f"/api/projects/{p['id']}").json()
    assert len(proj["midi_files"]) == 3


def test_midi_export_empty_project(client):
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/midi/export")
    assert r.status_code == 200
    assert r.json()["count"] == 0
