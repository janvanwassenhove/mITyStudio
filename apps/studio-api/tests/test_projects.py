"""Phase 3: SongProject create/load/save/validate."""
from __future__ import annotations


def make_project(client, **overrides) -> dict:
    body = {"title": "Test Song", "bpm": 120, "key": "C major",
            "time_signature": "4/4", **overrides}
    r = client.post("/api/projects", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_load_project(client):
    p = make_project(client, title="My Song", style="punk")
    assert p["title"] == "My Song"
    got = client.get(f"/api/projects/{p['id']}").json()
    assert got["id"] == p["id"]
    assert got["style"] == "punk"

    listed = client.get("/api/projects").json()
    assert len(listed) == 1
    assert listed[0]["title"] == "My Song"


def test_update_project_with_structure(client):
    p = make_project(client)
    p["sections"] = [
        {"name": "Verse", "start_bar": 0, "length_bars": 8},
        {"name": "Chorus", "start_bar": 8, "length_bars": 8},
    ]
    p["tracks"] = [{
        "name": "Bass", "track_type": "bass",
        "clips": [{
            "clip_type": "midi", "start_beat": 0, "duration_beats": 16,
            "note_events": [
                {"midi_note": 40, "start_beat": 0, "duration_beats": 1},
                {"midi_note": 43, "start_beat": 4, "duration_beats": 1},
            ],
        }],
    }]
    r = client.put(f"/api/projects/{p['id']}", json=p)
    assert r.status_code == 200, r.text
    got = r.json()
    assert len(got["sections"]) == 2
    assert got["tracks"][0]["clips"][0]["note_events"][0]["pitch"] == "E2"

    v = client.post(f"/api/projects/{p['id']}/validate").json()
    assert v["valid"] is True


def test_invalid_project_rejected(client):
    p = make_project(client)
    # overlapping sections
    p["sections"] = [
        {"name": "A", "start_bar": 0, "length_bars": 8},
        {"name": "B", "start_bar": 4, "length_bars": 8},
    ]
    r = client.put(f"/api/projects/{p['id']}", json=p)
    assert r.status_code == 422
    assert "overlap" in str(r.json()["detail"])

    # bad midi note
    p2 = make_project(client)
    p2["tracks"] = [{"name": "X", "track_type": "keys", "clips": [{
        "clip_type": "midi", "start_beat": 0, "duration_beats": 4,
        "note_events": [{"midi_note": 200, "start_beat": 0, "duration_beats": 1}]}]}]
    assert client.put(f"/api/projects/{p2['id']}", json=p2).status_code == 422

    # bad time signature
    assert client.post("/api/projects", json={
        "title": "x", "time_signature": "waltz"}).status_code == 422


def test_track_referencing_unknown_asset_rejected(client):
    p = make_project(client)
    p["tracks"] = [{"name": "Piano", "track_type": "keys",
                    "instrument_config": {"soundfont_asset_id": "nope"}}]
    r = client.put(f"/api/projects/{p['id']}", json=p)
    assert r.status_code == 422
    assert "not found" in str(r.json()["detail"])


def test_unknown_project_404(client):
    assert client.get("/api/projects/missing").status_code == 404
    assert client.put("/api/projects/missing", json={"title": "x"}).status_code == 404
