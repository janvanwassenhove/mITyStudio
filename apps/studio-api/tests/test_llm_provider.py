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


def test_openai_provider_key_and_url_rules(workspace, monkeypatch):
    from app.services.llm.provider import (LlmProviderError, OpenAIProvider,
                                           get_provider)
    from app.services.llm.settings import LlmSettings

    for env in ("OPENAI_API_KEY", "MITY_LLM_API_KEY"):
        monkeypatch.delenv(env, raising=False)

    # openai without key → clean failure
    ok, msg = OpenAIProvider(LlmSettings(provider="openai",
                                         model="gpt-5.2")).test_connection()
    assert ok is False and "key" in msg.lower()

    # custom without base_url → clean failure naming the fix
    ok, msg = OpenAIProvider(LlmSettings(provider="custom", model="llama3"),
                             "custom").test_connection()
    assert ok is False and "base url" in msg.lower()

    # custom with base_url but no key builds a client (local servers)
    p = OpenAIProvider(LlmSettings(provider="custom", model="llama3",
                                   base_url="http://localhost:1/v1"), "custom")
    client = p._client()
    assert str(client.base_url).startswith("http://localhost:1")

    # factory dispatch
    assert type(get_provider(LlmSettings(provider="openai"))).__name__ == "OpenAIProvider"
    assert type(get_provider(LlmSettings(provider="custom"))).__name__ == "OpenAIProvider"
    assert type(get_provider(LlmSettings(provider="anthropic"))).__name__ == "AnthropicProvider"
    assert type(get_provider(LlmSettings(provider="mock"))).__name__ == "MockLlmProvider"


def test_env_var_key_detection(workspace, monkeypatch):
    from app.services.llm.settings import get_api_key, key_source

    for env in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "OPENAI_API_KEY",
                "OPENROUTER_API_KEY", "GEMINI_API_KEY", "MITY_LLM_API_KEY"):
        monkeypatch.delenv(env, raising=False)

    # provider-specific env vars
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-openai")
    assert key_source("openai") == "OPENAI_API_KEY"
    assert get_api_key("openai") == "sk-env-openai"
    assert key_source("anthropic") is None

    monkeypatch.setenv("CLAUDE_API_KEY", "sk-env-claude")
    assert key_source("anthropic") == "CLAUDE_API_KEY"

    # domain-matched env var for the custom provider
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env-or")
    assert key_source("custom", "https://openrouter.ai/api/v1") == "OPENROUTER_API_KEY"
    assert get_api_key("custom", "https://openrouter.ai/api/v1") == "sk-env-or"
    monkeypatch.setenv("GEMINI_API_KEY", "sk-env-gem")
    assert key_source(
        "custom",
        "https://generativelanguage.googleapis.com/v1beta/openai/") == "GEMINI_API_KEY"
    # unrelated base_url does not leak another provider's key
    assert key_source("custom", "http://localhost:11434/v1") is None

    # stored key always wins over env
    from app.services.llm.settings import store_api_key
    store_api_key("openai", "sk-stored")
    assert key_source("openai") == "stored"
    assert get_api_key("openai") == "sk-stored"


def test_settings_endpoint_reports_key_sources(client, workspace, monkeypatch):
    for env in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "OPENAI_API_KEY",
                "OPENROUTER_API_KEY", "MITY_LLM_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

    s = client.get("/api/settings/llm").json()
    assert s["api_key_sources"]["openai"] == "OPENAI_API_KEY"
    assert s["api_key_sources"]["anthropic"] is None
    assert "sk-env" not in str(s)

    # base_url-aware: saving a custom provider with an OpenRouter URL
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or")
    s = client.put("/api/settings/llm", json={
        "provider": "custom", "model": "meta-llama/llama-3-70b",
        "base_url": "https://openrouter.ai/api/v1"}).json()
    assert s["api_key_sources"]["custom"] == "OPENROUTER_API_KEY"
    assert s["api_key_set"] is True


def test_openai_provider_plan_parses_response(workspace, monkeypatch):
    """plan() path with a stubbed OpenAI client — no network."""
    from app.services.llm.provider import OpenAIProvider
    from app.services.llm.settings import LlmSettings

    class FakeMsg:
        content = '{"reply": "done", "operations": [{"op_type": "change_tempo", "params": {"bpm": 100}}]}'

    class FakeChoice:
        message = FakeMsg()

    class FakeResp:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == "test-model"
            assert kwargs["messages"][0]["role"] == "system"
            return FakeResp()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    provider = OpenAIProvider(LlmSettings(provider="openai", model="test-model"))
    monkeypatch.setattr(provider, "_client", lambda: FakeClient())
    out = provider.plan("system", "make it 100 bpm")
    assert out["reply"] == "done"
    assert out["operations"][0]["op_type"] == "change_tempo"


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


def test_composition_aware_context(client, workspace):
    """The planner sees real instruments (bank/program), analysed sample
    metadata, and voice-model readiness."""
    import shutil
    from pathlib import Path

    from tests.test_sample_analysis import write_tone
    repo_fonts = Path(__file__).resolve().parents[3] / "soundfonts"
    fonts = sorted(repo_fonts.glob("*.sf2"), key=lambda f: f.stat().st_size)
    if fonts:
        shutil.copy2(fonts[0], workspace.soundfonts_dir / fonts[0].name)
    write_tone(workspace.samples_dir / "pad - 100 BPM - Am.wav", seconds=1.0)
    client.post("/api/assets/rescan")
    sample = client.get("/api/assets/samples").json()[0]
    client.post(f"/api/assets/{sample['id']}/analyse")

    from tests.test_voice_and_vocals import upload_recording
    rec = upload_recording(client)
    client.post("/api/voice/profiles", json={
        "name": "Me", "source_recording_ids": [rec["id"]],
        "consent_confirmed": True})

    from app.services.operation_planner import _asset_context
    ctx = _asset_context()
    if fonts:
        assert ctx["instruments"]
        inst = ctx["instruments"][0]
        assert {"category", "preset", "soundfont_asset_id", "bank",
                "program"} <= set(inst)
    s = next(x for x in ctx["samples"] if "pad" in x["filename"])
    assert s["bpm"] == 100.0
    assert s["key"] == "A minor"
    assert ctx["voice_profiles"][0]["high_fidelity_model_trained"] is False


def test_assign_soundfont_with_bank(client, workspace):
    import shutil
    from pathlib import Path
    repo_fonts = Path(__file__).resolve().parents[3] / "soundfonts"
    fonts = sorted(repo_fonts.glob("*.sf2"), key=lambda f: f.stat().st_size)
    if not fonts:
        import pytest
        pytest.skip("no soundfonts")
    shutil.copy2(fonts[0], workspace.soundfonts_dir / fonts[0].name)
    client.post("/api/assets/rescan")
    sf = client.get("/api/assets/soundfonts").json()[0]

    from app.models.operations import ChatOperation
    from app.models.song import SongProject, Track
    from app.services import operation_applier
    project = SongProject(title="t", tracks=[Track(name="D", track_type="drums")])
    results = operation_applier.apply_operations(project, [
        ChatOperation(op_type="assign_soundfont",
                      params={"track": "D", "soundfont_asset_id": sf["id"],
                              "bank": 128, "program": 7,
                              "preset": "TR-808 Drumset"})])
    assert results[0].applied, results[0].error
    assert "TR-808 Drumset" in results[0].summary
    cfg = project.tracks[0].instrument_config
    assert (cfg.bank, cfg.program) == (128, 7)
