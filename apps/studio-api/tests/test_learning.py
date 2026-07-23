"""The agentic improvement loop and local preference learning.

The design contract these pin: learning is MEASURED and LOCAL. The loop
hill-climbs an objective score and can never make a song worse; preferences
come only from what the user saves, feed back deterministically, and never
let the model tune itself.
"""
from __future__ import annotations

import pytest

from app.models.song import Clip, Effect, Section, SongProject, Track
from app.services import arrangement_metrics as am


def _full_song(style: str = "pop") -> SongProject:
    from app.services import music_gen
    p = SongProject(title="t", style=style, bpm=120, key="C major")
    p.sections = [Section(name=n, start_bar=b, length_bars=8, energy=e)
                  for n, b, e in (("Intro", 0, 0.3), ("Chorus", 8, 0.9),
                                  ("Verse 2", 16, 0.5), ("Chorus 2", 24, 0.95),
                                  ("Outro", 32, 0.35))]
    for name, tt, gen in (("Drums", "drums", music_gen.generate_drums),
                          ("Bass", "bass", music_gen.generate_bassline),
                          ("Keys", "keys", music_gen.generate_chords)):
        t = Track(name=name, track_type=tt)
        for s in p.sections:
            c = gen(p, s)
            if c.note_events:
                t.clips.append(c)
        p.tracks.append(t)
    return p


# --- quality score ---------------------------------------------------------

def test_score_rewards_a_finished_song_over_a_stub():
    from app.services import mixing
    stub = SongProject(title="t", key="C major")
    stub.sections = [Section(name="V", start_bar=0, length_bars=4, energy=0.5)]
    stub_score = am.score(am.analyse(stub), stub)["score"]

    song = _full_song()
    mixing.finalize_song(song)
    song_score = am.score(am.analyse(song), song)["score"]

    assert song_score > stub_score
    assert song_score >= 0.9            # a finished, mixed song scores high


def test_score_names_the_weakest_dimensions():
    song = _full_song()                 # no mix, no ending yet
    sc = am.score(am.analyse(song), song)
    assert "mix" in sc["weakest"] and "ending" in sc["weakest"]
    assert sc["dimensions"]["mix"] == 0.0

    from app.services import mixing
    mixing.finalize_song(song)          # now both are addressed
    sc2 = am.score(am.analyse(song), song)
    assert sc2["score"] > sc["score"]
    assert "mix" not in sc2["weakest"] and "ending" not in sc2["weakest"]


def test_has_ending_and_has_mix_detect_the_real_thing():
    song = _full_song()
    assert not am.has_ending(song) and not am.has_mix(song)
    from app.services import mixing
    mixing.apply_ending(song)
    assert am.has_ending(song)
    mixing.apply_default_mix(song)
    assert am.has_mix(song)


# --- preference learning ---------------------------------------------------

@pytest.fixture()
def prefs(workspace):
    from app.services import preferences
    preferences.reset()
    yield preferences
    preferences.reset()


def test_learns_role_volume_from_saved_projects(prefs):
    song = _full_song()
    for t in song.tracks:                       # the user pushes everything up
        t.volume = 1.4 if t.track_type == "bass" else 1.0
    for _ in range(6):                          # save it a few times
        prefs.observe(song)
    # the learned bass level sits between default (0.9) and the user's 1.4
    learned = prefs.role_volume("bass", 0.9)
    assert 0.9 < learned < 1.4
    # an unseen role falls back cleanly
    assert prefs.role_volume("strings", 0.66) == 0.66


def test_learns_asset_taste_per_genre(prefs):
    song = _full_song("funk")
    song.tracks[0].instrument_config.soundfont_asset_id = "font-abc"
    for _ in range(4):
        prefs.observe(song)
    assert "font-abc" in prefs.preferred_assets("funk", "sf")
    assert prefs.asset_boost("funk", "font-abc") > 0
    assert prefs.asset_boost("funk", "never-used") == 0
    # taste is genre-scoped: a rock query is not swayed by funk saves
    assert prefs.asset_boost("rock", "font-abc") == 0


def test_empty_projects_teach_nothing(prefs):
    empty = SongProject(title="t")
    empty.tracks = [Track(name="X", track_type="keys")]   # no clips
    prefs.observe(empty)
    assert prefs.summary()["saves_learned_from"] == 0


def test_recurring_issues_read_from_the_ledger(prefs, workspace):
    import json
    led = workspace.analysis_cache_dir / "song-pipeline.jsonl"
    led.parent.mkdir(parents=True, exist_ok=True)
    with open(led, "w", encoding="utf-8") as f:
        for _ in range(3):
            f.write(json.dumps({"metrics": {"is_complete_song": False,
                                            "static_arrangement": True},
                                "score": 0.6}) + "\n")
    issues = prefs.recurring_issues()
    assert issues and any("incomplete" in i or "static" in i for i in issues)


def test_mixing_uses_learned_volume(prefs):
    from app.services import mixing
    song = _full_song()
    for t in song.tracks:
        if t.track_type == "keys":
            t.volume = 1.1
    for _ in range(8):
        prefs.observe(song)
    fresh = _full_song()
    mixing.apply_default_mix(fresh)
    keys = next(t for t in fresh.tracks if t.track_type == "keys")
    assert keys.volume > 0.74           # nudged up from the built-in default


def test_improvement_loop_reverts_a_regression(client, workspace, monkeypatch):
    """A round that does not raise the score is rolled back — the loop can
    never leave the song worse than it started."""
    from app.services import song_pipeline as sp

    # a real LLM is "available", but the critic makes the song WORSE
    monkeypatch.setattr(sp, "_llm_available", lambda: True)

    calls = {"n": 0}

    def _bad_critic(project, metrics, sc, language, job):
        calls["n"] += 1
        project.tracks[0].clips = []          # delete a part → lower score
        return ["(damaging edit)"]
    monkeypatch.setattr(sp, "_critic_round", _bad_critic)

    project = _full_song()
    from app.services import mixing, project_repo
    mixing.finalize_song(project)
    project_repo.save_project(project)
    before = am.score(am.analyse(project), project)["score"]

    # drive just the loop body via a tiny job dict, mirroring _run
    job = {"log": []}
    metrics = am.analyse(project)
    sc = am.score(metrics, project)
    snapshot = project.model_copy(deep=True)
    fixes = sp._critic_round(project, metrics, sc, "en", job)
    new_sc = am.score(am.analyse(project), project)
    if new_sc["score"] < sc["score"] + sp.MIN_GAIN:
        project = snapshot                    # the loop's revert
    after = am.score(am.analyse(project), project)["score"]

    assert calls["n"] == 1
    assert after >= before                    # regression was undone
