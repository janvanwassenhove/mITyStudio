"""Deterministic mixing, song endings, and the sample tempo guard.

All three come from the same report: generated songs were flat, stopped
abruptly, and samples were placed without regard for tempo.
"""
from __future__ import annotations

import pytest

from app.models.operations import ChatOperation
from app.models.song import Clip, Section, SongProject, Track
from app.services import mixing, operation_applier


def _song() -> SongProject:
    p = SongProject(title="t", style="pop", bpm=120)
    p.sections = [
        Section(name="Intro", start_bar=0, length_bars=4, energy=0.3),
        Section(name="Chorus", start_bar=4, length_bars=8, energy=0.9),
        Section(name="Outro", start_bar=12, length_bars=4, energy=0.35),
    ]
    for name, tt in (("Drums", "drums"), ("Bass", "bass"), ("Keys", "keys"),
                     ("Lead Vocal", "lead_vocal")):
        t = Track(name=name, track_type=tt)
        for s in p.sections:
            t.clips.append(Clip(section_id=s.id, clip_type="midi",
                                start_beat=s.start_bar * 4,
                                duration_beats=s.length_bars * 4))
        p.tracks.append(t)
    return p


def test_mix_gives_each_role_its_own_level_and_space():
    p = _song()
    mixing.apply_default_mix(p)
    by = {t.name: t for t in p.tracks}
    # the voice sits on top of the bed
    assert by["Lead Vocal"].volume > by["Keys"].volume
    # low end and the voice stay centred; chordal beds get width
    assert by["Bass"].pan == 0.0 and by["Lead Vocal"].pan == 0.0
    assert by["Keys"].pan != 0.0
    # effects that earn their place — and no stacking
    vocal_fx = [e.effect_type for e in by["Lead Vocal"].effects.effects]
    assert "compressor" in vocal_fx and "reverb" in vocal_fx
    assert len(vocal_fx) <= 2
    assert [e.effect_type for e in by["Bass"].effects.effects] == ["compressor"]
    assert by["Drums"].effects.effects == []      # drums need none by default


def test_remixing_is_idempotent_and_keeps_user_effects():
    p = _song()
    vocal = next(t for t in p.tracks if t.track_type == "lead_vocal")
    from app.models.song import Effect
    vocal.effects.effects.append(Effect(effect_type="delay",
                                        params={"mix": 0.3}))
    mixing.apply_default_mix(p)
    first = len(vocal.effects.effects)
    mixing.apply_default_mix(p)                    # re-mix must not stack
    assert len(vocal.effects.effects) == first
    # the hand-added effect survives both passes
    assert any(e.effect_type == "delay" and not e.params.get("auto_mix")
               for e in vocal.effects.effects)


def test_ending_fades_the_last_section_out_and_the_first_in():
    p = _song()
    lines = mixing.apply_ending(p)
    assert lines
    intro, outro = p.sections[0], p.sections[-1]
    for t in p.tracks:
        first = next(c for c in t.clips if c.section_id == intro.id)
        last = next(c for c in t.clips if c.section_id == outro.id)
        assert first.fade_in_seconds > 0, "song starts abruptly"
        assert last.fade_out_seconds > 0, "song still stops abruptly"
        # the fade must be musical, not a click
        assert last.fade_out_seconds >= 1.0
    # middle sections are untouched — only the ends are shaped
    mid = p.sections[1]
    assert all(c.fade_out_seconds == 0
               for t in p.tracks for c in t.clips if c.section_id == mid.id)


def test_ops_expose_mix_and_ending_to_chat(client, workspace):
    p = _song()
    r = operation_applier.apply_operations(p, [
        ChatOperation(op_type="auto_mix", params={}),
        ChatOperation(op_type="finalize_ending", params={}),
    ])
    assert all(x.applied for x in r), [x.error for x in r]
    assert "mixed" in r[0].summary
    assert "fade-out" in r[1].summary
    # an empty project fails cleanly instead of pretending it worked
    empty = SongProject(title="e")
    r2 = operation_applier.apply_operations(empty, [
        ChatOperation(op_type="auto_mix", params={})])
    assert not r2[0].applied


def test_looped_sample_must_match_the_song_tempo(client, workspace):
    """A looped sample is grid-locked, so a wrong tempo audibly drifts —
    reject it at placement instead of trusting the model's judgement."""
    from app.services import asset_repo, sample_analysis
    from tests.test_sample_analysis import write_tone

    write_tone(workspace.samples_dir / "loop90.wav", seconds=1.0)
    client.post("/api/assets/rescan")
    asset = next(a for a in asset_repo.list_assets("sample")
                 if a.filename == "loop90.wav")
    sample_analysis._store(asset.id, {"estimated_bpm": 90.0,
                                      "estimated_key": "C major"})

    p = SongProject(title="t", bpm=128)
    r = operation_applier.apply_operations(p, [
        ChatOperation(op_type="select_sample",
                      params={"sample_asset_id": asset.id, "loop": True})])
    assert not r[0].applied
    assert "90" in (r[0].error or "") and "128" in (r[0].error or "")

    # the same sample as a ONE-SHOT is tempo-free and allowed
    r2 = operation_applier.apply_operations(p, [
        ChatOperation(op_type="select_sample",
                      params={"sample_asset_id": asset.id, "loop": False})])
    assert r2[0].applied, r2[0].error

    # half/double time counts as a match: a 90 BPM loop fits a 180 BPM song
    p2 = SongProject(title="t", bpm=180)
    r3 = operation_applier.apply_operations(p2, [
        ChatOperation(op_type="select_sample",
                      params={"sample_asset_id": asset.id, "loop": True})])
    assert r3[0].applied, r3[0].error


def test_pipeline_polishes_before_rendering():
    """The mix/ending pass must run in the pipeline, not be left to the
    critic (which only fires when metrics flag a problem)."""
    import inspect
    from app.services import song_pipeline
    src = inspect.getsource(song_pipeline)
    assert "mixing.finalize_song(project)" in src
    assert src.index("mixing.finalize_song") < src.index('stage="rendering"')
