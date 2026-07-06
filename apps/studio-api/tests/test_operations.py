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


def test_failed_op_rolls_back_but_others_apply(client):
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "add a chorus"})
    body = r.json()
    assert any(o["applied"] for o in body["operations"])
    assert len(body["project"]["sections"]) == 1
