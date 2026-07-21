"""Arrangement-quality validation harness (docs/song-quality.md M4/R4).

Builds a full song OFFLINE (no LLM — the deterministic generators only, so
this also proves R2's no-API-key path) for every genre in the golden set,
then scores it with arrangement_metrics plus genre-specific groove checks:
does bossa carry its clave, is trap half-time, does house keep four on the
floor, does the tempo sit in the genre's range, does the arrangement vary
per section?

Run it after ANY change to genres.py / music_gen.py / arrangement.py and
compare against the last run. Results are appended to
tools/arrangement-validation.jsonl so runs are comparable over time —
without this ledger, the critique loop has nothing to optimise against.

Usage (from the repo root):
  python tools/validate_arrangement.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "studio-api"))

# golden set: style text as a USER would type it → expected characteristics
GOLDEN = [
    {"style": "happy bossa nova pop", "family": "bossa",
     "groove": {"kick_and_of_2": True, "rim_clave": True}},
    {"style": "pop punk", "family": "rock",
     "groove": {"kick_every_beat": True, "backbeat": True}},
    {"style": "deep house", "family": "dance",
     "groove": {"kick_every_beat": True}},
    {"style": "synthwave", "family": "synthwave",
     "groove": {"kick_every_beat": True}},
    {"style": "trap", "family": "hiphop",
     "groove": {"halftime_snare": True}},
    {"style": "reggae", "family": "reggae",
     "groove": {"one_drop": True, "offbeat_hats": True}},
    {"style": "funk", "family": "funk",
     "groove": {"ghost_snares": True}},
    {"style": "smooth jazz", "family": "jazz",
     "groove": {"ride_swing": True}, "sevenths": True},
]

KICK, SNARE, RIM, HAT, RIDE = 36, 38, 37, 42, 51


def build_song(style: str):
    """Full song via the same ops chat would emit — mock/offline path."""
    from app.models.operations import ChatOperation
    from app.models.song import SongProject
    from app.services import operation_applier
    from app.services.genres import resolve_family, suggest_bpm

    fam = resolve_family(style)
    ops = [ChatOperation(op_type="create_song",
                         params={"title": f"golden {fam}", "style": style,
                                 "bpm": suggest_bpm(fam), "key": "C major"})]
    for name, bars, energy in (("Intro", 4, 0.3), ("Verse", 8, 0.45),
                               ("Chorus", 8, 0.9), ("Verse 2", 8, 0.5),
                               ("Chorus 2", 8, 0.95), ("Outro", 4, 0.35)):
        ops.append(ChatOperation(op_type="add_section",
                                 params={"name": name, "length_bars": bars,
                                         "energy": energy}))
    for gen, track in (("generate_drums", "Drums"),
                       ("generate_bassline", "Bass"),
                       ("generate_chords", "Keys"),
                       ("generate_melody", "Lead")):
        ops.append(ChatOperation(op_type=gen,
                                 params={"section": "all", "track": track}))
    project = SongProject(title="x")
    results = operation_applier.apply_operations(project, ops)
    errors = [r.error for r in results if not r.applied]
    return project, errors


def groove_checks(project, expect: dict) -> dict[str, bool]:
    """Genre-truth assertions against the drum track's first bar (the
    sections start at different energies; use the chorus = full groove)."""
    drums = next((t for t in project.tracks if t.track_type == "drums"), None)
    if drums is None:
        return {k: False for k in expect}
    chorus = next(s for s in project.sections if s.name == "Chorus")
    bpb = project.beats_per_bar
    start = chorus.start_bar * bpb
    notes = [n for c in drums.clips if c.section_id == chorus.id
             for n in c.note_events]

    def beats(midi_set, span=4.0):
        # quantize BEFORE the span filter: humanized jitter puts a beat-4
        # note at 3.988, which must count as bar 2, not bar 1
        out = set()
        for n in notes:
            q = round(n.start_beat * 4) / 4
            if n.midi_note in midi_set and q < span:
                out.add(q)
        return out

    kicks, snares = beats({KICK}), beats({SNARE})
    rims, hats, rides = beats({RIM}), beats({HAT}), beats({RIDE})
    checks = {
        "kick_every_beat": {0.0, 1.0, 2.0, 3.0} <= kicks,
        "kick_and_of_2": 1.5 in kicks,
        "rim_clave": {0.0, 1.5, 3.0} <= rims,
        "backbeat": {1.0, 3.0} <= snares,
        "halftime_snare": snares == {2.0},
        "one_drop": 2.0 in rims and not (kicks - {2.0, 0.0}),
        "offbeat_hats": bool(hats) and not any(h % 1 == 0 for h in hats),
        "ghost_snares": any(n.midi_note == SNARE and n.velocity < 50
                            for n in notes),
        "ride_swing": bool(rides) and any(abs(r % 1 - 0.75) < 0.05
                                          for r in rides),
    }
    return {k: checks[k] for k in expect}


def run() -> dict:
    from app.services import arrangement_metrics
    from app.services.genres import genre_profile

    git_rev = ""
    try:
        git_rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True,
                                 cwd=ROOT).stdout.strip()
    except OSError:
        pass

    rows, failures = [], 0
    for entry in GOLDEN:
        project, errors = build_song(entry["style"])
        prof = genre_profile(project)
        m = arrangement_metrics.analyse(project)
        grooves = groove_checks(project, entry["groove"])
        tempo_ok = prof.tempo[0] <= project.bpm <= prof.tempo[1]
        sevenths_ok = True
        if entry.get("sevenths"):
            from app.services.music_gen import chord_progression
            sevenths_ok = len(chord_progression("C major",
                                                entry["style"], 1)[0]) == 4
        ok = (not errors and project.genre == entry["family"] and tempo_ok
              and m["is_complete_song"] and not m["static_arrangement"]
              and all(grooves.values()) and sevenths_ok)
        failures += 0 if ok else 1
        rows.append({
            "style": entry["style"], "family": project.genre,
            "family_ok": project.genre == entry["family"],
            "bpm": project.bpm, "tempo_ok": tempo_ok,
            "completeness": m["completeness"], "key_ratio": m["key_ratio"],
            "duration_s": m["duration_seconds"],
            "complete_song": m["is_complete_song"],
            "varied_arrangement": not m["static_arrangement"],
            "grooves": grooves, "sevenths_ok": sevenths_ok,
            "errors": errors, "ok": ok,
        })
        flag = "OK " if ok else "FAIL"
        print(f"[{flag}] {entry['style']:24} -> {project.genre:10} "
              f"{project.bpm:3.0f}bpm  compl={m['completeness']:.0%} "
              f"key={m['key_ratio']:.0%}  grooves={grooves}")

    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "git": git_rev,
              "passed": len(rows) - failures, "failed": failures,
              "results": rows}
    ledger = ROOT / "tools" / "arrangement-validation.jsonl"
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"\n{record['passed']}/{len(rows)} genres pass — appended to "
          f"{ledger.relative_to(ROOT)}")
    return record


if __name__ == "__main__":
    rec = run()
    sys.exit(0 if rec["failed"] == 0 else 1)
