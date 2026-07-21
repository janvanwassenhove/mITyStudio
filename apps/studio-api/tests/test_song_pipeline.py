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
