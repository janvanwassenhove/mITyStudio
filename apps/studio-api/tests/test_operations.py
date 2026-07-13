"""Phases 9-10: LLM settings, mock provider, chat operations."""
from __future__ import annotations

from tests.test_projects import make_project
from tests.test_sample_analysis import write_tone


def test_llm_settings_roundtrip(client):
    s = client.get("/api/settings/llm").json()
    assert s["provider"] == "mock"
    assert set(s["providers"]) == {"mock", "anthropic", "openai", "custom"}
    assert set(s["api_keys_set"]) == {"anthropic", "openai", "custom"}

    r = client.put("/api/settings/llm", json={
        "provider": "mock", "model": "test-model", "temperature": 0.7,
        "max_tokens": 2048})
    assert r.status_code == 200
    assert r.json()["model"] == "test-model"
    # api key never returned
    assert "api_key" not in r.json()

    t = client.post("/api/settings/llm/test").json()
    assert t["ok"] is True

    # unknown provider rejected
    assert client.put("/api/settings/llm",
                      json={"provider": "skynet"}).status_code == 422


def test_per_provider_key_storage(client, workspace, monkeypatch):
    for env in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MITY_LLM_API_KEY"):
        monkeypatch.delenv(env, raising=False)

    r = client.put("/api/settings/llm", json={
        "provider": "openai", "model": "gpt-5.2", "api_key": "sk-test-openai"})
    body = r.json()
    assert body["api_keys_set"]["openai"] is True
    assert body["api_keys_set"]["anthropic"] is False
    assert "sk-test" not in str(body)  # key never echoed

    # key file lives in the isolated workspace root, not in the repo
    secrets_file = workspace.root / "local_settings.json"
    assert secrets_file.exists()
    assert "sk-test-openai" in secrets_file.read_text()

    # switching provider keeps the openai key stored
    r = client.put("/api/settings/llm", json={
        "provider": "anthropic", "model": "claude-sonnet-5",
        "api_key": "sk-ant-test"})
    keys = r.json()["api_keys_set"]
    assert keys["openai"] is True and keys["anthropic"] is True

    # empty string clears a key
    r = client.put("/api/settings/llm", json={
        "provider": "openai", "model": "gpt-5.2", "api_key": ""})
    assert r.json()["api_keys_set"]["openai"] is False
    assert r.json()["api_keys_set"]["anthropic"] is True


def test_chat_creates_full_song(client):
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "Create a punk song called 'Street Lights' at 170 bpm"})
    assert r.status_code == 200, r.text
    body = r.json()
    applied = [o for o in body["operations"] if o["applied"]]
    assert len(applied) > 10
    project = body["project"]
    assert project["title"] == "Street Lights"
    assert project["style"] == "punk"
    assert project["bpm"] == 170
    assert len(project["sections"]) == 6
    track_types = {t["track_type"] for t in project["tracks"]}
    assert {"drums", "bass"} <= track_types
    # generated notes exist
    total_notes = sum(len(c["note_events"]) for t in project["tracks"]
                      for c in t["clips"])
    assert total_notes > 100

    # manifest reflects the content
    m = client.get(f"/api/projects/{p['id']}/playback-manifest").json()
    assert m["duration_seconds"] > 30
    assert len(m["midi_note_metadata"]) == total_notes


def test_chat_edits(client):
    p = make_project(client)
    client.post(f"/api/projects/{p['id']}/chat",
                json={"message": "create a pop song"})
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "change tempo to 95 bpm"})
    assert r.json()["project"]["bpm"] == 95

    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "add lyrics about the ocean"})
    project = r.json()["project"]
    # full-song creation already wrote chorus lyrics; the new lines add to them
    assert len(project["lyrics"]["lines"]) >= 4
    assert any("ocean" in l["text"] for l in project["lyrics"]["lines"])
    assert any(t["track_type"] == "lead_vocal" for t in project["tracks"])


def test_write_notes_operation(client, workspace):
    """The LLM can compose parts note-by-note; junk notes are dropped and a
    fully-invalid list is rejected."""
    from app.models.operations import ChatOperation
    from app.models.song import Section, SongProject
    from app.services import operation_applier

    project = SongProject(title="t", bpm=120, key="C major")
    project.sections = [Section(name="Verse", start_bar=0, length_bars=2)]

    results = operation_applier.apply_operations(project, [
        ChatOperation(op_type="write_notes", params={
            "section": "Verse", "track": "AI Drums", "track_type": "drums",
            "notes": [
                {"midi_note": 36, "start_beat": 0, "duration_beats": 0.5,
                 "velocity": 110},
                {"midi_note": 38, "start_beat": 4, "duration_beats": 0.5},
                {"midi_note": 42, "start_beat": 999, "duration_beats": 0.5},
                {"midi_note": 300, "start_beat": 1, "duration_beats": 0.5},
                {"midi_note": 46, "start_beat": 7.5,
                 "duration_beats": 4.0},          # clamped to section end
            ]})])
    assert results[0].applied, results[0].error
    track = next(t for t in project.tracks if t.name == "AI Drums")
    notes = track.clips[0].note_events
    assert len(notes) == 3                # 2 junk notes dropped
    assert notes[-1].start_beat + notes[-1].duration_beats <= 8.0001

    # all-invalid notes → clean rejection, nothing added
    r2 = operation_applier.apply_operations(project, [
        ChatOperation(op_type="write_notes", params={
            "section": "Verse", "track": "AI Drums",
            "notes": [{"midi_note": 999, "start_beat": 0,
                       "duration_beats": 1}]})])
    assert not r2[0].applied


def test_invalid_operations_rejected(client, workspace):
    from app.models.operations import ChatOperation
    from app.models.song import SongProject
    from app.services import operation_applier

    project = SongProject(title="t")
    results = operation_applier.apply_operations(project, [
        ChatOperation(op_type="assign_soundfont",
                      params={"track": "nope", "soundfont_asset_id": "fake"}),
        ChatOperation(op_type="select_sample",
                      params={"sample_asset_id": "invented-by-llm"}),
        ChatOperation(op_type="change_tempo", params={"bpm": 9000}),
        ChatOperation(op_type="generate_drums", params={}),  # no sections
    ])
    assert all(not r.applied for r in results)
    assert "does not exist" in results[1].error
    assert "out of range" in results[2].error
    # project untouched
    assert project.tracks == [] and project.bpm == 120


def test_update_track_operation(client, workspace):
    from app.models.operations import ChatOperation
    from app.models.song import SongProject, Track
    from app.services import operation_applier

    project = SongProject(title="t", tracks=[Track(name="Melody", track_type="synth")])
    results = operation_applier.apply_operations(project, [
        ChatOperation(op_type="update_track",
                      params={"track": "Melody", "name": "Synth Hook",
                              "volume": 0.7, "pan": -0.25, "mute": False}),
        ChatOperation(op_type="update_track", params={"track": "nope", "name": "x"}),
        ChatOperation(op_type="update_track", params={"track": "Synth Hook"}),
    ])
    assert results[0].applied
    t = project.tracks[0]
    assert (t.name, t.volume, t.pan) == ("Synth Hook", 0.7, -0.25)
    assert not results[1].applied and "not found" in results[1].error
    assert not results[2].applied and "at least one" in results[2].error


def test_clip_operations_via_chat_ops(client, workspace):
    """split/duplicate/delete clips are chat-reachable (toolbar parity)."""
    from app.models.operations import ChatOperation
    from app.models.song import Clip, NoteEvent, SongProject, Track
    from app.services import operation_applier

    project = SongProject(title="t", bpm=120)
    clip = Clip(clip_type="midi", start_beat=0, duration_beats=16,
                note_events=[
                    NoteEvent(midi_note=60, start_beat=1, duration_beats=1),
                    NoteEvent(midi_note=64, start_beat=9, duration_beats=1)])
    project.tracks = [Track(name="Keys", track_type="keys", clips=[clip])]

    # split at bar 3 (beat 8): notes divide across the two halves
    r = operation_applier.apply_operations(project, [
        ChatOperation(op_type="split_clip", params={"track": "Keys", "at_bar": 3})])
    assert r[0].applied, r[0].error
    keys = project.tracks[0]
    assert len(keys.clips) == 2
    assert keys.clips[0].duration_beats == 8
    assert keys.clips[1].start_beat == 8
    assert [n.midi_note for n in keys.clips[0].note_events] == [60]
    assert [n.midi_note for n in keys.clips[1].note_events] == [64]
    assert keys.clips[1].note_events[0].start_beat == 1  # rebased

    # duplicate the clip at bar 1 → copy directly after it
    r = operation_applier.apply_operations(project, [
        ChatOperation(op_type="duplicate_clip", params={"track": "Keys", "at_bar": 1})])
    assert r[0].applied, r[0].error
    assert len(keys.clips) == 3
    assert keys.clips[1].start_beat == 8  # the copy

    # delete the last clip (no at_bar = last)
    r = operation_applier.apply_operations(project, [
        ChatOperation(op_type="delete_clip", params={"track": "Keys"})])
    assert r[0].applied
    assert len(keys.clips) == 2

    # errors are clear
    r = operation_applier.apply_operations(project, [
        ChatOperation(op_type="split_clip", params={"track": "Keys", "at_bar": 99})])
    assert not r[0].applied and "no clip" in r[0].error


def test_failed_op_rolls_back_but_others_apply(client):
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "add a chorus"})
    body = r.json()
    assert any(o["applied"] for o in body["operations"])
    assert len(body["project"]["sections"]) == 1
