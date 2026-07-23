"""Deterministic mixing + song ending (docs/song-quality.md).

Two things a freshly generated song was missing, both because they were
gated behind the LLM critic that only fires when metrics flag a problem — a
"structurally complete" song therefore got neither:

- **A mix.** Every track defaulted to unity gain, dead-centre, no effects,
  so the vocal fought the band and nothing had space. `apply_default_mix`
  gives each track a level and pan by its role (vocal on top, bass and kick
  solid in the centre, chordal beds ducked, colour instruments panned for
  width) plus a *small* set of effects that earn their place — light reverb
  and gentle compression on the voice, a tightening compressor on the bass.

- **An ending.** The last bar just stopped at full energy, so the song cut
  off abruptly. `apply_ending` fades the intro in and the final section out
  so it resolves instead of slamming shut.

Both are pure functions over the project model — no LLM, no rendering — so
they run in the pipeline unconditionally and are also exposed as chat ops.
They are idempotent: re-running replaces the mix effects this module owns
(tagged via Effect params) rather than stacking new ones, and never touches
effects a user added by hand.
"""
from __future__ import annotations

import logging

from ..models.song import Effect, SongProject, Track

log = logging.getLogger(__name__)

# marks the effects this module manages, so a re-mix replaces them instead of
# stacking and a user's own effects are left alone
_AUTO = "auto_mix"

# per-track-type level (0-2, 1.0 = unity) and whether it may be panned for
# width. The lead vocal sits on top; low end and kick stay centred; chordal
# beds and colour instruments sit under the lead.
_ROLE = {
    "lead_vocal":   {"vol": 1.0,  "pan": False},
    "backing_vocal": {"vol": 0.72, "pan": True},
    "drums":        {"vol": 0.94, "pan": False},
    "bass":         {"vol": 0.9,  "pan": False},
    "keys":         {"vol": 0.74, "pan": True},
    "guitar":       {"vol": 0.76, "pan": True},
    "strings":      {"vol": 0.66, "pan": True},
    "brass":        {"vol": 0.72, "pan": True},
    "synth":        {"vol": 0.72, "pan": True},
    "fx":           {"vol": 0.6,  "pan": True},
    "sample":       {"vol": 0.82, "pan": True},
}
# gentle spread positions handed out to pannable tracks in turn
_PAN_SLOTS = [-0.35, 0.35, -0.2, 0.2, -0.5, 0.5]


def _auto_effects_for(track_type: str, genre: str) -> list[Effect]:
    """The few effects a role genuinely benefits from — never a stack."""
    spacey = genre in ("ambient", "ballad", "synthwave", "soul")
    fx: list[Effect] = []
    if track_type == "lead_vocal":
        fx.append(Effect(effect_type="compressor", params={
            "threshold_db": -18.0, "ratio": 3.0, "attack_seconds": 0.008,
            "release_seconds": 0.15, "makeup_db": 3.0, _AUTO: 1}))
        fx.append(Effect(effect_type="reverb", params={
            "mix": 0.22 if spacey else 0.15, "decay": 0.55 if spacey else 0.4,
            _AUTO: 1}))
    elif track_type == "backing_vocal":
        fx.append(Effect(effect_type="reverb",
                         params={"mix": 0.28, "decay": 0.5, _AUTO: 1}))
    elif track_type == "bass":
        fx.append(Effect(effect_type="compressor", params={
            "threshold_db": -20.0, "ratio": 4.0, "attack_seconds": 0.02,
            "release_seconds": 0.12, "makeup_db": 2.0, _AUTO: 1}))
    elif track_type in ("keys", "guitar", "synth", "strings") and spacey:
        fx.append(Effect(effect_type="reverb",
                         params={"mix": 0.2, "decay": 0.5, _AUTO: 1}))
    elif track_type == "fx":
        fx.append(Effect(effect_type="reverb",
                         params={"mix": 0.35, "decay": 0.7, _AUTO: 1}))
    return fx


def _strip_auto(track: Track) -> list[Effect]:
    """Keep the user's own effects, drop the ones we placed before."""
    return [e for e in track.effects.effects if not e.params.get(_AUTO)]


def apply_default_mix(project: SongProject) -> list[str]:
    """Give every track a role-appropriate level, pan and (where it helps)
    an effect. Idempotent. Returns human-readable log lines."""
    from .genres import genre_profile
    genre = genre_profile(project).family
    log_lines: list[str] = []
    pan_i = 0
    for t in project.tracks:
        role = _ROLE.get(t.track_type)
        if role is None:
            continue
        from . import preferences
        t.volume = preferences.role_volume(t.track_type, role["vol"])
        if role["pan"]:
            t.pan = _PAN_SLOTS[pan_i % len(_PAN_SLOTS)]
            pan_i += 1
        else:
            t.pan = 0.0
        kept = _strip_auto(t)
        t.effects.effects = kept + _auto_effects_for(t.track_type, genre)
        log_lines.append(f"{t.name}: vol {t.volume:g}, pan {t.pan:g}"
                         + (f", +{len(t.effects.effects) - len(kept)} fx"
                            if len(t.effects.effects) > len(kept) else ""))
    # keep headroom for the limiter: master a touch below unity on big mixes
    audible = sum(1 for t in project.tracks if t.track_type in _ROLE)
    project.mix_settings.master_volume = 0.9 if audible >= 5 else 1.0
    project.mix_settings.limiter = True
    return log_lines


# --- ending ----------------------------------------------------------------

_INTRO_FADE_S = 0.6
_MAX_OUTRO_FADE_S = 6.0


def _section_seconds(project: SongProject, bars: int) -> float:
    from . import timing
    return timing.beats_to_seconds(project, bars * project.beats_per_bar)


def apply_ending(project: SongProject) -> list[str]:
    """Fade the first section in and the last section out so the song
    resolves instead of stopping mid-bar. Idempotent (recomputes the fades
    from the current sections). Returns log lines."""
    if not project.sections:
        return []
    sections = sorted(project.sections, key=lambda s: s.start_bar)
    first, last = sections[0], sections[-1]
    lines: list[str] = []

    # intro: a short fade-in on whatever plays in the first section
    for t in project.tracks:
        for c in t.clips:
            if c.section_id == first.id:
                c.fade_in_seconds = max(c.fade_in_seconds or 0.0, _INTRO_FADE_S)

    # outro: fade the final section out over most of its length so the last
    # chord/hit rings down rather than cutting
    outro_s = _section_seconds(project, last.length_bars)
    fade = min(outro_s * 0.7, _MAX_OUTRO_FADE_S)
    if fade < 0.5 and len(sections) >= 2:
        # a very short outro can't hold a musical fade — extend it to 4 bars
        last.length_bars = max(last.length_bars, 4)
        outro_s = _section_seconds(project, last.length_bars)
        fade = min(outro_s * 0.7, _MAX_OUTRO_FADE_S)
    faded = 0
    for t in project.tracks:
        for c in t.clips:
            if c.section_id == last.id:
                c.fade_out_seconds = max(c.fade_out_seconds or 0.0, fade)
                faded += 1
    if faded:
        lines.append(f"ending: {fade:.1f}s fade-out over {last.name!r}, "
                     f"{_INTRO_FADE_S:g}s fade-in on {first.name!r}")
    return lines


def finalize_song(project: SongProject) -> list[str]:
    """The full deterministic polish pass: mix + ending."""
    return apply_default_mix(project) + apply_ending(project)
