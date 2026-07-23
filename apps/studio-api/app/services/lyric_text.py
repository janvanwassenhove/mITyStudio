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


# --- language detection ----------------------------------------------------
# The singing engines need the lyrics' LANGUAGE, not just its text: XTTS
# pronounces with that language's phonetics and a DiffSinger bank picks its
# phoneme dictionary from it. Getting it wrong is catastrophic — Dutch words
# spoken with English phonetics are unintelligible — and the old default of
# "en" silently did exactly that for every song whose language nobody set.
#
# A stopword vote over the four app languages is enough here: lyrics are
# ordinary prose and we only choose between en/nl/fr/de.
_STOPWORDS: dict[str, set[str]] = {
    "nl": {"de", "het", "een", "en", "van", "ik", "je", "niet", "dat", "is",
           "in", "we", "wij", "mijn", "jij", "zijn", "met", "voor", "maar",
           "wat", "als", "ben", "heb", "naar", "ook", "dan", "nog", "zo",
           "hier", "daar", "altijd", "nooit", "samen", "hart", "nacht",
           "licht", "tijd", "weer", "door", "over", "meer", "veel", "zonder"},
    "de": {"der", "die", "das", "und", "ich", "nicht", "ist", "du", "wir",
           "mein", "dein", "mit", "für", "aber", "was", "wenn", "bin",
           "habe", "auch", "dann", "noch", "hier", "immer", "nie", "herz",
           "nacht", "licht", "zeit", "wieder", "über", "mehr", "ohne",
           "sein", "ein", "eine", "sind", "auf"},
    "fr": {"le", "la", "les", "un", "une", "et", "je", "tu", "il", "elle",
           "nous", "vous", "ne", "pas", "est", "mon", "ton", "avec", "pour",
           "mais", "que", "qui", "quand", "suis", "dans", "sur", "aussi",
           "encore", "toujours", "jamais", "coeur", "cœur", "nuit",
           "lumière", "temps", "sans", "plus", "des", "du", "au"},
    "en": {"the", "and", "you", "your", "not", "is", "are", "was", "were",
           "my", "we", "with", "for", "but", "what", "when", "if", "have",
           "also", "then", "still", "here", "there", "always", "never",
           "together", "heart", "night", "light", "time", "again", "over",
           "more", "without", "this", "that", "will", "all", "just"},
}


# Sung filler carries no language signal ("la la la" is not French).
_VOCALISE = {"la", "na", "da", "oh", "ooh", "ah", "aah", "yeah", "hey", "mm",
             "mmm", "doo", "ba", "ooo", "woah", "whoa", "uh", "hm"}

# Words shared by several of the four languages ("de" is Dutch *and* French)
# are noise in the vote — keep only the discriminative ones.
_DISCRIMINATIVE: dict[str, set[str]] = {
    lang: {w for w in words
           if w not in _VOCALISE
           and sum(1 for other in _STOPWORDS.values() if w in other) == 1}
    for lang, words in _STOPWORDS.items()
}


def detect_language(text: str, default: str = "en") -> str:
    """Best guess of the lyrics' language among the app's four, by stopword
    vote. Returns `default` when the text gives no signal (too short, or
    only words shared across languages)."""
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    if not words:
        return default
    scores = {lang: sum(1 for w in words if w in sw)
              for lang, sw in _DISCRIMINATIVE.items()}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return default
    # require a clear win: a tie means we genuinely don't know
    runner = max(v for k, v in scores.items() if k != best)
    return best if scores[best] > runner else default


def resolve_lyrics_language(project, default: str = "en") -> str:
    """The language the singing engines must synthesize in.

    Order: an explicitly stored lyrics language wins; otherwise detect it
    from the actual lyric text. NEVER silently assume English — that made
    XTTS pronounce Dutch words with English phonetics, which is the single
    biggest cause of unintelligible vocals.
    """
    stored = (getattr(getattr(project, "lyrics", None), "language", "") or "").lower()
    lines = getattr(getattr(project, "lyrics", None), "lines", []) or []
    text = " ".join(getattr(l, "text", "") for l in lines)
    if stored and stored != default:
        return stored            # user/LLM said so explicitly — trust it
    detected = detect_language(text, default=stored or default)
    return detected or default
