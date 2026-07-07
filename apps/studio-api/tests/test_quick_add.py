"""GarageBand-style flows: quick-add tracks, auto-render, chat voice."""
from __future__ import annotations

from tests.test_projects import make_project
from tests.test_voice_and_vocals import upload_recording


def test_quick_add_instrument_generates_part(client):
    p = make_project(client, title="Fresh")
    r = client.post(f"/api/projects/{p['id']}/tracks/quick-add",
                    json={"track_type": "guitar"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["errors"] == []
    proj = body["project"]
    # empty project got a starter structure + a playing guitar part
    assert len(proj["sections"]) == 2
    guitar = next(t for t in proj["tracks"] if t["track_type"] == "guitar")
    assert len(guitar["clips"]) == 2  # one per section
    assert sum(len(c["note_events"]) for c in guitar["clips"]) > 10

    # second instrument reuses existing sections
    r2 = client.post(f"/api/projects/{p['id']}/tracks/quick-add",
                     json={"track_type": "drums"}).json()
    assert len(r2["project"]["sections"]) == 2
    drums = next(t for t in r2["project"]["tracks"] if t["track_type"] == "drums")
    assert sum(len(c["note_events"]) for c in drums["clips"]) > 20


def test_quick_add_empty_track(client):
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/tracks/quick-add",
                    json={"track_type": "sample", "generate": False}).json()
    track = r["project"]["tracks"][0]
    assert track["track_type"] == "sample"
    assert track["clips"] == []


def test_quick_add_vocals_with_profile_and_lyrics(client):
    rec = upload_recording(client)
    profile = client.post("/api/voice/profiles", json={
        "name": "Me", "source_recording_ids": [rec["id"]],
        "consent_confirmed": True}).json()

    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/tracks/quick-add",
                    json={"track_type": "lead_vocal",
                          "voice_profile_id": profile["id"],
                          "lyrics": ["Hello world", "Singing my song"]}).json()
    assert r["errors"] == []
    proj = r["project"]
    vocal = next(t for t in proj["tracks"] if t["track_type"] == "lead_vocal")
    assert vocal["voice_profile_id"] == profile["id"]
    assert [l["text"] for l in proj["lyrics"]["lines"]] == \
        ["Hello world", "Singing my song"]
    # melody with syllables exists
    notes = [n for c in vocal["clips"] for n in c["note_events"]]
    assert notes and any(n["lyric_syllable"] for n in notes)

    # invalid profile rejected
    p2 = make_project(client)
    r2 = client.post(f"/api/projects/{p2['id']}/tracks/quick-add",
                     json={"track_type": "lead_vocal",
                           "voice_profile_id": "invented"}).json()
    assert r2["errors"]


def test_quick_add_vocal_sings_existing_lyric_sections(client):
    """A new AI voice track gets clips exactly where the lyrics are — and a
    section subset supports duets."""
    p = make_project(client)
    proj = client.get(f"/api/projects/{p['id']}").json()
    proj["sections"] = [{"name": "Verse", "start_bar": 0, "length_bars": 4},
                        {"name": "Chorus", "start_bar": 4, "length_bars": 4},
                        {"name": "Outro", "start_bar": 8, "length_bars": 4}]
    client.put(f"/api/projects/{p['id']}", json=proj)
    proj = client.get(f"/api/projects/{p['id']}").json()
    for s in proj["sections"][:2]:  # lyrics on Verse + Chorus only
        proj["lyrics"]["lines"].append(
            {"section_id": s["id"], "text": f"singing in the {s['name']}"})
    client.put(f"/api/projects/{p['id']}", json=proj)

    # full vocal: clips land on BOTH lyric sections (not the outro)
    r = client.post(f"/api/projects/{p['id']}/tracks/quick-add",
                    json={"track_type": "lead_vocal"}).json()
    assert r["errors"] == []
    vocal = next(t for t in r["project"]["tracks"]
                 if t["track_type"] == "lead_vocal")
    lyric_ids = {l["section_id"] for l in r["project"]["lyrics"]["lines"]}
    assert {c["section_id"] for c in vocal["clips"]} == lyric_ids
    assert len(vocal["clips"]) == 2

    # duet: a second voice singing ONLY the chorus
    chorus_id = next(s["id"] for s in r["project"]["sections"]
                     if s["name"] == "Chorus")
    r2 = client.post(f"/api/projects/{p['id']}/tracks/quick-add",
                     json={"track_type": "backing_vocal",
                           "sections": [chorus_id]}).json()
    assert r2["errors"] == []
    backing = next(t for t in r2["project"]["tracks"]
                   if t["track_type"] == "backing_vocal")
    assert [c["section_id"] for c in backing["clips"]] == [chorus_id]


def test_auto_render_endpoint(client, workspace):
    from tests.test_sample_analysis import write_tone
    write_tone(workspace.samples_dir / "loop.wav", seconds=1.0, rate=44100)
    client.post("/api/assets/rescan")
    sample = client.get("/api/assets/samples").json()[0]

    p = make_project(client)
    p["sections"] = [{"name": "A", "start_bar": 0, "length_bars": 2}]
    p["tracks"] = [{"name": "S", "track_type": "sample",
                    "clips": [{"clip_type": "sample", "start_beat": 0,
                               "duration_beats": 4,
                               "source_asset_id": sample["id"]}]}]
    client.put(f"/api/projects/{p['id']}", json=p)

    r = client.post(f"/api/projects/{p['id']}/render/auto").json()
    assert r["changed"] is True
    assert r["stems"] == 1
    # second call: everything fresh, nothing re-rendered
    r2 = client.post(f"/api/projects/{p['id']}/render/auto").json()
    assert r2["changed"] is False


def test_chat_adds_voice(client, workspace):
    rec = upload_recording(client)
    profile = client.post("/api/voice/profiles", json={
        "name": "Me", "source_recording_ids": [rec["id"]],
        "consent_confirmed": True}).json()

    p = make_project(client)
    client.post(f"/api/projects/{p['id']}/chat",
                json={"message": "create a pop song"})
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "add vocals with my voice about the sea"})
    body = r.json()
    applied = [o for o in body["operations"] if o["applied"]]
    assert applied, body["operations"]
    proj = body["project"]
    vocals = [t for t in proj["tracks"] if t["track_type"] == "lead_vocal"]
    assert vocals
    assert any(t["voice_profile_id"] == profile["id"] for t in vocals)
    assert proj["lyrics"]["lines"]


def test_chat_full_song_includes_vocals(client):
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "create a rock song"})
    proj = r.json()["project"]
    assert any(t["track_type"] == "lead_vocal" for t in proj["tracks"])
    assert proj["lyrics"]["lines"]
    vocal = next(t for t in proj["tracks"] if t["track_type"] == "lead_vocal")
    assert any(c["note_events"] for c in vocal["clips"])