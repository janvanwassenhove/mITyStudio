"""Phoneme singing, chord-symbol parsing, vision import plumbing,
score upload."""
from __future__ import annotations

import numpy as np
import soundfile as sf

from tests.test_studio_features import _make_voice_project


def test_syllable_parts_and_consonants(workspace):
    from app.services.vocal_engine import (_one_consonant, _render_cluster,
                                           _syllable_parts)

    assert _syllable_parts("straight") == ("str", "a", "ght")
    assert _syllable_parts("sing") == ("s", "i", "ng")
    assert _syllable_parts("oh") == ("", "o", "h")

    rng = np.random.default_rng(1)
    for ch in ("t", "s", "sh", "m", "l", "k"):
        c = _one_consonant(ch, 220.0, rng)
        assert len(c) > 100
        assert abs(np.abs(c).max() - 1.0) < 0.01  # normalized

    cluster = _render_cluster("str", 220.0, rng)
    assert cluster is not None and len(cluster) > 3000
    assert _render_cluster("", 220.0, rng) is None


def test_vocal_render_contains_sibilance(client, workspace):
    """A syllable starting with 's' must add high-frequency energy at note
    onsets — i.e. words get consonants, not just vowels."""
    p, _ = _make_voice_project(client, workspace, with_profile=True)
    proj = client.get(f"/api/projects/{p['id']}").json()
    notes = proj["tracks"][0]["clips"][0]["note_events"]
    notes[0]["lyric_syllable"] = "sun"
    notes[1]["lyric_syllable"] = "shine"
    client.put(f"/api/projects/{p['id']}", json=proj)

    r = client.post(f"/api/projects/{p['id']}/vocals/render").json()
    assert r["errors"] == []
    proj = client.get(f"/api/projects/{p['id']}").json()
    data, rate = sf.read(str(workspace.root / proj["stems"][0]["path"]))
    mono = data.mean(axis=1)

    def hf_ratio(seg):
        spec = np.abs(np.fft.rfft(seg))
        freqs = np.fft.rfftfreq(len(seg), 1 / rate)
        return spec[freqs > 4000].sum() / (spec.sum() + 1e-9)

    onset = mono[: int(0.07 * rate)]              # the 's' of "sun"
    vowel = mono[int(0.25 * rate): int(0.45 * rate)]  # sustained vowel
    assert hf_ratio(onset) > hf_ratio(vowel) * 3  # sibilant onset


def test_chord_symbol_parser(workspace):
    from app.services.score_vision import chord_to_midis

    assert chord_to_midis("C") == [48, 52, 55]
    assert chord_to_midis("Em") == [52, 55, 59]
    assert chord_to_midis("G7") == [55, 59, 62, 65]
    assert chord_to_midis("F#m7") == [54, 57, 61, 64]
    assert chord_to_midis("Bb") == [58, 62, 65]
    assert chord_to_midis("Dsus4") == [50, 55, 57]
    assert chord_to_midis("Adim") == [57, 60, 63]
    assert chord_to_midis("??") is None


def test_vision_import_builds_project(client, workspace, monkeypatch):
    """Vision path with a mocked LLM response — no network needed."""
    (workspace.scores_dir / "sheet.png").write_bytes(b"\x89PNG fake")
    client.post("/api/assets/rescan")
    score = next(s for s in client.get("/api/assets/scores").json()
                 if s["extension"] == ".png")

    from app.services import score_vision
    monkeypatch.setattr(score_vision, "_load_image_bytes",
                        lambda p: (b"img", "image/png"))
    monkeypatch.setattr(score_vision, "extract_song_data", lambda i, m: {
        "title": "Linoleum", "bpm": 168, "key": "E minor",
        "time_signature": "4/4",
        "sections": [
            {"name": "Verse", "chords": ["Em", "C", "G", "D"],
             "lyrics": ["Possessions never meant anything to me"]},
            {"name": "Chorus", "chords": ["C", "D", "Em", "Em"],
             "lyrics": ["And that's okay"]},
        ]})

    r = client.post(f"/api/scores/{score['id']}/import",
                    json={"create_project": True, "title": "From Sheet"})
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["bpm"] == 168
    assert proj["key"] == "E minor"
    assert [s["name"] for s in proj["sections"]] == ["Verse", "Chorus"]
    assert proj["sections"][1]["start_bar"] == 4
    # lyrics present → a singing lead vocal is created automatically
    assert {t["track_type"] for t in proj["tracks"]} == \
        {"guitar", "bass", "lead_vocal"}
    total_notes = sum(len(c["note_events"]) for t in proj["tracks"]
                      for c in t["clips"])
    assert total_notes > 40
    assert any("Possessions" in l["text"] for l in proj["lyrics"]["lines"])
    vocal = next(t for t in proj["tracks"] if t["track_type"] == "lead_vocal")
    assert len(vocal["clips"]) == 2  # one melody per lyric section
    assert any(n["lyric_syllable"] for c in vocal["clips"]
               for n in c["note_events"])


def test_world_singing_resynthesis(workspace):
    """WORLD vocoder path: a spoken vowel is resynthesized ON the target
    notes (continuous curve), silences between notes, rap keeps source pitch."""
    from app.services.sample_analysis import _estimate_pitch
    from app.services.vocal_clone import _world_sing_line

    rate = 24000
    t = np.linspace(0, 1.2, int(1.2 * rate), endpoint=False)
    spoken = (0.4 * np.sin(2 * np.pi * 150 * t)
              + 0.15 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    notes = [{"start": 0.0, "end": 0.5, "freq": 261.6, "syl": "la"},
             {"start": 0.5, "end": 1.0, "freq": 329.6, "syl": "lo"}]

    out = _world_sing_line(spoken, rate, notes, 1.0, 0.0)
    assert len(out) == 44100
    assert np.abs(out).max() > 0.1
    _, f1 = _estimate_pitch(out[2000:18000], 44100)
    _, f2 = _estimate_pitch(out[24000:42000], 44100)
    assert f1 is not None and abs(f1 - 261.6) < 10
    assert f2 is not None and abs(f2 - 329.6) < 10

    # rap mode keeps the natural (source) pitch
    rap = _world_sing_line(spoken, rate, notes, 1.0, 0.0, rap=True)
    _, fr = _estimate_pitch(rap[2000:18000], 44100)
    assert fr is not None and abs(fr - 150) < 12


def test_vocal_melody_one_note_per_syllable(workspace):
    """The clone engine needs exactly one note per syllable — verify the
    dedicated vocal melody generator delivers that, for singing and rap."""
    from app.models.song import Section, SongProject
    from app.services.music_gen import _syllables, generate_vocal_melody

    project = SongProject(title="t", bpm=100, key="G major")
    section = Section(name="V", start_bar=0, length_bars=8)
    project.sections = [section]
    lines = ["Hello darkness my old friend", "I've come to talk with you again"]
    expected = sum(len(_syllables(l)) for l in lines)

    for rap in (False, True):
        clip = generate_vocal_melody(project, section, lines, rap=rap)
        assert len(clip.note_events) == expected, f"rap={rap}"
        assert all(n.lyric_syllable for n in clip.note_events)
        # notes are sequential (no overlaps) and inside the section
        notes = sorted(clip.note_events, key=lambda n: n.start_beat)
        for a, b in zip(notes, notes[1:]):
            assert b.start_beat >= a.start_beat
        assert notes[-1].start_beat + notes[-1].duration_beats <= 32.01
    # rap stays in a tight pitch range
    rap_clip = generate_vocal_melody(project, section, lines, rap=True)
    pitches = [n.midi_note for n in rap_clip.note_events]
    assert max(pitches) - min(pitches) <= 4


def test_sing_lyrics_endpoint(client, workspace):
    from tests.test_projects import make_project
    p = make_project(client)
    # no lyrics yet → clear 422
    assert client.post(f"/api/projects/{p['id']}/vocals/sing-lyrics").status_code == 422

    proj = client.get(f"/api/projects/{p['id']}").json()
    proj["sections"] = [{"name": "Verse", "start_bar": 0, "length_bars": 4},
                        {"name": "Chorus", "start_bar": 4, "length_bars": 4}]
    client.put(f"/api/projects/{p['id']}", json=proj)
    proj = client.get(f"/api/projects/{p['id']}").json()
    for s in proj["sections"]:
        proj["lyrics"]["lines"].append(
            {"section_id": s["id"], "text": f"words for {s['name']}"})
    client.put(f"/api/projects/{p['id']}", json=proj)

    r = client.post(f"/api/projects/{p['id']}/vocals/sing-lyrics").json()
    assert r["sections_sung"] == 2
    assert r["errors"] == []
    proj = client.get(f"/api/projects/{p['id']}").json()
    vocal = next(t for t in proj["tracks"] if t["track_type"] == "lead_vocal")
    assert len(vocal["clips"]) == 2
    # idempotent-ish: re-singing replaces, section count stays covered
    r2 = client.post(f"/api/projects/{p['id']}/vocals/sing-lyrics").json()
    assert r2["sections_sung"] == 2


def test_vision_import_fails_gracefully_without_key(client, workspace, monkeypatch):
    for env in ("OPENAI_API_KEY", "MITY_LLM_API_KEY", "GEMINI_API_KEY",
                "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    (workspace.scores_dir / "photo.jpg").write_bytes(b"\xff\xd8 fake jpeg")
    client.post("/api/assets/rescan")
    score = client.get("/api/assets/scores").json()[0]
    r = client.post(f"/api/scores/{score['id']}/import", json={})
    body = r.json()
    assert body["supported"] is False
    assert any("key" in w.lower() for w in body["warnings"])


def test_score_upload(client, workspace):
    r = client.post("/api/scores/upload",
                    files={"file": ("my chords.png", b"\x89PNG data", "image/png")})
    assert r.status_code == 201, r.text
    asset = r.json()
    assert asset["asset_type"] == "score"
    assert asset["relative_path"].startswith("scores/")
    assert (workspace.root / asset["relative_path"]).exists()
    # bad extension rejected
    assert client.post("/api/scores/upload",
                       files={"file": ("x.exe", b"MZ", "app/x")}).status_code == 422