"""Message-aware asset retrieval for the chat planner (deterministic RAG).

The planner cannot ship 967 presets + 2969 samples in its context, and a
fixed slice (the previous approach) meant chat literally did not know most of
the library. This module retrieves the assets RELEVANT to the current request
from the SQLite registry + analysis cache:

- a global SUMMARY so the model knows the shape of the full inventory
  (categories + counts — it can say "I have 71 drum kits" without seeing all)
- top-K instruments/samples scored against the user's message + the
  project's genre/bpm/key, with per-category coverage guarantees so a full
  song can always be orchestrated.

Plain keyword/metadata scoring, no embeddings: asset names, categories,
tags and analysis fields are short structured strings — lexical match with
musical constraints (bpm ±3, key compatibility) beats vector similarity here
and costs nothing.
"""
from __future__ import annotations

import re

from ..models.song import SongProject
from . import asset_repo

import numpy as np

_WORD = re.compile(r"[a-zà-ÿ0-9']+")

# NL/FR/DE music vocabulary → the English words asset metadata uses. The
# user chats in their language; filenames/tags are English — bridge cheaply.
_SYNONYMS = {
    "gitaar": ["guitar"], "gitarre": ["guitar"], "guitare": ["guitar"],
    "slagwerk": ["drums", "percussion"], "schlagzeug": ["drums"],
    "batterie": ["drums"], "drumstel": ["drums"],
    "bas": ["bass"], "basse": ["bass"],
    "zang": ["vocals", "voice"], "stem": ["vocals", "voice"],
    "gesang": ["vocals"], "stimme": ["vocals", "voice"],
    "voix": ["vocals", "voice"], "chant": ["vocals"],
    "strijkers": ["strings"], "streicher": ["strings"], "cordes": ["strings"],
    "blazers": ["brass"], "bläser": ["brass"], "cuivres": ["brass"],
    "fluit": ["flute"], "flöte": ["flute"], "flûte": ["flute"],
    "koor": ["choir"], "chor": ["choir"], "choeur": ["choir"],
    "chœur": ["choir"],
    "klavier": ["piano", "keys"], "toetsen": ["keys", "piano"],
    "lus": ["loop"], "boucle": ["loop"], "schleife": ["loop"],
    "trom": ["drum"], "trommel": ["drum", "percussion"],
    "handtrommel": ["conga", "percussion"],
    "vrolijk": ["happy", "upbeat"], "fröhlich": ["happy", "upbeat"],
    "joyeux": ["happy", "upbeat"], "rustig": ["calm", "mellow"],
    "ruhig": ["calm", "mellow"], "calme": ["calm", "mellow"],
    "snel": ["fast"], "schnell": ["fast"], "rapide": ["fast"],
    "langzaam": ["slow"], "langsam": ["slow"], "lent": ["slow"],
}

# genre / vibe keywords → instrument-category hints (boost fitting presets)
_GENRE_HINTS = {
    "rock": ["guitar", "overdrive", "distortion", "drum"],
    "punk": ["overdrive", "distortion", "drum"],
    "metal": ["distortion", "drum"],
    "jazz": ["upright", "sax", "brass", "piano", "ride"],
    "blues": ["guitar", "organ", "piano"],
    "pop": ["piano", "keys", "pad", "synth", "drum"],
    "edm": ["synth", "pad", "lead", "bass", "drum"],
    "house": ["synth", "pad", "bass", "drum"],
    "techno": ["synth", "lead", "drum"],
    "hip": ["drum", "bass", "synth"],
    "rap": ["drum", "bass", "synth"],
    "country": ["guitar", "banjo", "fiddle", "steel"],
    "folk": ["guitar", "accordion", "flute"],
    "classical": ["strings", "violin", "cello", "orchestra", "piano"],
    "orchestral": ["strings", "brass", "orchestra", "timpani"],
    "ballad": ["piano", "strings", "pad"],
    "reggae": ["organ", "guitar", "bass"],
    "latin": ["conga", "bongo", "brass", "nylon"],
    "funk": ["bass", "brass", "clav", "guitar"],
    "soul": ["organ", "piano", "brass"],
    "ambient": ["pad", "strings", "choir"],
}

# longest alternatives first — "m" before "major" would eat its first letter
_KEY_RE = re.compile(r"^([A-G][#b]?)\s*(minor|major|min|maj|m)?\b",
                     re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall((text or "").lower()) if len(t) > 2}


def _hint_words(message: str, project: SongProject) -> set[str]:
    """Query vocabulary: message words + project genre words + genre hints
    + cross-language synonyms (Dutch/French/German → English metadata)."""
    words = _tokens(message) | _tokens(project.style or "")
    for w in list(words):
        words.update(_SYNONYMS.get(w, ()))
    for g, hints in _GENRE_HINTS.items():
        if g in words or any(g in w for w in words):
            words.update(hints)
    return words


def _key_root_minor(key: str | None) -> tuple[str, bool] | None:
    m = _KEY_RE.match((key or "").strip())
    if not m:
        return None
    root = m.group(1)[0].upper() + m.group(1)[1:]        # e.g. "F#", "Bb"
    quality = (m.group(2) or "").lower()
    return root, quality.startswith("m") and not quality.startswith("maj")


_NOTE_INDEX = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
               "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
               "A#": 10, "Bb": 10, "B": 11}


def _keys_compatible(song_key: str | None, sample_key: str | None) -> bool:
    """Same key, or relative major/minor. Unknown keys count as compatible
    (the planner prompt still tells the model the rule)."""
    a, b = _key_root_minor(song_key), _key_root_minor(sample_key)
    if a is None or b is None:
        return True
    (ra, ma), (rb, mb) = a, b
    ia, ib = _NOTE_INDEX.get(ra), _NOTE_INDEX.get(rb)
    if ia is None or ib is None:
        return True
    if ia == ib and ma == mb:
        return True
    # relative pair: minor root is 9 semitones above its relative major
    if ma != mb:
        major, minor = (ib, ia) if ma else (ia, ib)
        return (major + 9) % 12 == minor
    return False


def summary() -> dict:
    """Global inventory shape — cheap, lets the model reason about what
    exists beyond the retrieved slice."""
    from .sf2_parser import instrument_catalog
    cats = [{"category": c["category"], "presets": len(c["presets"])}
            for c in instrument_catalog()]
    samples = asset_repo.list_assets("sample", include_missing=False)
    analysed = sum(1 for a in samples if a.analysis_status == "analysed")
    return {
        "instrument_categories": cats,
        "total_presets": sum(c["presets"] for c in cats),
        "total_samples": len(samples),
        "analysed_samples": analysed,
        "total_scores": len(asset_repo.list_assets(
            "score", include_missing=False)),
    }


def retrieve_instruments(message: str, project: SongProject,
                         limit: int = 40) -> list[dict]:
    """Top presets scored against the request, with guaranteed coverage of
    the core band categories so full-song orchestration always has options."""
    from .sf2_parser import instrument_catalog
    words = _hint_words(message, project)

    scored: list[tuple[float, dict]] = []
    per_cat: dict[str, list[dict]] = {}
    for cat in instrument_catalog():
        cat_l = cat["category"].lower()
        cat_words = _tokens(cat_l)
        for p in cat["presets"]:
            label_words = _tokens(p["label"])
            score = 2.0 * len(words & label_words) + len(words & cat_words)
            entry = {"category": cat["category"], "preset": p["label"],
                     "soundfont_asset_id": p["asset_id"],
                     "bank": p["bank"], "program": p["program"]}
            if score > 0:
                scored.append((score, entry))
            per_cat.setdefault(cat["category"], [])
            if len(per_cat[cat["category"]]) < 3:
                per_cat[cat["category"]].append(entry)

    scored.sort(key=lambda t: -t[0])
    out: list[dict] = []
    seen: set[tuple] = set()

    def add(e: dict):
        k = (e["soundfont_asset_id"], e["bank"], e["program"])
        if k not in seen:
            seen.add(k)
            out.append(e)

    for _s, e in scored[:limit // 2]:
        add(e)
    # coverage: a few presets from every category (drums, bass, keys… always
    # present even when the message mentions none of them)
    for entries in per_cat.values():
        for e in entries:
            if len(out) >= limit:
                return out
            add(e)
    return out[:limit]


def retrieve_samples(message: str, project: SongProject,
                     limit: int = 48) -> list[dict]:
    """Samples that actually FIT: scored by keyword match + bpm proximity +
    key compatibility + vocal/type metadata + CLAP semantic similarity
    (what the sample SOUNDS like vs what the user asked for). Mismatched-bpm
    loops sink."""
    from . import sample_analysis
    words = _hint_words(message, project)
    bpm = float(project.bpm or 0)

    scored: list[tuple[float, dict]] = []
    embeds: list[tuple[int, list[float]]] = []   # (index in scored, embedding)
    for a in asset_repo.list_assets("sample", include_missing=False):
        analysis = sample_analysis.get_analysis(a.id) or {}
        tags = [*(a.tags or []), *(analysis.get("vibe_tags") or [])]
        text_words = _tokens(a.filename) | _tokens(" ".join(tags))
        score = 1.5 * len(words & text_words)
        if analysis:
            score += 0.5   # analysed samples carry data the model can use

        s_bpm = analysis.get("estimated_bpm")
        loopable = bool(analysis.get("loopability_estimate"))
        if s_bpm and bpm:
            diff = abs(float(s_bpm) - bpm)
            half = abs(float(s_bpm) / 2 - bpm)
            dbl = abs(float(s_bpm) * 2 - bpm)
            best = min(diff, half, dbl)
            if best <= 3:
                score += 3.0
            elif loopable:
                score -= 2.5   # a mismatched loop is worse than nothing
        if not _keys_compatible(project.key,
                                analysis.get("estimated_key")):
            score -= 2.0
        # no hard filter: penalties RANK bad fits down. Small libraries stay
        # fully visible; at scale the limit keeps only the best matches.
        entry: dict = {"id": a.id, "filename": a.filename,
                       "tags": list(dict.fromkeys(tags))[:8]}
        for k_src, k_dst in (("estimated_bpm", "bpm"),
                             ("estimated_key", "key"),
                             ("sound_type_guess", "type"),
                             ("loopability_estimate", "loopable"),
                             ("has_vocals", "vocals"),
                             ("is_acapella", "acapella"),
                             ("content_tags", "sounds_like")):
            if analysis.get(k_src) is not None:
                entry[k_dst] = analysis[k_src]
        if analysis.get("clap_embedding"):
            embeds.append((len(scored), analysis["clap_embedding"]))
        scored.append((score, entry))

    # semantic term: rank by what the audio SOUNDS like. Only when the
    # library already carries CLAP embeddings (batch analysis ran) — a chat
    # message must never trigger the model download itself.
    if embeds and message.strip():
        from . import audio_tagging
        qvec = (audio_tagging.embed_text(message)
                if audio_tagging.available() else None)
        if qvec is not None:
            q = np.asarray(qvec)
            for idx, emb in embeds:
                cos = float(np.asarray(emb) @ q)
                s, e = scored[idx]
                scored[idx] = (s + 4.0 * max(cos, 0.0), e)

    scored.sort(key=lambda t: -t[0])
    return [e for _s, e in scored[:limit]]
