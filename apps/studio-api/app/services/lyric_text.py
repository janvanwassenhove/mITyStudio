"""Language-aware lyric text helpers.

EN/NL/FR/DE all use the Latin alphabet, so one vowel class covering the
accented vowels makes syllabification work across the studio's four
languages (karaoke timing, melody syllable assignment, XTTS pacing).
"""
from __future__ import annotations

import re

VOWELS = "aeiouyàáâäæãåéèêëíìîïóòôöõœøúùûüýÿ"
_V = f"[{VOWELS}]"
_C = f"[^{VOWELS}]"

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ']+")
SYLLABLE_RE = re.compile(f"{_C}*{_V}+(?:{_C}+$)?", re.IGNORECASE)
# onset consonants, first vowel, coda consonants — for phoneme synthesis
SYLLABLE_PARTS_RE = re.compile(f"({_C}*)({_V}){_V}*({_C}*)$")

# accented → base vowel, for formant lookup (German ä sounds like e,
# œ/ö sit between o and e — o keeps them warm)
_BASE = str.maketrans({
    "à": "a", "á": "a", "â": "a", "ä": "e", "æ": "e", "ã": "a", "å": "o",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "ö": "o", "õ": "o", "ø": "o", "œ": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ý": "i", "ÿ": "i",
})


def base_vowel(ch: str) -> str:
    return ch.lower().translate(_BASE)


def word_syllables(word: str) -> list[str]:
    groups = SYLLABLE_RE.findall(word)
    return groups or [word]


def line_syllables(line: str) -> list[str]:
    out: list[str] = []
    for word in WORD_RE.findall(line):
        out.extend(word_syllables(word))
    return out


def syllable_count(text: str) -> int:
    return max(1, len(line_syllables(text)))
