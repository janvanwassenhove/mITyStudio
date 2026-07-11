"""Phase 6: inline lyric editing, melody re-sync, version history."""
from app.models.song import LyricsLine, Section, SongProject, Track
from app.services import lyrics_editing
from app.services.music_gen import generate_vocal_melody


def _project_with_vocals() -> SongProject:
    p = SongProject(title="t", bpm=120)
    sec = Section(name="Verse", start_bar=0, length_bars=4)
    p.sections.append(sec)
    p.lyrics.lines = [LyricsLine(section_id=sec.id, text="hello summer sky"),
                      LyricsLine(section_id=sec.id, text="we are singing now")]
    track = Track(name="Lead Vocal", track_type="lead_vocal")
    clip = generate_vocal_melody(p, sec, [l.text for l in p.lyrics.lines])
    track.clips.append(clip)
    p.tracks.append(track)
    return p


def test_update_line_resyncs_melody_and_snapshots():
    p = _project_with_vocals()
    line = p.lyrics.lines[0]
    old_syls = [n.lyric_syllable for n in p.tracks[0].clips[0].note_events]

    result = lyrics_editing.update_line(p, line.id, "completely different words here")
    assert result["changed"] and result["needs_render"]
    assert result["resynced_clips"] == 1
    new_syls = [n.lyric_syllable for n in p.tracks[0].clips[0].note_events]
    assert new_syls != old_syls
    assert "".join(new_syls).startswith("com")   # new text drives the notes
    # history holds the pre-edit state
    assert len(p.lyrics.history) == 1
    assert p.lyrics.history[0].label == "edit"
    assert p.lyrics.history[0].lines[0].text == "hello summer sky"


def test_update_line_noop_when_unchanged():
    p = _project_with_vocals()
    line = p.lyrics.lines[0]
    result = lyrics_editing.update_line(p, line.id, line.text)
    assert not result["changed"]
    assert not p.lyrics.history


def test_restore_version_round_trip():
    p = _project_with_vocals()
    line = p.lyrics.lines[0]
    lyrics_editing.update_line(p, line.id, "changed words entirely")
    version = p.lyrics.history[0]

    result = lyrics_editing.restore_version(p, version.id)
    assert result["lines"] == 2 and result["needs_render"]
    assert p.lyrics.lines[0].text == "hello summer sky"
    syls = [n.lyric_syllable for n in p.tracks[0].clips[0].note_events]
    assert "".join(syls).startswith("hel")
    # the pre-restore state was snapshotted too
    assert [v.label for v in p.lyrics.history] == ["edit", "restore"]


def test_history_capped():
    p = _project_with_vocals()
    line = p.lyrics.lines[0]
    for i in range(lyrics_editing.HISTORY_CAP + 5):
        lyrics_editing.update_line(p, line.id, f"version number {i} words")
    assert len(p.lyrics.history) == lyrics_editing.HISTORY_CAP
