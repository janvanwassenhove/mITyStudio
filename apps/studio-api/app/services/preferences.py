"""Learned preferences — the agent gets better at fitting THIS user.

Honest, local, deterministic learning: we do not let the model tune itself.
Instead we watch what the user actually keeps and edits, distil it into a
few numbers, and feed those back into the deterministic generators.

What is learned, and from where:
- **Mix taste** — a slow EMA of the volume the user settles on per track
  role. If they always push the lead vocal up, the auto-mix learns to start
  it there.
- **Asset taste** — how often each SoundFont / synth patch / sample actually
  ends up in a saved project, per genre. Used to bias instrument retrieval
  toward the things this user reaches for.
- Observations come ONLY from user-initiated saves (the PUT route), never
  from the pipeline's own internal saves — otherwise we would just relearn
  our own generated defaults.

Everything lives in one small JSON in the analysis cache; a corrupt or
missing file degrades to "no preferences yet", never an error.
"""
from __future__ import annotations

import json
import logging
import threading

from ..config import get_config
from ..models.song import SongProject

log = logging.getLogger(__name__)

_EMA = 0.2          # weight of each new observation (slow, robust to outliers)
_lock = threading.Lock()
_cache: dict | None = None

_INSTRUMENT_TYPES = {"drums", "bass", "guitar", "keys", "synth", "strings",
                     "brass", "fx"}


def _path():
    return get_config().analysis_cache_dir / "preferences.json"


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        _cache = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _cache = {"role_volume": {}, "assets": {}, "genres": {}, "saves": 0}
    _cache.setdefault("role_volume", {})
    _cache.setdefault("assets", {})
    _cache.setdefault("genres", {})
    _cache.setdefault("saves", 0)
    return _cache


def _save(data: dict) -> None:
    try:
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        log.warning("could not persist preferences")


def reset() -> None:
    """Drop the in-memory cache (tests / after an external edit)."""
    global _cache
    with _lock:
        _cache = None


def observe(project: SongProject) -> None:
    """Learn from a user-saved project. Cheap; never raises."""
    try:
        content = [t for t in project.tracks
                   if any(c.note_events or c.source_asset_id
                          for c in t.clips)]
        if not content:
            return            # an empty/stub project teaches us nothing
        from .genres import genre_profile
        genre = genre_profile(project).family
        with _lock:
            data = _load()
            data["saves"] += 1
            rv = data["role_volume"]
            assets = data["assets"].setdefault(genre, {})
            for t in content:
                # mix taste: EMA of the level the user keeps for this role
                prev = rv.get(t.track_type)
                rv[t.track_type] = (t.volume if prev is None
                                    else round((1 - _EMA) * prev
                                               + _EMA * t.volume, 4))
                # asset taste, per genre
                cfg = t.instrument_config
                for key in (f"sf:{cfg.soundfont_asset_id}"
                            if cfg.soundfont_asset_id else None,
                            f"synth:{cfg.synth_patch}"
                            if cfg.synth_patch else None):
                    if key:
                        assets[key] = assets.get(key, 0) + 1
                for c in t.clips:
                    if c.source_asset_id:
                        k = f"sample:{c.source_asset_id}"
                        assets[k] = assets.get(k, 0) + 1
            data["genres"][genre] = data["genres"].get(genre, 0) + 1
            _save(data)
    except Exception as e:  # noqa: BLE001 — learning must never break a save
        log.debug("preferences.observe skipped: %s", e)


def role_volume(track_type: str, fallback: float) -> float:
    """The level to start this role at — the learned taste eased toward the
    built-in default so a couple of odd saves can't wreck the mix."""
    learned = _load()["role_volume"].get(track_type)
    if learned is None:
        return fallback
    return round(0.5 * learned + 0.5 * fallback, 4)


def preferred_assets(genre: str, prefix: str, limit: int = 8) -> list[str]:
    """Asset ids of `prefix` kind (sf/synth/sample) this user reaches for in
    this genre, most-used first."""
    counts = _load()["assets"].get(genre, {})
    hits = [(k[len(prefix) + 1:], n) for k, n in counts.items()
            if k.startswith(prefix + ":")]
    return [k for k, _ in sorted(hits, key=lambda x: -x[1])[:limit]]


def asset_boost(genre: str, asset_id: str) -> float:
    """A small retrieval bonus for an asset this user favours (0 when
    unseen). Capped so taste nudges ranking without dominating fit."""
    counts = _load()["assets"].get(genre, {})
    n = counts.get(f"sf:{asset_id}", 0) + counts.get(f"sample:{asset_id}", 0)
    return min(1.5, 0.4 * n)


def summary() -> dict:
    d = _load()
    return {"saves_learned_from": d["saves"],
            "role_volume": d["role_volume"],
            "genres": d["genres"]}


# --- learning from mistakes -------------------------------------------------

def recurring_issues(limit: int = 3) -> list[str]:
    """The problems the improvement loop has had to fix most often across
    recent songs, so the producer can pre-empt them. Read straight from the
    pipeline ledger — the same measured signal, aggregated over time."""
    import collections
    path = get_config().analysis_cache_dir / "song-pipeline.jsonl"
    if not path.exists():
        return []
    tally: collections.Counter = collections.Counter()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-40:]
    except OSError:
        return []
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        m = rec.get("metrics", {})
        if not m.get("is_complete_song", True):
            tally["songs came out incomplete — make sure every section is "
                  "filled and the song is long enough"] += 1
        if m.get("static_arrangement"):
            tally["arrangements were static — vary which instruments play "
                  "per section"] += 1
        if (rec.get("score") or 1) < 0.85:
            tally["overall quality was low — aim for full, in-key, dynamic "
                  "arrangements"] += 1
    return [msg for msg, _ in tally.most_common(limit)]
