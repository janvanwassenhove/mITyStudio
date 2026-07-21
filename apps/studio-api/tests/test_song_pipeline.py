"""Full-song pipeline (docs/song-quality.md M5) — offline/mock path.

R2 acceptance: with the mock provider (tests never call an LLM), a
full-song request still yields a complete, genre-true, dynamically
arranged song.
"""
from __future__ import annotations

import time

from tests.test_projects import make_project


def _wait_done(client, pid: str, job_id: str, timeout: float = 20.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = client.get(f"/api/projects/{pid}/generate-song/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.1)
    raise AssertionError(f"pipeline did not finish: {job}")


def test_offline_pipeline_builds_a_complete_song(client, workspace):
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/generate-song",
                    json={"prompt": "a happy bossa nova pop song"})
    assert r.status_code == 202, r.text
    job = _wait_done(client, p["id"], r.json()["job_id"])
    assert job["status"] == "done", job.get("error")
    assert job["llm_calls"] == 0                      # fully offline

    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj["genre"] == "bossa"
    assert 110 <= proj["bpm"] <= 145                  # in the genre range
    assert len(proj["sections"]) >= 3
    track_types = {t["track_type"] for t in proj["tracks"]}
    assert "drums" in track_types and "bass" in track_types
    assert "brass" in track_types                     # bossa band choice

    # objective quality gate (R6)
    from app.services import arrangement_metrics, project_repo
    m = arrangement_metrics.analyse(project_repo.load_project(p["id"]))
    assert m["is_complete_song"], m["incomplete_reasons"]
    assert not m["static_arrangement"]
    assert m["key_ratio"] > 0.8

    # the run landed in the ledger (R4)
    ledger = workspace.analysis_cache_dir / "song-pipeline.jsonl"
    assert ledger.exists() and "bossa" in ledger.read_text(encoding="utf-8")


def test_pipeline_renders_stems_for_the_critic(client, workspace):
    """The render stage fills the waveform cache so metrics carry real
    per-stem peaks — and the song is playable the moment the job ends."""
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/generate-song",
                    json={"prompt": "funk instrumental"})
    job = _wait_done(client, p["id"], r.json()["job_id"], timeout=60)
    assert job["status"] == "done", job.get("error")

    from app.services import arrangement_metrics, project_repo
    project = project_repo.load_project(p["id"])
    assert project.stems, "no stems rendered by the pipeline"
    m = arrangement_metrics.analyse(project)
    assert m["stems"], "metrics carry no per-stem peaks"
    assert all(0 < s["peak"] <= 1.0 for s in m["stems"])


def test_chat_hands_full_song_requests_to_the_pipeline(client, workspace,
                                                       monkeypatch):
    """docs/song-quality.md §10: chat routing. With a real LLM configured, a
    make-a-song message on an empty project starts the pipeline; edits (and
    the mock provider) keep the normal synchronous chat flow."""
    from app.services import song_pipeline
    from app.services.song_pipeline import detect_full_song_intent
    assert detect_full_song_intent("maak een vrolijk bossa nova nummer")
    assert detect_full_song_intent("create a punk song about summer")
    assert detect_full_song_intent("écris une chanson douce")
    assert detect_full_song_intent("erstelle einen kompletten Song")
    assert detect_full_song_intent("ik wil een nummer maken over de zee")
    # compound song nouns (the normal Dutch/German phrasing)
    assert detect_full_song_intent(
        "Maak een vrolijk popnummer over zomeravonden, met drums en zang")
    assert detect_full_song_intent("create a punksong about the city")
    assert detect_full_song_intent("erstelle ein Sommerlied")
    assert not detect_full_song_intent("add a guitar track")
    assert not detect_full_song_intent("make it faster")

    # mock provider (the default in tests) → NO handoff, planner flow runs
    p0 = make_project(client)
    r0 = client.post(f"/api/projects/{p0['id']}/chat",
                     json={"message": "maak een reggae nummer",
                           "language": "nl"})
    assert r0.json().get("job") is None

    # "real LLM" → handoff (plan() still resolves to the mock under test,
    # which every pipeline stage tolerates)
    monkeypatch.setattr(song_pipeline, "_llm_available", lambda: True)
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/chat",
                    json={"message": "maak een reggae nummer", "language": "nl"})
    assert r.status_code == 200
    body = r.json()
    assert body["job"] and body["job"]["kind"] == "generate_song"
    assert "achtergrond" in body["reply"]          # localized ack
    job = _wait_done(client, p["id"], body["job"]["job_id"], timeout=60)
    assert job["status"] == "done", job.get("error")
    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj["genre"] == "reggae"
    assert any(t["clips"] for t in proj["tracks"])

    # a project WITH content never gets hijacked by the pipeline
    r2 = client.post(f"/api/projects/{p['id']}/chat",
                     json={"message": "maak een punk nummer", "language": "nl"})
    assert r2.json().get("job") is None


def test_explicit_bpm_always_wins_over_the_genre_range(client, workspace):
    """Regression: the genre tempo table is guidance for when the user says
    nothing — it must never cap a tempo they asked for out loud."""
    from app.services.song_pipeline import _fallback_spec, explicit_bpm

    assert explicit_bpm("een punk nummer op 170 bpm") == 170
    assert explicit_bpm("erstelle einen Song mit BPM: 96") == 96
    assert explicit_bpm("a song at 128bpm") == 128
    assert explicit_bpm("make 4 sections about summer 2024") is None
    assert explicit_bpm("no tempo here") is None
    assert explicit_bpm("9999 bpm") is None            # out of valid range

    # 175 is far outside pop's 95-125 range and must survive anyway
    assert _fallback_spec("maak een pop nummer, 175 bpm")["bpm"] == 175
    assert _fallback_spec("a slow ballad at 60 bpm")["bpm"] == 60
    # nothing asked → the genre's typical tempo
    assert 118 <= _fallback_spec("a house track")["bpm"] <= 132

    # end to end: the generated project really carries the requested tempo
    p = make_project(client)
    r = client.post(f"/api/projects/{p['id']}/generate-song",
                    json={"prompt": "a pop song at 172 bpm"})
    job = _wait_done(client, p["id"], r.json()["job_id"], timeout=60)
    assert job["status"] == "done", job.get("error")
    assert client.get(f"/api/projects/{p['id']}").json()["bpm"] == 172


def test_pipeline_refuses_to_clobber_content(client, workspace):
    """R1: a project with clips requires force=true."""
    p = make_project(client)
    r1 = client.post(f"/api/projects/{p['id']}/generate-song",
                     json={"prompt": "synthwave night drive"})
    _wait_done(client, p["id"], r1.json()["job_id"])

    r2 = client.post(f"/api/projects/{p['id']}/generate-song",
                     json={"prompt": "now make it polka"})
    assert r2.status_code == 409
    r3 = client.post(f"/api/projects/{p['id']}/generate-song",
                     json={"prompt": "deep house sunrise set", "force": True})
    assert r3.status_code == 202
    job = _wait_done(client, p["id"], r3.json()["job_id"])
    assert job["status"] == "done"
    proj = client.get(f"/api/projects/{p['id']}").json()
    assert proj["genre"] == "dance"
