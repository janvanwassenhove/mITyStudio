"""Portable bundles: project + voice export/import round trips."""
from app.models.song import Clip, Section, SongProject, Track
from app.services import asset_repo, bundles, project_repo


def _seeded_project(client, workspace) -> SongProject:
    from tests.test_sample_analysis import write_tone
    write_tone(workspace.samples_dir / "bundle groove.wav")
    client.post("/api/assets/rescan")
    sample = asset_repo.list_assets("sample")[0]

    p = SongProject(title="Bundle Song", bpm=120)
    sec = Section(name="Verse", start_bar=0, length_bars=4)
    p.sections.append(sec)
    t = Track(name="Samples", track_type="sample")
    t.clips.append(Clip(section_id=sec.id, clip_type="sample",
                        start_beat=0, duration_beats=8,
                        source_asset_id=sample.id))
    p.tracks.append(t)
    project_repo.save_project(p)
    return p


def test_project_bundle_round_trip(client, workspace):
    p = _seeded_project(client, workspace)
    zip_path = bundles.export_project_bundle(p.id)
    assert zip_path.exists() and zip_path.stat().st_size > 100

    # delete the original project, then import the bundle
    project_repo.delete_project(p.id)
    result = bundles.import_project_bundle(zip_path)
    assert not result["warnings"]
    p2 = project_repo.load_project(result["project_id"])
    assert p2.title == "Bundle Song"
    clip = p2.tracks[0].clips[0]
    a = asset_repo.get_asset(clip.source_asset_id)
    assert a is not None and not a.is_missing


def test_project_bundle_import_alongside_existing(client, workspace):
    p = _seeded_project(client, workspace)
    zip_path = bundles.export_project_bundle(p.id)
    result = bundles.import_project_bundle(zip_path)   # original still exists
    assert result["project_id"] != p.id
    assert "(imported)" in result["title"]
    p2 = project_repo.load_project(result["project_id"])
    # the asset already existed with the same file → same id reused
    assert p2.tracks[0].clips[0].source_asset_id == p.tracks[0].clips[0].source_asset_id


def test_delete_project_endpoint(client, workspace):
    p = _seeded_project(client, workspace)
    r = client.delete(f"/api/projects/{p.id}")
    assert r.status_code == 200
    assert client.get(f"/api/projects/{p.id}").status_code == 404


def test_voice_bundle_round_trip(client, workspace):
    from tests.test_sample_analysis import write_tone
    write_tone(workspace.voice_recordings_dir / "take one.wav", seconds=2.0)
    client.post("/api/assets/rescan")
    rec = asset_repo.list_assets("voice_recording")[0]
    r = client.post("/api/voice/profiles", json={
        "name": "Bundle Voice", "source_recording_ids": [rec.id],
        "consent_confirmed": True, "consent_notes": "test"})
    assert r.status_code == 201
    pid = r.json()["id"]

    zip_path = bundles.export_voice_bundle(pid)
    assert zip_path.exists()
    # re-import over the same workspace: profile exists → reused, no dupes
    result = bundles.import_voice_bundle(zip_path)
    assert result["profile_id"] == pid
