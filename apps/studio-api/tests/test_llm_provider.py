"""Phase 22: real LLM provider path — mocked responses, strict validation.

The Anthropic adapter is exercised with a monkeypatched provider so no API
key or network is needed; what matters is that provider output goes through
the same validation as the mock planner and cannot invent assets.
"""
from __future__ import annotations

import pytest

from tests.test_projects import make_project


def test_extract_json_variants():
    from app.services.llm.provider import LlmProviderError, _extract_json

    ok = _extract_json('Here you go:\n```json\n{"reply": "hi", "operations": []}\n```')
    assert ok["reply"] == "hi"

    ok2 = _extract_json('{"reply": "x", "operations": [{"op_type": "change_key"}]}')
    assert len(ok2["operations"]) == 1

    with pytest.raises(LlmProviderError):
        _extract_json("no json here at all")
    with pytest.raises(LlmProviderError):
        _extract_json('{"reply": "bad", "operations": "not-a-list"}')


def test_llm_output_validated_and_assets_checked(client, monkeypatch):
    """A 'real' provider returning invented asset ids must be rejected."""
    from app.services.llm import provider as provider_mod

    class FakeRealProvider:
        def plan(self, system_prompt, user_message):
            # provider tries to use assets that do not exist
            return {"reply": "using a great soundfont",
                    "operations": [
                        {"op_type": "add_track",
                         "params": {"name": "Piano", "track_type": "keys",
                                    "soundfont_asset_id": "hallucinated-id"}},
                        {"op_type": "add_section",
                         "params": {"name": "Verse", "length_bars": 8}},
                        {"op_type": "unknown_evil_op", "params": {}},
                    ]}

        def test_connection(self):
            return True, "fake"

    monkeypatch.setattr(provider_mod, "get_provider",
                        lambda s: FakeRealProvider())
    import app.services.operation_planner as planner_mod
    monkeypatch.setattr(planner_mod, "get_provider", lambda s: FakeRealProvider())

    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/chat", json={"message": "anything"})
    assert r.status_code == 200
    body = r.json()
    ops = {o["op_type"]: o for o in body["operations"]}
    # invented asset rejected
    assert ops["add_track"]["applied"] is False
    assert "does not exist" in ops["add_track"]["error"]
    # valid op still applied
    assert ops["add_section"]["applied"] is True
    # unknown op type rejected at validation
    assert any(not o["applied"] and "rejected" in (o["error"] or "")
               for o in body["operations"] if o["op_type"] == "(planner)")
    # project persisted with only the valid change
    proj = client.get(f"/api/projects/{p['id']}").json()
    assert len(proj["sections"]) == 1
    assert len(proj["tracks"]) == 0


def test_anthropic_provider_without_key_fails_cleanly(workspace, monkeypatch):
    from app.services.llm.provider import AnthropicProvider, LlmProviderError
    from app.services.llm.settings import LlmSettings

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MITY_LLM_API_KEY", raising=False)
    provider = AnthropicProvider(LlmSettings(provider="anthropic"))
    ok, msg = provider.test_connection()
    assert ok is False
    assert "key" in msg.lower() or "anthropic" in msg.lower()


def test_system_prompt_contains_only_real_assets(client, workspace):
    from tests.test_sample_analysis import write_tone
    write_tone(workspace.samples_dir / "groove - 120 BPM.wav")
    client.post("/api/assets/rescan")

    from app.services import operation_planner, project_repo
    p = make_project(client)
    project = project_repo.load_project(p["id"])
    prompt = operation_planner.build_system_prompt(project)
    assert "groove - 120 BPM.wav" in prompt
    assert "NEVER generate audio" in prompt
    assert "Never invent ids" in prompt
