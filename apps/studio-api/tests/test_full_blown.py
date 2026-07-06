"""Full-blown upgrade tests: SF2 preset parsing + smart matching, MusicXML
import, Guitar Pro import, master bus effects, pitch detection."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tests.test_projects import make_project
from tests.test_sample_analysis import write_tone

REPO_SOUNDFONTS = Path(__file__).resolve().parents[3] / "soundfonts"


# --- SF2 parsing + smart matching ------------------------------------------

@pytest.mark.skipif(not list(REPO_SOUNDFONTS.glob("*.sf2")),
                    reason="needs real .sf2 files in soundfonts/")
def test_sf2_preset_parsing(workspace):
    from app.services.sf2_parser import parse_sf2
    sf2 = sorted(REPO_SOUNDFONTS.glob("*.sf2"), key=lambda p: p.stat().st_size)[0]
    info = parse_sf2(sf2)
    assert isinstance(info["presets"], list) and info["presets"]
    p = info["presets"][0]
    assert set(p) == {"name", "bank", "program"}
    assert 0 <= p["program"] <= 127


@pytest.mark.skipif(not list(REPO_SOUNDFONTS.glob("*.sf2")),
                    reason="needs real .sf2 files in soundfonts/")
def test_smart_soundfont_matching(client, workspace):
    # copy a bass-ish and a generic font into the isolated workspace
    fonts = sorted(list(REPO_SOUNDFONTS.glob("*.sf2"))
                   + list(REPO_SOUNDFONTS.glob("*.SF2")),
                   key=lambda p: p.stat().st_size)
    bass_font = next((f for f in fonts if "bass" in f.name.lower()), None)
    if bass_font is None:
        pytest.skip("no bass soundfont in library")
    shutil.copy2(bass_font, workspace.soundfonts_dir / bass_font.name)
    shutil.copy2(fonts[0], workspace.soundfonts_dir / fonts[0].name)
    client.post("/api/assets/rescan")

    from app.services.sf2_parser import find_best_soundfont
    match = find_best_soundfont("bass")
    assert match is not None
    asset, preset = match
    assert "bass" in (asset.filename + preset["name"]).lower()

    # preset endpoint
    sf_assets = client.get("/api/assets/soundfonts").json()
    r = client.get(f"/api/assets/{sf_assets[0]['id']}/soundfont-presets")
    assert r.status_code == 200
    assert r.json()["presets"]


def test_auto_assign_soundfonts_sets_config(client, workspace):
    fonts = sorted(list(REPO_SOUNDFONTS.glob("*.sf2")),
                   key=lambda p: p.stat().st_size)
    if not fonts:
        pytest.skip("no soundfonts")
    shutil.copy2(fonts[0], workspace.soundfonts_dir / fonts[0].name)
    client.post("/api/assets/rescan")

    from app.models.song import SongProject, Track
    from app.services.render.soundfont_renderer import auto_assign_soundfonts
    project = SongProject(title="t", tracks=[Track(name="B", track_type="bass")])
    auto_assign_soundfonts(project)
    # with only one (possibly unsuitable) font, assignment may or may not
    # happen — but if it did, the config must be complete
    cfg = project.tracks[0].instrument_config
    if cfg.soundfont_asset_id:
        assert 0 <= cfg.program <= 127


# --- MusicXML import --------------------------------------------------------

MUSICXML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name>
      <midi-instrument id="P1-I1"><midi-channel>1</midi-channel>
        <midi-program>1</midi-program></midi-instrument>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>2</divisions>
        <key><fifths>2</fifths><mode>major</mode></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <direction><sound tempo="96"/></direction>
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>2</duration></note>
      <note><pitch><step>F</step><alter>1</alter><octave>4</octave></pitch><duration>2</duration></note>
      <note><pitch><step>A</step><octave>4</octave></pitch><duration>2</duration>
        <tie type="start"/></note>
      <note><pitch><step>A</step><octave>4</octave></pitch><duration>2</duration>
        <tie type="stop"/></note>
    </measure>
    <measure number="2">
      <note><rest/><duration>4</duration></note>
      <note><pitch><step>D</step><octave>5</octave></pitch><duration>2</duration></note>
      <note><chord/><pitch><step>F</step><alter>1</alter><octave>5</octave></pitch><duration>2</duration></note>
    </measure>
  </part>
</score-partwise>
"""


def test_musicxml_import(client, workspace):
    (workspace.scores_dir / "piece.musicxml").write_text(MUSICXML, encoding="utf-8")
    client.post("/api/assets/rescan")
    score = client.get("/api/assets/scores").json()[0]

    r = client.post(f"/api/scores/{score['id']}/import", json={})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["supported"] is True
    assert res["detected_tempo"] == 96.0
    assert res["detected_key"] == "D major"
    assert res["time_signature"] == "4/4"
    t = res["detected_tracks"][0]
    assert t["name"] == "Piano"
    notes = t["notes"]
    # D4, F#4, A4(tied 2 beats), then chord D5+F#5 in bar 2 → 5 note events
    assert [n["midi_note"] for n in notes] == [62, 66, 69, 74, 78]
    tied = next(n for n in notes if n["midi_note"] == 69)
    assert tied["duration_beats"] == 2.0
    # chord notes share a start (bar2 beat 2 → absolute beat 6)
    assert notes[3]["start_beat"] == notes[4]["start_beat"] == 6.0

    # can create a project from it
    r2 = client.post(f"/api/scores/{score['id']}/import",
                     json={"create_project": True, "title": "From XML"})
    pid = r2.json()["project_id"]
    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["bpm"] == 96.0
    assert proj["key"] == "D major"


def test_mxl_compressed_import(client, workspace):
    import zipfile
    mxl = workspace.scores_dir / "piece.mxl"
    with zipfile.ZipFile(mxl, "w") as zf:
        zf.writestr("META-INF/container.xml",
                    '<?xml version="1.0"?><container><rootfiles>'
                    '<rootfile full-path="score.xml"/></rootfiles></container>')
        zf.writestr("score.xml", MUSICXML)
    client.post("/api/assets/rescan")
    score = next(s for s in client.get("/api/assets/scores").json()
                 if s["extension"] == ".mxl")
    r = client.post(f"/api/scores/{score['id']}/import", json={})
    assert r.json()["supported"] is True
    assert r.json()["detected_tracks"][0]["note_count"] == 5


# --- Guitar Pro import -------------------------------------------------------

def _make_gp_song():
    from guitarpro import models as gm
    song = gm.Song()
    song.tempo = 132
    track = song.tracks[0]
    track.name = "Guitar"
    voice = track.measures[0].voices[0]
    beat = gm.Beat(voice)
    beat.duration = gm.Duration(value=4)  # quarter
    note = gm.Note(beat)
    note.string = 6
    note.value = 0        # low E open
    note.type = gm.NoteType.normal
    beat.notes.append(note)
    voice.beats.append(beat)
    beat2 = gm.Beat(voice)
    beat2.duration = gm.Duration(value=8)  # eighth
    note2 = gm.Note(beat2)
    note2.string = 5
    note2.value = 2       # B on A string
    note2.type = gm.NoteType.normal
    beat2.notes.append(note2)
    voice.beats.append(beat2)
    return song


def test_guitarpro_conversion(workspace):
    """Conversion logic tested on an in-memory Song (the gp5 writer merges
    programmatically-built beats, so file round-trip isn't representative)."""
    from app.services.guitarpro_import import convert_song
    from app.services.score_import import ScoreImportResult

    res = convert_song(_make_gp_song(),
                       ScoreImportResult(source_asset_id="x", format="guitarpro"))
    assert res.supported is True
    assert res.detected_tempo == 132.0
    t = res.detected_tracks[0]
    assert t.name == "Guitar"
    # standard tuning: string6 fret0 = E2(40), string5 fret2 = B2(47)
    assert [n["midi_note"] for n in t.notes] == [40, 47]
    assert t.notes[0]["duration_beats"] == 1.0
    assert t.notes[1]["duration_beats"] == 0.5
    assert t.notes[1]["start_beat"] == 1.0
    assert res.time_signature == "4/4"


def test_guitarpro_file_import_endpoint(client, workspace):
    """End-to-end: a real .gp5 file through the import endpoint."""
    import guitarpro
    guitarpro.write(_make_gp_song(), str(workspace.scores_dir / "riff.gp5"))
    client.post("/api/assets/rescan")
    score = client.get("/api/assets/scores").json()[0]
    r = client.post(f"/api/scores/{score['id']}/import", json={})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["supported"] is True, res["warnings"]
    assert res["detected_tempo"] == 132.0
    assert res["detected_tracks"][0]["notes"]  # notes survive round-trip


def test_gpx_still_placeholder(client, workspace):
    (workspace.scores_dir / "x.gpx").write_bytes(b"BCFZ-dummy")
    client.post("/api/assets/rescan")
    score = next(s for s in client.get("/api/assets/scores").json()
                 if s["extension"] == ".gpx")
    r = client.post(f"/api/scores/{score['id']}/import", json={})
    assert r.json()["supported"] is False


# --- master bus + pitch detection -------------------------------------------

def test_master_effects_in_mixdown(client, workspace):
    write_tone(workspace.samples_dir / "tone.wav", seconds=2.0, freq=220,
               rate=44100, amp=0.4)
    client.post("/api/assets/rescan")
    sample = client.get("/api/assets/samples").json()[0]

    p = make_project(client, bpm=120)
    p["sections"] = [{"name": "A", "start_bar": 0, "length_bars": 2}]
    p["tracks"] = [{"name": "S", "track_type": "sample",
                    "clips": [{"clip_type": "sample", "start_beat": 0,
                               "duration_beats": 8,
                               "source_asset_id": sample["id"], "loop": True}]}]
    p["mix_settings"] = {"master_volume": 1.0, "normalize": False,
                         "limiter": False,
                         "master_effects": {"effects": [
                             {"effect_type": "gain", "params": {"gain_db": -20}}]}}
    client.put(f"/api/projects/{p['id']}", json=p)
    job = client.post(f"/api/projects/{p['id']}/export/mix",
                      json={"formats": ["wav"]}).json()
    assert job["status"] == "completed", job["errors"]
    quiet, _ = sf.read(str(workspace.root / job["output_files"][0]))

    p = client.get(f"/api/projects/{p['id']}").json()
    p["mix_settings"]["master_effects"]["effects"] = []
    client.put(f"/api/projects/{p['id']}", json=p)
    job2 = client.post(f"/api/projects/{p['id']}/export/mix",
                       json={"formats": ["wav"]}).json()
    loud, _ = sf.read(str(workspace.root / job2["output_files"][0]))
    assert np.abs(quiet).max() < np.abs(loud).max() * 0.2


def test_master_effect_via_chat_operation(client):
    from app.models.operations import ChatOperation
    from app.models.song import SongProject
    from app.services import operation_applier
    project = SongProject(title="t")
    results = operation_applier.apply_operations(project, [
        ChatOperation(op_type="add_effect",
                      params={"track": "master", "effect_type": "compressor",
                              "params": {"threshold_db": -12}})])
    assert results[0].applied, results[0].error
    assert project.mix_settings.master_effects.effects[0].effect_type == "compressor"


def test_pitch_detection_on_tonal_sample(client, workspace):
    # A3 = 220 Hz pure tone, no key in filename
    write_tone(workspace.samples_dir / "mystery.wav", seconds=1.0, freq=220.0,
               rate=44100)
    client.post("/api/assets/rescan")
    asset = client.get("/api/assets/samples").json()[0]
    a = client.post(f"/api/assets/{asset['id']}/analyse").json()
    assert a["pitch_range"] is not None
    assert a["pitch_range"]["note"] == "A3"
    assert abs(a["pitch_range"]["frequency"] - 220.0) < 3
    assert a["estimated_key"] == "A"
