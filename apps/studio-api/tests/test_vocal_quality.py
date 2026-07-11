"""Vocal quality program: lyric-sheet handling, singing fallback, harmony,
auto-sing, sustain mapping, sample-op robustness."""
import numpy as np

from app.models.song import LyricsLine, Section, SongProject, Track
from app.services import operation_applier as oa
from app.services.music_gen import generate_vocal_melody
from app.services.vocal_autofill import ensure_vocal_melodies
from app.services.vocal_clone import _lines_with_notes, _map_syllable_frames


def _project(sections=("Verse", "Chorus")) -> SongProject:
    p = SongProject(title="t", bpm=120)
    bar = 0
    for name in sections:
        p.sections.append(Section(name=name, start_bar=bar, length_bars=4))
        bar += 4
    return p


# --- prefixed lyric sheets are distributed across their sections ------------

def test_prefixed_sheet_is_distributed_by_section_name():
    p = _project(("Verse", "Chorus"))
    oa.op_rewrite_lyrics(p, {"section": "Chorus", "lines": [
        "Verse: first line of the verse",
        "walking through the rain",
        "Chorus: sing it loud",
        "Chorus: sing it louder",
    ]})
    verse, chorus = p.sections
    by_sec = {}
    for l in p.lyrics.lines:
        by_sec.setdefault(l.section_id, []).append(l.text)
    assert by_sec[verse.id] == ["first line of the verse",
                                "walking through the rain"]
    assert by_sec[chorus.id] == ["sing it loud", "sing it louder"]
    # prefixes are stripped from the stored text
    assert not any(":" in t.split()[0] for t in by_sec[chorus.id])


def test_plain_lines_still_go_to_named_section():
    p = _project(("Verse", "Chorus"))
    oa.op_rewrite_lyrics(p, {"section": "Chorus",
                             "lines": ["only chorus words", "nothing prefixed"]})
    chorus = p.sections[1]
    assert all(l.section_id == chorus.id for l in p.lyrics.lines)


# --- singing falls back when lyric sections don't match melodies -------------

def test_lines_with_notes_sequential_fallback():
    p = _project(("Verse", "Chorus"))
    track = Track(name="Lead Vocal", track_type="lead_vocal")
    texts = ["hello sunny sky above", "another line to sing today"]
    for sec, txt in zip(p.sections, texts):
        track.clips.append(generate_vocal_melody(p, sec, [txt]))
    p.tracks.append(track)
    # all lines wrongly assigned to the LAST section (the pomm failure)
    p.lyrics.lines = [LyricsLine(section_id=p.sections[1].id, text=t)
                      for t in texts]
    pairs = _lines_with_notes(p, track)
    assert len(pairs) == 2                       # both lines sing
    assert pairs[0][1][0]["start"] < 4 * 2       # first line lands in Verse


# --- backing vocals sing harmony, not unison ---------------------------------

def test_backing_harmony_above_lead():
    p = _project(("Verse",))
    lines = ["la la la la la la"]
    lead = generate_vocal_melody(p, p.sections[0], lines)
    back = generate_vocal_melody(p, p.sections[0], lines, harmony=True)
    assert len(lead.note_events) == len(back.note_events)
    diffs = [b.midi_note - a.midi_note
             for a, b in zip(lead.note_events, back.note_events)]
    assert all(1 <= d <= 5 for d in diffs)       # diatonic third-ish above
    assert any(d > 0 for d in diffs)


# --- auto-sing fills vocal tracks after chat ----------------------------------

def test_ensure_vocal_melodies_fills_missing_sections():
    p = _project(("Verse", "Chorus"))
    p.tracks.append(Track(name="Vocal Chants", track_type="lead_vocal"))
    p.lyrics.lines = [LyricsLine(section_id=p.sections[1].id,
                                 text="we are one feel the pulse")]
    log = ensure_vocal_melodies(p)
    assert len(log) == 1 and "Chorus" in log[0]
    clips = p.tracks[0].clips
    assert len(clips) == 1 and clips[0].note_events
    # idempotent: second call adds nothing
    assert ensure_vocal_melodies(p) == []


# --- select_sample aimed at a non-sample track lands on a sample lane --------

def test_select_sample_redirects_from_instrument_track(workspace, client):
    from tests.test_sample_analysis import write_tone
    from app.services import asset_repo
    write_tone(workspace.samples_dir / "clap one shot.wav")
    client.post("/api/assets/rescan")
    asset = asset_repo.list_assets("sample")[0]
    p = _project(("Verse",))
    p.tracks.append(Track(name="Drums", track_type="drums"))
    msg = oa.op_select_sample(p, {"sample_asset_id": asset.id,
                                  "track": "Drums"})
    assert "placed sample" in msg
    target = next(t for t in p.tracks if t.clips)
    assert target.track_type == "sample"         # not the drums track


# --- sustain mapping: no slow-motion vowels -----------------------------------

def test_map_syllable_frames_loops_sustains():
    rng = np.random.default_rng(0)
    a, b, span = 100, 120, 300                   # 20 input frames → 300 out
    idx = _map_syllable_frames(a, b, span, rng)
    assert len(idx) == span
    assert idx.min() >= a and idx.max() < b
    onset = idx[:5]
    assert list(onset) == list(range(a, a + 5))  # onset at natural speed
    # the core LOOPS (revisits frames) instead of crawling monotonically
    assert (np.diff(idx.astype(int)) < 0).any()
    # short notes still compress linearly (monotonic)
    short = _map_syllable_frames(a, b, 10, rng)
    assert (np.diff(short.astype(int)) >= 0).all()
