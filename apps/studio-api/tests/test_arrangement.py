"""Arrangement dynamics, completeness autofill and metrics (M3)."""
from __future__ import annotations

from app.models.operations import ChatOperation
from app.models.song import Section, SongProject, Track
from app.services import arrangement, arrangement_metrics, operation_applier


def _song(style: str = "pop") -> SongProject:
    p = SongProject(title="t", style=style, bpm=120)
    p.sections = [
        Section(name="Intro", start_bar=0, length_bars=4, energy=0.25),
        Section(name="Verse", start_bar=4, length_bars=8, energy=0.45),
        Section(name="Chorus", start_bar=12, length_bars=8, energy=0.9),
        Section(name="Verse 2", start_bar=20, length_bars=8, energy=0.5),
        Section(name="Chorus 2", start_bar=28, length_bars=8, energy=0.95),
    ]
    return p


def test_instrumentation_varies_with_energy():
    p = _song()
    intro, verse, chorus = p.sections[:3]
    assert not arrangement.plays_in_section("drums", intro, p)
    assert arrangement.plays_in_section("drums", verse, p)
    assert arrangement.plays_in_section("keys", intro, p)     # backbone
    assert not arrangement.plays_in_section("strings", verse, p)
    assert arrangement.plays_in_section("strings", chorus, p)
    # genre nuance: brass earns early entry in funk; a dance synth plays the
    # 0.45-energy verse (a pop synth would not) but sits out true breakdowns
    funk = _song("funk")
    assert arrangement.plays_in_section("brass", funk.sections[1], funk)
    dance = _song("deep house")
    assert arrangement.plays_in_section("synth", dance.sections[1], dance)
    assert not arrangement.plays_in_section("synth", dance.sections[0], dance)
    pop = _song("pop")
    assert not arrangement.plays_in_section("synth", pop.sections[1], pop)


def test_generate_all_respects_the_template(client, workspace):
    """F9 fix: section:"all" no longer puts every instrument everywhere."""
    p = _song()
    r = operation_applier.apply_operations(p, [
        ChatOperation(op_type="generate_drums",
                      params={"section": "all", "track": "Drums"}),
        ChatOperation(op_type="generate_chords",
                      params={"section": "all", "track": "Keys",
                              "track_type": "keys"}),
    ])
    assert all(x.applied for x in r), [x.error for x in r]
    drums = next(t for t in p.tracks if t.name == "Drums")
    keys = next(t for t in p.tracks if t.name == "Keys")
    intro = p.sections[0]
    assert not any(c.section_id == intro.id for c in drums.clips)
    assert any(c.section_id == intro.id for c in keys.clips)
    assert "sits out low-energy" in r[0].summary
    # explicit per-section request is NEVER gated (user intent wins)
    r2 = operation_applier.apply_operations(p, [
        ChatOperation(op_type="generate_drums",
                      params={"section": "Intro", "track": "Drums"})])
    assert r2[0].applied
    assert any(c.section_id == intro.id for c in drums.clips)


def test_fill_new_sections_is_additive_and_template_gated(client, workspace):
    p = _song()
    operation_applier.apply_operations(p, [
        ChatOperation(op_type="generate_drums",
                      params={"section": "all", "track": "Drums"})])
    drums = next(t for t in p.tracks if t.name == "Drums")
    clips_before = list(drums.clips)

    # a new big section arrives → drums extend into it; a new quiet one → not
    bridge = Section(name="Bridge", start_bar=36, length_bars=4, energy=0.7)
    outro = Section(name="Outro", start_bar=40, length_bars=4, energy=0.2)
    p.sections += [bridge, outro]
    lines = arrangement.fill_new_sections(p, {bridge.id, outro.id})
    assert any("Bridge" in ln for ln in lines)
    assert not any("Outro" in ln for ln in lines)
    assert any(c.section_id == bridge.id for c in drums.clips)
    # strictly additive: nothing that existed was replaced or removed
    for c in clips_before:
        assert c in drums.clips
    # empty tracks are a deliberate choice — never filled
    p.tracks.append(Track(name="Empty", track_type="bass"))
    assert arrangement.fill_new_sections(p, {bridge.id}) == []


def test_metrics_flag_incomplete_and_static_songs(client, workspace):
    p = _song()
    operation_applier.apply_operations(p, [
        ChatOperation(op_type="generate_drums",
                      params={"section": "all", "track": "Drums"}),
        ChatOperation(op_type="generate_chords",
                      params={"section": "all", "track": "Keys",
                              "track_type": "keys"}),
        ChatOperation(op_type="generate_bassline",
                      params={"section": "all", "track": "Bass"}),
    ])
    m = arrangement_metrics.analyse(p)
    assert m["completeness"] >= 0.9
    assert m["key_ratio"] > 0.6           # approach notes allowed
    assert not m["static_arrangement"]    # intro lineup differs from chorus
    assert m["is_complete_song"], m["incomplete_reasons"]
    assert "completeness" in arrangement_metrics.summary_line(m)

    # rip out the bass clips → completeness drops and the song is flagged
    bass = next(t for t in p.tracks if t.name == "Bass")
    bass_clip_count = len(bass.clips)
    assert bass_clip_count > 0
    bass.clips = bass.clips[:1]
    m2 = arrangement_metrics.analyse(p)
    assert m2["completeness"] < m["completeness"]

    # a 2-section stub is not "a full song" (R6)
    stub = SongProject(title="s", bpm=120)
    stub.sections = [Section(name="A", start_bar=0, length_bars=2, energy=0.5)]
    m3 = arrangement_metrics.analyse(stub)
    assert not m3["is_complete_song"]
    assert m3["incomplete_reasons"]
