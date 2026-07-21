"""Genre engine + tempo-aware generators (docs/song-quality.md M1)."""
from __future__ import annotations

from app.models.song import Section, SongProject
from app.services import music_gen as mg
from app.services.genres import (families, genre_profile, profile_for,
                                 resolve_family, suggest_bpm)

KICK, SNARE, RIM, HAT = 36, 38, 37, 42


def _drums(style: str, bpm: float = 120, energy: float = 0.7):
    p = SongProject(title="t", style=style, bpm=bpm)
    sec = Section(name="V", start_bar=0, length_bars=4, energy=energy)
    return mg.generate_drums(p, sec).note_events


def _beats(notes, midi_set, before: float = 4.0) -> list[float]:
    # quantize to 16ths BEFORE the range filter: humanized jitter (±0.02
    # beats) can put a beat-4 note at 3.988, which belongs to the next bar
    out = set()
    for n in notes:
        q = round(n.start_beat * 4) / 4
        if n.midi_note in midi_set and q < before:
            out.add(q)
    return sorted(out)


def test_multiword_styles_resolve_to_real_families():
    """The audit's F2 failures: multi-word styles must not fall through."""
    assert resolve_family("happy bossa nova pop") == "bossa"
    assert resolve_family("pop punk") == "rock"
    assert resolve_family("deep house") == "dance"
    assert resolve_family("synthwave") == "synthwave"
    assert resolve_family("trap beat") == "hiphop"
    assert resolve_family("country road song") == "country"
    assert resolve_family("") == "pop"                 # sane default
    assert resolve_family("something unheard of") == "pop"


def test_genres_produce_distinct_grooves():
    """Bossa, trap, reggae, funk and house must be audibly different."""
    bossa = _drums("bossa nova")
    assert 1.5 in _beats(bossa, {KICK})               # surdo "and of 2"
    assert _beats(bossa, {RIM}) == [0.0, 1.5, 3.0]    # 3-side of the clave

    trap = _drums("trap")
    assert _beats(trap, {SNARE}) == [2.0]             # half-time: snare on 3
    assert 1.0 not in _beats(trap, {SNARE})

    reggae = _drums("reggae")
    assert _beats(reggae, {RIM}) == [2.0]             # one drop on beat 3
    assert 0.5 in _beats(reggae, {HAT})               # offbeat skank hats
    assert 0.0 not in _beats(reggae, {HAT})

    house = _drums("deep house")
    assert _beats(house, {KICK}) == [0.0, 1.0, 2.0, 3.0]   # four on the floor

    funk = _drums("funk")
    ghosts = [n for n in funk if n.midi_note == SNARE and n.velocity < 50]
    assert ghosts, "funk needs ghosted snares"


def test_tempo_changes_the_arrangement():
    """F1 fix: bpm must shape the pattern, not just playback speed."""
    slow = [n for n in _drums("pop", bpm=70, energy=0.5) if n.midi_note == HAT]
    fast = [n for n in _drums("pop", bpm=160, energy=0.5) if n.midi_note == HAT]
    assert len(slow) > len(fast)          # slow songs earn 16th hats

    crashes_fast = [n for n in _drums("rock", bpm=175) if n.midi_note == 49]
    crashes_mid = [n for n in _drums("rock", bpm=120) if n.midi_note == 49]
    assert len(crashes_fast) <= len(crashes_mid)   # fills/crashes thin out


def test_pinned_genre_wins_over_style_text():
    p = SongProject(title="t", style="a weird unclassifiable vibe",
                    genre="reggae")
    assert genre_profile(p).family == "reggae"


def test_chord_colour_follows_genre():
    jazz = mg.chord_progression("C major", "smooth jazz", 4)
    pop = mg.chord_progression("C major", "pop", 4)
    assert len(jazz[0]) == 4        # sevenths
    assert len(pop[0]) == 3         # triads


def test_bass_styles_differ_per_genre():
    p_bossa = SongProject(title="t", style="bossa nova", bpm=130)
    p_trap = SongProject(title="t", style="trap", bpm=80)
    sec = Section(name="V", start_bar=0, length_bars=2, energy=0.5)
    bossa = mg.generate_bassline(p_bossa, sec).note_events
    trap = mg.generate_bassline(p_trap, sec).note_events
    # bossa alternates short root/fifth figures; trap holds long 808 roots
    assert max(n.duration_beats for n in trap) > \
        max(n.duration_beats for n in bossa)
    assert len(bossa) > len(trap)


def test_tempo_table_is_sane():
    for prof in families():
        lo, hi = prof.tempo
        assert 40 <= lo < hi <= 200, prof.family
        assert lo <= suggest_bpm(prof.family) <= hi


def test_create_song_pins_genre(client, workspace):
    from app.models.operations import ChatOperation
    from app.services import operation_applier
    project = SongProject(title="t")
    r = operation_applier.apply_operations(project, [
        ChatOperation(op_type="create_song",
                      params={"title": "Beach", "style": "happy bossa nova pop",
                              "bpm": 132})])
    assert r[0].applied
    assert project.genre == "bossa"
    assert "[bossa]" in r[0].summary


def test_deterministic_regeneration():
    """R7: same project + section → identical notes (A/B-able)."""
    p = SongProject(title="t", style="funk", bpm=105)
    sec = Section(name="V", start_bar=0, length_bars=4, energy=0.6)
    a = mg.generate_drums(p, sec).note_events
    b = mg.generate_drums(p, sec).note_events
    assert [(n.midi_note, n.start_beat, n.velocity) for n in a] \
        == [(n.midi_note, n.start_beat, n.velocity) for n in b]
