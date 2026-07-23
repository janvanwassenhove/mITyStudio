"""Lyrics-language resolution — the root cause of unintelligible vocals.

`LyricsDocument.language` defaulted to "en" and nothing ever set it for
lyrics the user typed or imported, so XTTS pronounced Dutch/German words
with English phonetics and DiffSinger banks were asked for the wrong
phoneme dictionary. These tests pin the fix: detect rather than assume.
"""
from __future__ import annotations

from app.models.operations import ChatOperation
from app.models.song import LyricsLine, Section, SongProject
from app.services import operation_applier
from app.services.lyric_text import detect_language, resolve_lyrics_language


def test_detects_the_four_app_languages():
    assert detect_language("ik zing dit mooie lied vanavond samen") == "nl"
    assert detect_language("de nacht is jong en wij staan hier") == "nl"
    assert detect_language("the night is young and we are here") == "en"
    assert detect_language("je chante cette chanson avec toi") == "fr"
    assert detect_language("ich singe dieses lied mit dir heute") == "de"


def test_vocalise_and_empty_text_give_no_false_signal():
    # "la la la" is not French; sung filler must not decide the language
    assert detect_language("la la la") == "en"
    assert detect_language("oh oh yeah") == "en"
    assert detect_language("") == "en"
    assert detect_language("", default="nl") == "nl"


def test_resolver_prefers_explicit_then_detects():
    p = SongProject(title="t")
    p.lyrics.lines = [LyricsLine(section_id="s",
                                 text="ik zing dit lied vanavond samen")]
    # language never set → detected, NOT silently English
    assert p.lyrics.language == "en"          # the misleading default
    assert resolve_lyrics_language(p) == "nl"

    p.lyrics.language = "fr"                  # explicit wins over detection
    assert resolve_lyrics_language(p) == "fr"


def test_rewrite_lyrics_stores_the_language_it_detected(client, workspace):
    p = SongProject(title="t")
    p.sections = [Section(name="Verse", start_bar=0, length_bars=4)]
    r = operation_applier.apply_operations(p, [
        ChatOperation(op_type="rewrite_lyrics", params={
            "section": "Verse",
            "lines": ["ik zing dit lied vanavond",
                      "samen met jou in de nacht"]})])   # no language param
    assert r[0].applied, r[0].error
    assert p.lyrics.language == "nl"

    # an explicit language from the model is always respected
    p2 = SongProject(title="t")
    p2.sections = [Section(name="Verse", start_bar=0, length_bars=4)]
    operation_applier.apply_operations(p2, [
        ChatOperation(op_type="rewrite_lyrics", params={
            "section": "Verse", "lines": ["la la la"], "language": "de"})])
    assert p2.lyrics.language == "de"


def test_engines_resolve_language_instead_of_assuming_english():
    """Both singing engines must go through the resolver — a regression here
    silently reintroduces English phonetics on foreign lyrics."""
    import inspect
    from app.services import svs_engine, vocal_clone
    for mod in (vocal_clone, svs_engine):
        src = inspect.getsource(mod)
        assert "resolve_lyrics_language(project)" in src, mod.__name__
        assert '(project.lyrics.language or "en")' not in src, mod.__name__


def test_bank_language_mismatch_is_warned_not_silently_mangled():
    """A voicebank that cannot sing the lyrics' language must say so — the
    old behaviour fell through to the word-less formant engine."""
    import inspect
    from app.services import vocal_engine
    src = inspect.getsource(vocal_engine.render_vocal_stems)
    assert "does not sing" in src
    assert "select your own voice profile" in src
