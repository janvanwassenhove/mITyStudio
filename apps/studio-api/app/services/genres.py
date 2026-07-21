"""Genre engine — the single source of truth for musical style.

Maps a free-text style ("happy bossa nova pop", "Deep House", "pop punk")
onto a canonical genre family with a concrete FEEL SPEC the deterministic
generators consume: groove template, swing, hat subdivision, chord colour,
progression, and a typical tempo range.

Matching is token/substring based (longest keyword first), fixing the old
exact-membership bug where any multi-word style fell through to a generic
pattern. Resolution is lexicon-first so the app stays fully offline-capable;
an LLM producer pass may pin `project.genre` explicitly and that always wins.

The tempo table is also surfaced to the chat planner so `create_song` picks
a bpm that suits the genre (docs/song-quality.md F1/F10).
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GenreProfile:
    family: str                       # canonical id, e.g. "bossa"
    label: str                        # human name for prompts/UI
    groove: str                       # drum groove template id
    tempo: tuple[int, int]            # typical bpm range (lo, hi)
    swing: float = 0.0                # 0 = straight; 0.17 ≈ swung 8ths
    seventh: bool = False             # colour chords with 7ths
    degrees_major: tuple[int, ...] = (0, 3, 4, 0)
    degrees_minor: tuple[int, ...] = (0, 5, 2, 6)
    chord_style: str = "keys"         # keys|power|strum|skank|stab|pad
    bass_style: str = "pop"           # pop|drive|walk|octave|bossa|funk|reggae|half|sparse


# groove ids implemented in music_gen.generate_drums:
#   rock       driving kicks, backbeat 2+4
#   four_floor kick every beat, open-hat offbeats
#   swing      ride swing, cross-stick 2+4, feathered kick
#   bossa      bossa kick pattern + rim clave, light shaker 8ths
#   funk       syncopated 16th kicks, ghosted snare, 16th hats
#   reggae     one drop: kick+rim together on beat 3, offbeat hats
#   halftime   trap/hip-hop: snare on 3 only, rolls, sparse kicks
#   train      country/folk: alternating kick-snare 8ths feel
#   pop        backbeat 2+4 with pickup kicks (default)
#   sparse     ballad/ambient: kick 1, rim 3, minimal motion

_FAMILIES: dict[str, GenreProfile] = {p.family: p for p in [
    GenreProfile("rock", "Rock / Punk / Metal", "rock", (110, 175),
                 degrees_major=(0, 4, 5, 3), chord_style="power",
                 bass_style="drive"),
    GenreProfile("pop", "Pop / Indie", "pop", (95, 125),
                 degrees_major=(5, 3, 0, 4)),
    GenreProfile("dance", "House / Techno / EDM", "four_floor", (118, 132),
                 degrees_major=(5, 3, 0, 4), chord_style="pad",
                 bass_style="octave"),
    GenreProfile("synthwave", "Synthwave / Retrowave", "four_floor", (85, 118),
                 degrees_major=(5, 3, 0, 4), degrees_minor=(0, 5, 3, 6),
                 chord_style="pad", bass_style="octave"),
    GenreProfile("jazz", "Jazz / Blues / Swing", "swing", (100, 160),
                 swing=0.17, seventh=True, degrees_major=(1, 4, 0, 5),
                 bass_style="walk"),
    GenreProfile("bossa", "Bossa / Latin", "bossa", (110, 145),
                 seventh=True, degrees_major=(0, 1, 4, 0),
                 degrees_minor=(0, 3, 6, 0), chord_style="comp",
                 bass_style="bossa"),
    GenreProfile("funk", "Funk / Disco", "funk", (95, 118),
                 seventh=True, degrees_major=(0, 3, 0, 4),
                 chord_style="stab", bass_style="funk"),
    GenreProfile("soul", "Soul / R&B", "pop", (68, 100),
                 seventh=True, degrees_major=(0, 5, 3, 4)),
    GenreProfile("reggae", "Reggae / Ska", "reggae", (68, 96),
                 degrees_major=(0, 3, 4, 3), chord_style="skank",
                 bass_style="reggae"),
    GenreProfile("hiphop", "Hip-hop / Trap", "halftime", (70, 100),
                 degrees_minor=(0, 5, 2, 6), bass_style="half"),
    GenreProfile("country", "Country / Folk", "train", (90, 130),
                 degrees_major=(0, 3, 4, 0), chord_style="strum"),
    GenreProfile("ballad", "Ballad / Singer-songwriter", "sparse", (60, 85),
                 degrees_major=(0, 4, 5, 3), chord_style="keys",
                 bass_style="sparse"),
    GenreProfile("ambient", "Ambient / Cinematic", "sparse", (60, 90),
                 chord_style="pad", bass_style="sparse"),
]}

# keyword → family. Checked longest-first over the normalised style text so
# "pop punk" hits punk (rock) before pop, "deep house" hits house, etc.
_KEYWORDS: dict[str, str] = {
    # rock family
    "punk": "rock", "rock": "rock", "metal": "rock", "grunge": "rock",
    "hardcore": "rock", "emo": "rock",
    # dance family
    "house": "dance", "techno": "dance", "edm": "dance", "electro": "dance",
    "dance": "dance", "trance": "dance", "eurodance": "dance",
    "drum and bass": "dance", "dnb": "dance",
    "synthwave": "synthwave", "retrowave": "synthwave", "vaporwave": "synthwave",
    "new wave": "synthwave", "synthpop": "synthwave", "80s": "synthwave",
    # jazz family
    "jazz": "jazz", "blues": "jazz", "swing": "jazz", "bebop": "jazz",
    "big band": "jazz",
    # latin family
    "bossa": "bossa", "bossa nova": "bossa", "samba": "bossa",
    "latin": "bossa", "salsa": "bossa", "rumba": "bossa", "tango": "bossa",
    # funk / soul
    "funk": "funk", "disco": "funk", "groove": "funk",
    "soul": "soul", "rnb": "soul", "r&b": "soul", "motown": "soul",
    "gospel": "soul", "neo soul": "soul",
    # reggae
    "reggae": "reggae", "ska": "reggae", "dub": "reggae",
    "dancehall": "reggae",
    # hip-hop
    "hip hop": "hiphop", "hiphop": "hiphop", "hip-hop": "hiphop",
    "trap": "hiphop", "rap": "hiphop", "boom bap": "hiphop", "lofi": "hiphop",
    "lo-fi": "hiphop",
    # country / folk
    "country": "country", "folk": "country", "bluegrass": "country",
    "americana": "country", "acoustic": "country", "singer-songwriter": "ballad",
    # ballad / ambient
    "ballad": "ballad", "slow": "ballad",
    "ambient": "ambient", "cinematic": "ambient", "chill": "ambient",
    "soundtrack": "ambient", "orchestral": "ambient", "classical": "ambient",
    # pop
    "pop": "pop", "indie": "pop", "schlager": "pop",
}

# longest keywords first so "bossa nova" wins before "pop" in the same string
_KEYWORDS_ORDERED = sorted(_KEYWORDS, key=len, reverse=True)

_NORM = re.compile(r"[^a-z0-9&\- ]+")


def resolve_family(style: str) -> str:
    """Free-text style → canonical family id ("pop" when nothing matches)."""
    text = _NORM.sub(" ", (style or "").lower())
    text = f" {' '.join(text.split())} "
    for kw in _KEYWORDS_ORDERED:
        if f" {kw} " in text or (len(kw) > 4 and kw in text):
            return _KEYWORDS[kw]
    return "pop"


def profile_for(style: str) -> GenreProfile:
    return _FAMILIES[resolve_family(style)]


def genre_profile(project) -> GenreProfile:
    """The project's genre profile. An explicitly pinned `project.genre`
    (set by the producer pass or the user) wins over free-text resolution."""
    pinned = getattr(project, "genre", "") or ""
    if pinned in _FAMILIES:
        return _FAMILIES[pinned]
    return profile_for(pinned or project.style)


def families() -> list[GenreProfile]:
    return list(_FAMILIES.values())


def suggest_bpm(family: str) -> int:
    p = _FAMILIES.get(family)
    return (p.tempo[0] + p.tempo[1]) // 2 if p else 110


def tempo_table_text() -> str:
    """Genre→tempo guidance block for the planner prompt (generated, so it
    can never drift from the engine)."""
    rows = [f"  {p.label}: {p.tempo[0]}-{p.tempo[1]} bpm ({p.family})"
            for p in _FAMILIES.values()]
    return "\n".join(rows)
