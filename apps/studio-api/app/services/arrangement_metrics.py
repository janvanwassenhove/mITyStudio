"""Arrangement metrics — objective quality signals, no LLM
(docs/song-quality.md 0.8, R5, R6).

These numbers are what the critique loop optimises against and what the
validation ledger records. Everything here is cheap, deterministic and
computable offline:

- completeness: does every section carry the parts the arrangement template
  expects? (R6: "a full song" becomes testable, not a matter of taste)
- key adherence: fraction of pitched notes inside the project scale
- density: notes per beat per track — flags near-empty and overcrowded parts
- section dynamics: do sections actually differ (energy shape, who plays)?
- stem peaks: clipping / headroom straight from the waveform cache
"""
from __future__ import annotations

import logging

from ..config import get_config
from ..models.song import SongProject

log = logging.getLogger(__name__)

# R6 — the written definition of "a full song"
MIN_SECTIONS = 3
MIN_DURATION_S = 60.0
MIN_COMPLETENESS = 0.9


def analyse(project: SongProject) -> dict:
    from .arrangement import _covers, plays_in_section
    from .music_gen import scale_notes

    bpb = project.beats_per_bar
    scale = set(scale_notes(project.key))
    instrument = [t for t in project.tracks
                  if t.track_type in ("drums", "bass", "guitar", "keys",
                                      "strings", "brass", "synth", "fx")]
    content = [t for t in instrument
               if any(c.clip_type == "midi" and c.note_events
                      for c in t.clips)]

    # --- completeness: (content track, section) pairs the template expects
    expected = covered = 0
    missing: list[str] = []
    per_section: list[dict] = []
    for s in project.sections:
        playing = []
        for t in content:
            if not plays_in_section(t.track_type, s, project):
                continue
            expected += 1
            if _covers(t, s, bpb):
                covered += 1
                playing.append(t.name)
            else:
                missing.append(f"{t.name} in {s.name!r}")
        per_section.append({"section": s.name, "energy": s.energy,
                            "playing": playing})
    completeness = covered / expected if expected else 1.0

    # --- key adherence over pitched tracks
    pitched_total = pitched_in_key = 0
    for t in content:
        if t.track_type == "drums":
            continue
        for c in t.clips:
            for n in c.note_events:
                pitched_total += 1
                if n.midi_note % 12 in scale:
                    pitched_in_key += 1
    key_ratio = pitched_in_key / pitched_total if pitched_total else 1.0

    # --- density per track (notes per beat) — near-empty / overcrowded flags
    density: dict[str, float] = {}
    flags: list[str] = []
    for t in content:
        beats = sum(c.duration_beats for c in t.clips
                    if c.clip_type == "midi") or 1.0
        notes = sum(len(c.note_events) for c in t.clips)
        d = round(notes / beats, 3)
        density[t.name] = d
        if d < 0.05:
            flags.append(f"{t.name}: nearly empty ({d} notes/beat)")
        elif d > 8:
            flags.append(f"{t.name}: overcrowded ({d} notes/beat)")

    # --- section dynamics: instrumentation must actually vary
    lineups = {tuple(sorted(sec["playing"])) for sec in per_section}
    static_arrangement = len(project.sections) >= 3 and len(lineups) <= 1

    # --- stem peaks from the waveform cache (present after a render)
    stems: list[dict] = []
    try:
        import json
        wf = get_config().projects_dir / project.id / "waveforms.json"
        if wf.exists():
            for entry in json.loads(wf.read_text(encoding="utf-8")):
                peak = max(entry.get("peaks") or [0.0])
                stems.append({"track_id": entry["track_id"], "peak": peak,
                              "clipping": peak >= 0.99})
    except Exception:  # noqa: BLE001 — metrics must never break a request
        pass

    duration = project.duration_seconds()
    reasons = []
    if len(project.sections) < MIN_SECTIONS:
        reasons.append(f"only {len(project.sections)} sections "
                       f"(need {MIN_SECTIONS})")
    if duration < MIN_DURATION_S:
        reasons.append(f"only {duration:.0f}s long (need {MIN_DURATION_S:.0f}s)")
    if completeness < MIN_COMPLETENESS:
        reasons.append(f"completeness {completeness:.2f} "
                       f"(need {MIN_COMPLETENESS}); missing: "
                       + "; ".join(missing[:6]))
    if not content:
        reasons.append("no instrument tracks with content")

    return {
        "completeness": round(completeness, 3),
        "missing": missing,
        "key_ratio": round(key_ratio, 3),
        "density": density,
        "density_flags": flags,
        "sections": per_section,
        "static_arrangement": static_arrangement,
        "stems": stems,
        "clipping": [s["track_id"] for s in stems if s["clipping"]],
        "duration_seconds": round(duration, 1),
        "is_complete_song": not reasons,
        "incomplete_reasons": reasons,
    }


def has_ending(project: SongProject) -> bool:
    """Does the last section fade out (a real ending, not a hard stop)?"""
    if not project.sections:
        return False
    last = max(project.sections, key=lambda s: s.start_bar)
    return any(c.section_id == last.id and (c.fade_out_seconds or 0) > 0.4
               for t in project.tracks for c in t.clips)


def has_mix(project: SongProject) -> bool:
    """Has anything shaped the mix, or is every track still flat/centred?"""
    return any(t.volume != 1.0 or t.pan != 0.0 or t.effects.effects
               for t in project.tracks
               if t.track_type not in ("sample",))


# what each dimension contributes to the 0-1 quality score. The score is the
# scalar the improvement loop hill-climbs and the ledger records — grounded
# in measurements, never in the model's opinion of its own work.
_WEIGHTS = {"completeness": 0.30, "key": 0.20, "dynamics": 0.15,
            "headroom": 0.12, "density": 0.08, "complete_song": 0.05,
            "ending": 0.05, "mix": 0.05}


def score(m: dict, project: SongProject | None = None) -> dict:
    """A composite 0-1 quality score plus its per-dimension breakdown, so the
    loop knows WHAT to improve, not just that it should."""
    dims = {
        "completeness": m["completeness"],
        "key": m["key_ratio"],
        "dynamics": 0.0 if m["static_arrangement"] else 1.0,
        "headroom": 0.0 if m["clipping"] else 1.0,
        "density": max(0.0, 1.0 - 0.34 * len(m["density_flags"])),
        "complete_song": 1.0 if m["is_complete_song"] else 0.0,
        "ending": 1.0 if (project and has_ending(project)) else 0.0,
        "mix": 1.0 if (project and has_mix(project)) else 0.0,
    }
    total = round(sum(_WEIGHTS[k] * v for k, v in dims.items()), 4)
    # the dimensions most worth fixing = biggest weighted shortfall
    worst = sorted(dims, key=lambda k: _WEIGHTS[k] * (1 - dims[k]),
                   reverse=True)
    return {"score": total, "dimensions": dims,
            "weakest": [k for k in worst if dims[k] < 0.999][:3]}


def summary_line(m: dict) -> str:
    """One-line digest for logs, the chat reply and the ledger."""
    bits = [f"completeness {m['completeness']:.0%}",
            f"key {m['key_ratio']:.0%}",
            f"{m['duration_seconds']:.0f}s"]
    if m["static_arrangement"]:
        bits.append("static arrangement")
    if m["clipping"]:
        bits.append(f"{len(m['clipping'])} stems clipping")
    if m["density_flags"]:
        bits.append(f"{len(m['density_flags'])} density flags")
    return ", ".join(bits)
