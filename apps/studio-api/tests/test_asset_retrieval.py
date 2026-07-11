"""Message-aware asset retrieval (the chat planner's deterministic RAG)."""
from __future__ import annotations

from tests.test_projects import make_project


def test_key_compatibility():
    from app.services.asset_retrieval import _keys_compatible
    assert _keys_compatible("C major", "C major")
    assert _keys_compatible("C major", "A minor")      # relative pair
    assert _keys_compatible("A minor", "C major")
    assert not _keys_compatible("C major", "F# major")
    assert not _keys_compatible("C major", "D minor")
    assert _keys_compatible(None, "C major")           # unknown → permissive
    assert _keys_compatible("C major", None)


def test_retrieval_ranks_fitting_samples_first(client, workspace):
    """A bpm-matching, keyword-matching sample must outrank a mismatched
    loop; the summary reflects the real library."""
    from tests.test_sample_analysis import write_tone
    write_tone(workspace.samples_dir / "conga groove - 120 BPM.wav",
               seconds=1.0)
    write_tone(workspace.samples_dir / "slow pad - 70 BPM.wav", seconds=1.0)
    client.post("/api/assets/rescan")
    for s in client.get("/api/assets/samples").json():
        client.post(f"/api/assets/{s['id']}/analyse")

    from app.services import asset_retrieval, project_repo
    p = make_project(client)                    # default bpm 120
    project = project_repo.load_project(p["id"])

    samples = asset_retrieval.retrieve_samples("add a conga groove", project)
    assert samples, "retrieval returned nothing"
    assert "conga" in samples[0]["filename"].lower()

    summary = asset_retrieval.summary()
    assert summary["total_samples"] == 2
    assert summary["analysed_samples"] == 2


def test_prompt_carries_summary_and_relevant_assets(client, workspace):
    from tests.test_sample_analysis import write_tone
    write_tone(workspace.samples_dir / "kick punchy.wav", seconds=0.5)
    client.post("/api/assets/rescan")

    from app.services import operation_planner, project_repo
    p = make_project(client)
    project = project_repo.load_project(p["id"])
    prompt = operation_planner.build_system_prompt(
        project, "en", "make a techno track with a punchy kick")
    assert "library_summary" in prompt
    assert "kick punchy.wav" in prompt


def test_alignment_text_folding():
    """fold(word) == concat(fold(syllable)) must hold — the char-allocation
    invariant syllable timing depends on."""
    from app.services.lyric_text import word_syllables
    from app.services.vocal_align import _fold
    for word in ("hello", "Straße", "café", "vrolijk", "père", "schönen"):
        syls = word_syllables(word)
        assert _fold(word) == "".join(_fold(s) for s in syls), word


def test_genre_delivery_resolution():
    from app.services.vocal_clone import _STYLES, resolve_delivery
    assert resolve_delivery("sing", "Punk Rock") == "rock"
    assert resolve_delivery("sing", "acoustic ballad") == "ballad"
    assert resolve_delivery("sing", "Deep House") == "edm"
    assert resolve_delivery("sing", "unknown genre") == "sing"
    assert resolve_delivery("sing", None) == "sing"
    assert resolve_delivery("powerful", "jazz") == "powerful"  # explicit wins
    for style in ("ballad", "rock", "jazz", "edm", "country"):
        assert style in _STYLES
        assert {"vib", "vib_rate", "breath", "gain",
                "overshoot", "feel"} <= set(_STYLES[style])
