"""Phase 4 i18n: language-aware planning prompt and syllabification."""
from app.models.song import SongProject
from app.services import lyric_text
from app.services.operation_planner import build_system_prompt


def test_prompt_carries_reply_language():
    p = SongProject(title="t")
    assert "Dutch" in build_system_prompt(p, "nl")
    assert "French" in build_system_prompt(p, "fr")
    assert "German" in build_system_prompt(p, "de")
    assert "English" in build_system_prompt(p, "en")
    assert "English" in build_system_prompt(p, "xx")   # unknown → fallback


def test_accented_syllables_nl_fr_de():
    # Dutch: zo-mer-a-vond (compound, vowel groups); één has accents
    assert len(lyric_text.line_syllables("zomeravond")) == 4
    assert lyric_text.syllable_count("één") == 1
    # French: été = é-té, cœur = 1
    assert lyric_text.syllable_count("été") == 2
    assert lyric_text.syllable_count("cœur") == 1
    # German: schöner = schö-ner, Träume = Träu-me
    assert lyric_text.syllable_count("schöner") == 2
    assert lyric_text.syllable_count("Träume") == 2
    # English regression
    assert lyric_text.syllable_count("straight") == 1
    assert lyric_text.syllable_count("melody") == 3


def test_base_vowel_mapping():
    assert lyric_text.base_vowel("é") == "e"
    assert lyric_text.base_vowel("ü") == "u"
    assert lyric_text.base_vowel("ä") == "e"   # German ä sounds like e
    assert lyric_text.base_vowel("a") == "a"
