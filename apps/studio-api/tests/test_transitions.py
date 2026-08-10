"""Section transitions + intra-section dynamics.

The report was that songs sound artificial and "not joined up": every part
stopped dead on the section line and each section sat at one intensity.
These pin the two fixes and, just as importantly, that the agents can see
and act on them (op + scored metric).
"""
from __future__ import annotations

from app.models.song import Section, SongProject, Track
from app.services import arrangement_metrics as am
from app.services import music_gen, transitions


def _song(bars: int = 8) -> SongProject:
    """Verse → Chorus (a clear lift) → Outro."""
    p = SongProject(title="t", style="pop", bpm=120, key="C major")
    p.sections = [
        Section(name="Verse", start_bar=0, length_bars=bars, energy=0.45),
        Section(name="Chorus", start_bar=bars, length_bars=bars, energy=0.9),
        Section(name="Outro", start_bar=bars * 2, length_bars=4, energy=0.4),
    ]
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


# --- intra-section dynamics ------------------------------------------------

def test_velocity_builds_across_a_section():
    """A section that sits at one intensity reads as a loop, not a take."""
    p = _song()
    sec = p.sections[0]
    clip = music_gen.generate_chords(p, sec)
    notes = sorted(clip.note_events, key=lambda n: n.start_beat)
    first = sum(n.velocity for n in notes[:6]) / 6
    last = sum(n.velocity for n in notes[-6:]) / 6
    assert last > first + 5, f"no build: {first:.0f} -> {last:.0f}"


def test_section_arc_stays_musical():
    """The arc must be a shaping, not a volume ramp that guts the start."""
    assert 0.9 <= music_gen._section_arc(0.0) <= 0.95
    assert 1.05 <= music_gen._section_arc(1.0) <= 1.12
    # monotonically rising
    vals = [music_gen._section_arc(i / 10) for i in range(11)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))


# --- transitions -----------------------------------------------------------

def test_notes_ring_over_the_section_boundary():
    p = _song()
    bpb = p.beats_per_bar
    verse_end = p.sections[0].length_bars * bpb
    keys = next(t for t in p.tracks if t.track_type == "keys")
    clip = next(c for c in keys.clips if c.section_id == p.sections[0].id)
    assert all(c.start_beat + n.start_beat + n.duration_beats <= verse_end + 0.01
               for c in [clip] for n in clip.note_events), "already ringing over"

    transitions.apply_transitions(p)
    over = [n for n in clip.note_events
            if clip.start_beat + n.start_beat + n.duration_beats > verse_end + 0.05]
    assert over, "nothing rings over the boundary"
    # tails are existing notes we lengthened, so they carry no marker — the
    # audible property is what matters, and it must stay bounded
    assert all(clip.start_beat + n.start_beat + n.duration_beats
               <= verse_end + transitions._MAX_TAIL_BEATS + 0.01 for n in over)


def test_pickup_and_crash_announce_a_lift():
    p = _song()
    transitions.apply_transitions(p)
    verse, chorus = p.sections[0], p.sections[1]
    drums = next(t for t in p.tracks if t.track_type == "drums")
    verse_clip = next(c for c in drums.clips if c.section_id == verse.id)
    chorus_clip = next(c for c in drums.clips if c.section_id == chorus.id)

    pickups = [n for n in verse_clip.note_events
               if n.articulation == transitions.PICKUP]
    assert len(pickups) == 4, "expected a four-stroke fill into the chorus"
    # it sits in the final beat, and rises
    assert all(n.start_beat >= verse_clip.duration_beats - 1.01 for n in pickups)
    vels = [n.velocity for n in sorted(pickups, key=lambda n: n.start_beat)]
    assert vels == sorted(vels), f"pickup should build: {vels}"

    # the downbeat of the lift is landed
    assert any(n.midi_note == transitions.CRASH and n.start_beat < 0.1
               for n in chorus_clip.note_events)

    # a bass walk-up leads in too
    bass = next(t for t in p.tracks if t.track_type == "bass")
    bass_clip = next(c for c in bass.clips if c.section_id == verse.id)
    assert any(n.articulation == transitions.PICKUP
               for n in bass_clip.note_events)


def test_no_pickup_into_a_section_that_drops():
    """Chorus → Outro loses energy: announcing it would be wrong."""
    p = _song()
    transitions.apply_transitions(p)
    drums = next(t for t in p.tracks if t.track_type == "drums")
    chorus_clip = next(c for c in drums.clips if c.section_id == p.sections[1].id)
    assert not any(n.articulation == transitions.PICKUP
                   for n in chorus_clip.note_events)


def test_transitions_are_idempotent():
    """Running twice must replace our additions, never stack them."""
    p = _song()
    transitions.apply_transitions(p)
    counts = [len(c.note_events) for t in p.tracks for c in t.clips]
    transitions.apply_transitions(p)
    assert [len(c.note_events) for t in p.tracks for c in t.clips] == counts


def test_user_and_generator_notes_are_never_removed():
    p = _song()
    keys = next(t for t in p.tracks if t.track_type == "keys")
    clip = keys.clips[0]
    original = {(n.midi_note, n.start_beat) for n in clip.note_events}
    transitions.apply_transitions(p)
    transitions.apply_transitions(p)
    still = {(n.midi_note, n.start_beat) for n in clip.note_events}
    assert original <= still, "a generator/user note went missing"


# --- the agents can see and act on it --------------------------------------

def test_transitions_are_a_scored_dimension():
    """The improvement loop must be able to chase this, not just humans."""
    p = _song()
    before = am.score(am.analyse(p), p)
    assert before["dimensions"]["transitions"] == 0.0
    assert "transitions" in before["weakest"]

    transitions.apply_transitions(p)
    after = am.score(am.analyse(p), p)
    assert after["dimensions"]["transitions"] > 0.9
    assert after["score"] > before["score"]
    assert "transitions" not in after["weakest"]


def test_chat_can_ask_for_it(client, workspace):
    from app.models.operations import ChatOperation
    from app.services import operation_applier
    p = _song()
    r = operation_applier.apply_operations(p, [
        ChatOperation(op_type="glue_sections", params={})])
    assert r[0].applied, r[0].error
    assert "ring over" in r[0].summary or "pickups" in r[0].summary

    # a one-section stub fails cleanly rather than pretending
    stub = SongProject(title="s")
    stub.sections = [Section(name="A", start_bar=0, length_bars=4)]
    r2 = operation_applier.apply_operations(stub, [
        ChatOperation(op_type="glue_sections", params={})])
    assert not r2[0].applied


def test_pipeline_glues_before_rendering():
    import inspect
    from app.services import song_pipeline
    src = inspect.getsource(song_pipeline)
    assert "transitions.apply_transitions(project)" in src
    assert src.index("apply_transitions") < src.index('stage="rendering"')
