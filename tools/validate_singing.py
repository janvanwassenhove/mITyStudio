"""Singing-quality validation harness.

Renders a fixed test phrase (same lyrics + melody every run) through every
available singing engine and prints objective metrics side by side — run it
after any change to the vocal pipeline and compare against the last run.

Usage (from the repo root):
  apps/studio-api/.venv/Scripts/python.exe tools/validate_singing.py [profile_id] [language]

Engines covered:
  formant   MockSingingVoiceEngine (no profile)
  clone     XTTS + WORLD singing (profile, RVC skipped)
  clone+rvc XTTS + WORLD + trained RVC model (the production path)

Results are appended to tools/singing-validation.jsonl so runs are comparable
over time.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "studio-api"))

TEST_LINES = {
    "en": ["I found a quiet place to sing", "the morning light is following"],
    "nl": ["Ik vond een stille plek om te zingen", "het ochtendlicht volgt mij"],
    "fr": ["J'ai trouvé un endroit pour chanter", "la lumière du matin me suit"],
    "de": ["Ich fand einen stillen Ort zum Singen", "das Morgenlicht folgt mir"],
}


def build_test_project(language: str):
    from app.models.song import LyricsLine, Section, SongProject, Track
    from app.services.music_gen import generate_vocal_melody

    p = SongProject(title="_singing_validation", bpm=100)
    sec = Section(name="Verse", start_bar=0, length_bars=8)
    p.sections.append(sec)
    p.lyrics.language = language
    lines = TEST_LINES.get(language, TEST_LINES["en"])
    p.lyrics.lines = [LyricsLine(section_id=sec.id, text=t) for t in lines]
    track = Track(name="Lead Vocal", track_type="lead_vocal")
    clip = generate_vocal_melody(p, sec, lines)
    track.clips.append(clip)
    p.tracks.append(track)
    return p, track


def target_notes(p, track):
    from app.services import timing
    from app.services.vocal_engine import _note_freq
    out = []
    for clip in track.clips:
        for n in clip.note_events:
            start = timing.beats_to_seconds(p, clip.start_beat + n.start_beat)
            out.append({"start": start,
                        "end": start + timing.beats_to_seconds(p, n.duration_beats),
                        "freq": _note_freq(n.midi_note)})
    return out


def run_engine(name: str, engine, p, track, notes, out_dir: Path) -> dict:
    from app.services.audio_io import read_audio
    from app.services.singing_metrics import report

    out = out_dir / f"validate_{name.replace('+', '_')}.wav"
    t0 = time.time()
    try:
        engine.render(p, track, out)
    except Exception as e:  # noqa: BLE001
        return {"engine": name, "error": str(e)[:200]}
    data, rate = read_audio(out)
    r = report(data, rate, notes)
    r["engine"] = name
    r["render_seconds"] = round(time.time() - t0, 1)
    r["wav"] = str(out)
    return r


def main() -> None:
    profile_id = sys.argv[1] if len(sys.argv) > 1 else None
    language = sys.argv[2] if len(sys.argv) > 2 else "en"

    from app.config import get_config
    from app.services import voice_profiles as vp
    from app.services.vocal_engine import MockSingingVoiceEngine

    p, track = build_test_project(language)
    notes = target_notes(p, track)
    out_dir = get_config().analysis_cache_dir / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = None
    if profile_id:
        profile = vp.get_profile(profile_id)
    if profile is None:
        consented = [x for x in vp.list_profiles() if x.consent_confirmed]
        profile = consented[0] if consented else None

    results = [run_engine("formant", MockSingingVoiceEngine(), p, track,
                          notes, out_dir)]
    if profile is not None:
        from app.services.vocal_clone import (CloneSingingEngine,
                                              clone_engine_available)
        if clone_engine_available():
            os.environ["MITY_DISABLE_CLONE_ENGINE"] = ""
            # clone WITHOUT rvc: temporarily report as not-ready
            import app.services.rvc_convert as rvc
            real_ready = rvc.rvc_model_ready
            rvc.rvc_model_ready = lambda _p: False
            try:
                results.append(run_engine("clone", CloneSingingEngine(profile),
                                          p, track, notes, out_dir))
            finally:
                rvc.rvc_model_ready = real_ready
            if real_ready(profile):
                results.append(run_engine("clone+rvc",
                                          CloneSingingEngine(profile),
                                          p, track, notes, out_dir))
        else:
            results.append({"engine": "clone", "error": "voice deps not installed"})
    else:
        results.append({"engine": "clone", "error": "no consented voice profile"})

    cols = ["engine", "voiced_ratio", "median_cents_error", "within_50_cents",
            "spectral_flatness", "rms_active", "render_seconds"]
    print(f"\n=== singing validation · language={language}"
          f" · profile={profile.name if profile else '-'} ===")
    print(" | ".join(f"{c:>18}" for c in cols))
    for r in results:
        if "error" in r:
            print(f"{r['engine']:>18} | ERROR: {r['error']}")
        else:
            print(" | ".join(f"{str(r.get(c, '-')):>18}" for c in cols))
    print("\nListen to the WAVs in", out_dir, "— metrics rank variants;"
          " ears decide.")

    log = ROOT / "tools" / "singing-validation.jsonl"
    stamp = {"language": language,
             "profile": profile.name if profile else None,
             "results": results}
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(stamp) + "\n")


if __name__ == "__main__":
    main()
