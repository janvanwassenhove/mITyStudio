"""Full-song generation pipeline (docs/song-quality.md §6, M5).

Deterministic control flow in Python; the LLM is called only where musical
judgment is needed — never for orchestration:

  1. producer   one LLM call → song spec (sections, tempo, key, energy
                curve, instrumentation, genre). Offline: a deterministic
                spec from the prompt (R2 — no API key still yields a song).
  2. skeleton   the spec expands through the existing generate_* ops —
                instant, genre-true, complete BY CONSTRUCTION.
  3. composers  one write_notes call per instrument track, each with its
                own token budget (the fix for truncated half-songs), run
                in parallel.
  4. metrics    arrangement_metrics — objective, no LLM.
  5. improve    an agentic loop: measure a 0-1 quality score, have the
                producer fix the WEAKEST dimensions, re-measure, and keep the
                round only if the score climbed (revert otherwise). Stops on
                target, no-gain, or the round cap.
  6. ledger     metrics + usage appended to analysis-cache/song-pipeline.jsonl
                so quality is comparable across runs (R4).

The whole run executes as a background job (the quick-add refinement
pattern: an LLM takes minutes; endpoints must stay instant).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from ..config import get_config
from ..models.operations import ChatOperation
from ..models.song import SongProject
from . import (arrangement_metrics, genres, operation_applier,
               operation_planner, project_repo)
from .llm.settings import load_settings

log = logging.getLogger(__name__)

MAX_CRITIC_ROUNDS = 3          # hard cap (R3); the loop also stops on no gain
QUALITY_TARGET = 0.9           # stop improving once the score clears this
MIN_GAIN = 0.01                # a round must lift the score by at least this
MAX_COMPOSERS = 3              # parallel LLM composer calls

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _llm_available() -> bool:
    return load_settings().provider != "mock"


# chat handoff: "make/write/generate ... a song" in the four app languages.
# Both orders ("maak een nummer", "een nummer maken") are matched.
_MAKE = (r"(?:maak|schrijf|genereer|componeer|bouw|creëer|make|create|write|"
         r"generate|compose|build|crée|creer|écris|ecris|génère|genere|"
         r"erstelle|schreib|generiere|komponiere)")
# \w* prefixes catch the Dutch/German compound forms that are the NORMAL
# phrasing: "popnummer", "punksong", "zomerliedje", "Sommerlied"
_SONG = r"(?:\w*song|\w*nummer|\w*lied(?:je)?|track|chanson|morceau)"
_FULL_SONG_RE = re.compile(
    rf"\b{_MAKE}\w*\b.{{0,80}}?\b{_SONG}\b"
    rf"|\b{_SONG}\b.{{0,40}}?\b{_MAKE}\w*\b",
    re.IGNORECASE | re.DOTALL)


# An explicitly requested tempo ("170 bpm", "bpm: 96", "op 128 BPM").
# Requiring the literal "bpm" keeps years, counts and section numbers out.
_BPM_RE = re.compile(r"(?:(\d{2,3})\s*bpm|bpm\s*[:=]?\s*(\d{2,3}))",
                     re.IGNORECASE)


def explicit_bpm(message: str) -> float | None:
    """The tempo the user asked for, if they named one. This ALWAYS wins over
    the genre's typical range — that range is guidance for when nothing was
    asked, never a cap on an explicit request."""
    m = _BPM_RE.search(message or "")
    if not m:
        return None
    try:
        bpm = float(m.group(1) or m.group(2))
    except (TypeError, ValueError):
        return None
    return bpm if 20 < bpm < 400 else None      # SongProject's valid range


def detect_full_song_intent(message: str) -> bool:
    """Does this chat message ask for a whole song? Used by routes_chat to
    hand an empty project over to the pipeline instead of the one-shot
    Layer-1 plan (which is where truncated half-songs came from)."""
    return bool(_FULL_SONG_RE.search(message or ""))


# --------------------------------------------------------------------------
# 1. producer
# --------------------------------------------------------------------------

_SECTION_TEMPLATE = [("Intro", 4, 0.3), ("Verse", 8, 0.45),
                     ("Chorus", 8, 0.9), ("Verse 2", 8, 0.5),
                     ("Chorus 2", 8, 0.95), ("Outro", 4, 0.35)]

_DEFAULT_BAND = ["drums", "bass", "keys", "guitar"]


def _fallback_spec(prompt: str) -> dict:
    """Deterministic spec — the offline producer. Genre-true by lexicon."""
    fam = genres.resolve_family(prompt)
    prof = genres.profile_for(prompt)
    band = list(_DEFAULT_BAND)
    if fam in ("dance", "synthwave", "hiphop", "ambient"):
        band = ["drums", "bass", "synth", "keys"]
    elif fam in ("funk", "soul", "bossa", "jazz"):
        band = ["drums", "bass", "keys", "brass"]
    return {"title": prompt.strip()[:60] or "Untitled",
            "style": prompt.strip() or prof.label, "genre": fam,
            # an explicitly requested tempo wins; otherwise the genre's
            # typical tempo is a sensible default
            "bpm": explicit_bpm(prompt) or genres.suggest_bpm(fam),
            "key": "C major",
            "sections": [{"name": n, "length_bars": b, "energy": e}
                         for n, b, e in _SECTION_TEMPLATE],
            "instrumentation": band}


def _producer_spec(project: SongProject, prompt: str, language: str,
                   job: dict) -> dict:
    spec = _fallback_spec(prompt)
    if not _llm_available():
        return spec
    from . import preferences
    avoid = preferences.recurring_issues()
    lesson = ("\n\nRecent songs had these recurring problems — avoid them:\n- "
              + "\n- ".join(avoid)) if avoid else ""
    ask = (
        "Design a song SPEC for this request — structure only, no notes yet. "
        "Reply with ONE operation: create_song with params title, style, "
        "genre, bpm (inside the genre's tempo range), key, and an extra "
        "param \"plan\" = {\"sections\": [{\"name\", \"length_bars\", "
        "\"energy\" (0-1, shape a real dynamic arc: calm intro, big "
        "choruses)}...], \"instrumentation\": [track types], "
        "\"vocals\": true|false (should this song be sung?), "
        "\"lyrics_theme\": \"one line\"}. "
        f"Request: {prompt}{lesson}")
    reply, ops, _warn, usage = operation_planner.plan(project, ask,
                                                      language=language)
    _count_usage(job, usage)
    for op in ops:
        if op.op_type != "create_song":
            continue
        p = op.params
        plan = p.get("plan") or {}
        secs = [s for s in plan.get("sections", [])
                if isinstance(s, dict) and s.get("name")][:10]
        fam = genres.resolve_family(str(p.get("genre") or p.get("style")
                                        or prompt))
        asked = explicit_bpm(prompt)
        if asked:
            bpm = asked                    # the user named a tempo: obey it
        else:
            lo, hi = genres.profile_for(fam).tempo
            try:
                bpm = float(p.get("bpm", 0)) or genres.suggest_bpm(fam)
            except (TypeError, ValueError):
                bpm = genres.suggest_bpm(fam)
            # only a model-invented tempo gets nudged toward the genre range
            bpm = min(max(bpm, lo - 15), hi + 15)
        spec.update({
            "title": str(p.get("title") or spec["title"])[:80],
            "style": str(p.get("style") or spec["style"]),
            "genre": fam,
            "bpm": bpm,
            "key": str(p.get("key") or spec["key"]),
        })
        if len(secs) >= 3:
            spec["sections"] = [
                {"name": str(s["name"])[:40],
                 "length_bars": max(2, min(16, int(s.get("length_bars", 8)))),
                 "energy": min(1.0, max(0.0, float(s.get("energy", 0.5))))}
                for s in secs]
        band = [t for t in plan.get("instrumentation", [])
                if t in ("drums", "bass", "guitar", "keys", "synth",
                         "strings", "brass")]
        if band:
            spec["instrumentation"] = list(dict.fromkeys(band))[:6]
        spec["vocals"] = bool(plan.get("vocals"))
        spec["lyrics_theme"] = str(plan.get("lyrics_theme") or "")[:200]
        break
    return spec


# --------------------------------------------------------------------------
# 2. skeleton
# --------------------------------------------------------------------------

_GEN_FOR_TYPE = {"drums": "generate_drums", "bass": "generate_bassline",
                 "guitar": "generate_chords", "keys": "generate_chords",
                 "strings": "generate_chords", "brass": "generate_chords",
                 "synth": "generate_melody"}


def _build_skeleton(project: SongProject, spec: dict) -> list[str]:
    ops = [ChatOperation(op_type="create_song", params={
        "title": spec["title"], "style": spec["style"],
        "genre": spec["genre"], "bpm": spec["bpm"], "key": spec["key"]})]
    for s in spec["sections"]:
        ops.append(ChatOperation(op_type="add_section", params=s))
    for tt in spec["instrumentation"]:
        gen = _GEN_FOR_TYPE.get(tt)
        if gen:
            ops.append(ChatOperation(op_type=gen, params={
                "section": "all", "track": tt.title(), "track_type": tt}))
    results = operation_applier.apply_operations(project, ops)
    return [r.error for r in results if not r.applied and r.error]


# --------------------------------------------------------------------------
# 3. composers (parallel, per-track token budget)
# --------------------------------------------------------------------------

def _compose_track(project_id: str, track_id: str, language: str,
                   job: dict) -> str | None:
    """One LLM composer call for one track; returns a log line or None.
    Loads a FRESH copy for planning but applies to the shared project via
    the caller (thread-safe: each composer touches only its own track)."""
    project = project_repo.load_project(project_id)
    track = next((t for t in project.tracks if t.id == track_id), None)
    if track is None:
        return None
    ask = (f"Compose the {track.track_type} part for track \"{track.name}\" "
           f"yourself with write_notes, section by section — a genre-true, "
           f"memorable part that fits the song's style, key and tempo. "
           f"Replace the placeholder pattern; do not add tracks or effects.")
    _reply, ops, _warn, usage = operation_planner.plan(project, ask,
                                                       language=language)
    _count_usage(job, usage)
    wrote = [op for op in ops if op.op_type == "write_notes"]
    for op in wrote:
        op.params["track"] = track_id          # rename-proof targeting
    if not wrote:
        return None
    results = operation_applier.apply_operations(project, wrote)
    applied = [r for r in results if r.applied]
    if applied:
        project_repo.save_project(project)
        return (f"{track.name}: AI-composed "
                f"{sum(1 for _ in applied)} section part(s)")
    return None


# --------------------------------------------------------------------------
# 3b. vocals (when the song wants singing)
# --------------------------------------------------------------------------

_VOCAL_HINT = ("vocal", "vocals", "sing", "singer", "sung", "lyric",
               "zang", "zing", "gezongen", "songtekst",
               "chant", "chante", "paroles",
               "gesang", "singen", "songtext")


def _wants_vocals(spec: dict, prompt: str) -> bool:
    if spec.get("vocals"):
        return True
    low = prompt.lower()
    return any(h in low for h in _VOCAL_HINT)


_VOCAL_OPS = {"rewrite_lyrics", "create_vocal_track", "generate_melody",
              "assign_voice_profile"}


def _vocals_stage(project_id: str, spec: dict, language: str,
                  job: dict) -> list[str]:
    """LLM writes the lyrics and sets up a singing lead; the existing
    vocal autofill then guarantees every lyric section gets a melody.
    Offline: only sings lyrics the project already has (imported scores)."""
    from .vocal_autofill import ensure_vocal_melodies

    project = project_repo.load_project(project_id)
    lines: list[str] = []
    if _llm_available():
        theme = spec.get("lyrics_theme") or spec.get("title") or ""
        ask = (f"Write the full lyrics for this song (theme: {theme}) with "
               f"rewrite_lyrics per lyric section (set the language param), "
               f"then create_vocal_track (track_type lead_vocal) and "
               f"generate_melody with track_type lead_vocal for the lyric "
               f"sections. Lyrics only — no instrument changes.")
        _reply, ops, _warn, usage = operation_planner.plan(project, ask,
                                                           language=language)
        _count_usage(job, usage)
        ops = [op for op in ops if op.op_type in _VOCAL_OPS]
        results = operation_applier.apply_operations(project, ops)
        lines += [r.summary for r in results if r.applied]
    elif not project.lyrics.lines:
        return []          # nothing to sing offline
    if not any(t.track_type == "lead_vocal" for t in project.tracks) \
            and project.lyrics.lines:
        results = operation_applier.apply_operations(project, [ChatOperation(
            op_type="create_vocal_track",
            params={"name": "Lead Vocal", "track_type": "lead_vocal"})])
        lines += [r.summary for r in results if r.applied]
    lines += ensure_vocal_melodies(project)
    project_repo.save_project(project)
    return lines


# --------------------------------------------------------------------------
# 5. critic (bounded)
# --------------------------------------------------------------------------

_CRITIC_OPS = {"set_clip_fades", "update_track", "add_effect",
               "update_effect", "update_mix", "generate_drums",
               "generate_bassline", "generate_chords", "generate_melody",
               "write_notes"}


# the fix each weak dimension calls for — turns a measured shortfall into a
# concrete instruction the producer can act on
_DIMENSION_FIX = {
    "completeness": "some sections are missing parts — generate the missing "
                    "instruments so every section is filled",
    "key": "notes stray from the key — regenerate the off-key parts in key",
    "dynamics": "the same instruments play in every section — vary the "
                "arrangement so verses are sparser than choruses",
    "headroom": "stems are clipping — lower the loudest track volumes with "
                "update_track / update_mix",
    "density": "a part is nearly empty or overcrowded — regenerate it at a "
               "sensible density",
    "complete_song": "the song is too short or thin to stand as a full song "
                     "— add sections or parts",
    "ending": "the song stops abruptly — finalize_ending (fade the outro out)",
    "mix": "the mix is flat — auto_mix for role levels, pan and earning effects",
}


def _critic_round(project: SongProject, metrics: dict, sc: dict,
                  language: str, job: dict) -> list[str]:
    # target the weakest measured dimensions first, with concrete fixes
    issues = [_DIMENSION_FIX[d] for d in sc["weakest"] if d in _DIMENSION_FIX]
    issues += [r for r in metrics["incomplete_reasons"]
               if r not in issues][:3]
    if not issues:
        return []
    ask = (f"You are the producer improving a song (current quality "
           f"{sc['score']:.2f}/1.0). Fix ONLY these measured weaknesses — "
           "nothing else, and every effect must earn its place (no "
           "stacking):\n- " + "\n- ".join(issues[:6]))
    _reply, ops, _warn, usage = operation_planner.plan(project, ask,
                                                       language=language)
    _count_usage(job, usage)
    ops = [op for op in ops if op.op_type in _CRITIC_OPS]
    results = operation_applier.apply_operations(project, ops)
    return [r.summary for r in results if r.applied]


# --------------------------------------------------------------------------
# job driver
# --------------------------------------------------------------------------

def _count_usage(job: dict, usage: dict | None) -> None:
    if usage:
        job["llm_calls"] = job.get("llm_calls", 0) + 1
        job["tokens_out"] = job.get("tokens_out", 0) \
            + int(usage.get("output_tokens") or 0)


def _set(job: dict, **kw) -> None:
    with _jobs_lock:
        job.update(kw)


def _run(job: dict, project_id: str, prompt: str, language: str) -> None:
    t0 = time.time()
    try:
        project = project_repo.load_project(project_id)
        _set(job, stage="producer", progress=0.1)
        spec = _producer_spec(project, prompt, language, job)

        _set(job, stage="skeleton", progress=0.25,
             detail=f"{spec['genre']} @ {spec['bpm']:g} bpm")
        errors = _build_skeleton(project, spec)
        project_repo.save_project(project)
        job.setdefault("log", []).extend(errors)

        if _llm_available():
            _set(job, stage="composing", progress=0.4)
            tracks = [t.id for t in project.tracks
                      if t.track_type in _GEN_FOR_TYPE]
            with ThreadPoolExecutor(max_workers=MAX_COMPOSERS) as pool:
                for line in pool.map(
                        lambda tid: _compose_track(project_id, tid,
                                                   language, job), tracks):
                    if line:
                        job.setdefault("log", []).append(line)
            project = project_repo.load_project(project_id)

        if _wants_vocals(spec, prompt):
            _set(job, stage="vocals", progress=0.6)
            job.setdefault("log", []).extend(
                _vocals_stage(project_id, spec, language, job))
            project = project_repo.load_project(project_id)

        # Deterministic polish BEFORE rendering, so the fades bake into the
        # stems and the levels are right the first time you press play. This
        # used to be the critic's job, but the critic only runs when metrics
        # flag a problem — so a structurally fine song got no mix and no
        # ending, which is why generated songs stopped dead at the last bar.
        _set(job, stage="mixing", progress=0.65)
        from . import mixing
        job.setdefault("log", []).extend(mixing.finalize_song(project))
        project_repo.save_project(project)

        # render the instrument stems NOW: the waveform cache this fills is
        # what gives the critic real per-stem peaks/clipping to judge, and
        # the user can press ▶ the moment the job finishes
        _set(job, stage="rendering", progress=0.68)
        try:
            from .render.soundfont_renderer import render_instrument_stems
            r = render_instrument_stems(project)
            job.setdefault("log", []).extend(r["errors"])
            project_repo.save_project(project)
        except Exception as e:  # noqa: BLE001 — metrics still work unrendered
            log.warning("pipeline render stage failed: %s", e)

        _set(job, stage="metrics", progress=0.78)
        metrics = arrangement_metrics.analyse(project)
        sc = arrangement_metrics.score(metrics, project)
        job["metrics_before"] = arrangement_metrics.summary_line(metrics)
        job["score_before"] = sc["score"]

        # AGENTIC IMPROVEMENT LOOP: re-evaluate and re-fix until the measured
        # quality score stops climbing. Each round targets the WEAKEST scoring
        # dimensions, then re-measures; a round that does not raise the score
        # by MIN_GAIN is rolled back (its edits reverted) and the loop ends —
        # so the model can never make the song worse, and "learning" here
        # means hill-climbing a number, not the model grading itself.
        if _llm_available():
            for rnd in range(MAX_CRITIC_ROUNDS):
                if sc["score"] >= QUALITY_TARGET or not sc["weakest"]:
                    break
                _set(job, stage="critic", progress=0.82 + 0.04 * rnd,
                     detail=f"round {rnd + 1}: fixing {', '.join(sc['weakest'])}")
                snapshot = project.model_copy(deep=True)
                fixes = _critic_round(project, metrics, sc, language, job)
                if not fixes:
                    break
                new_metrics = arrangement_metrics.analyse(project)
                new_sc = arrangement_metrics.score(new_metrics, project)
                if new_sc["score"] < sc["score"] + MIN_GAIN:
                    # no real gain (or a regression) — undo this round and stop
                    project = snapshot
                    job.setdefault("log", []).append(
                        f"round {rnd + 1}: score {new_sc['score']:.2f} did not "
                        f"beat {sc['score']:.2f} — reverted")
                    break
                job.setdefault("log", []).extend(fixes)
                job["log"].append(
                    f"round {rnd + 1}: score {sc['score']:.2f} → "
                    f"{new_sc['score']:.2f}")
                project_repo.save_project(project)
                metrics, sc = new_metrics, new_sc

        job["metrics"] = {k: metrics[k] for k in
                          ("completeness", "key_ratio", "duration_seconds",
                           "is_complete_song", "static_arrangement")}
        job["score"] = sc["score"]
        _ledger_append(project, prompt, job, time.time() - t0)
        _set(job, stage="done", progress=1.0, status="done",
             summary=f"quality {sc['score']:.2f} · "
                     + arrangement_metrics.summary_line(metrics))
    except Exception as e:  # noqa: BLE001 — job must report, not vanish
        log.exception("song pipeline failed")
        _set(job, status="error", error=str(e))


def _ledger_append(project: SongProject, prompt: str, job: dict,
                   seconds: float) -> None:
    try:
        path = get_config().analysis_cache_dir / "song-pipeline.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "project_id": project.id, "prompt": prompt,
                "genre": project.genre, "bpm": project.bpm,
                "llm_calls": job.get("llm_calls", 0),
                "tokens_out": job.get("tokens_out", 0),
                "seconds": round(seconds, 1),
                "score_before": job.get("score_before"),
                "score": job.get("score"),
                "metrics": job.get("metrics", {}),
            }) + "\n")
    except OSError:
        log.warning("could not append song-pipeline ledger")


def start(project_id: str, prompt: str, language: str = "en",
          force: bool = False) -> dict:
    """Kick off a full-song job. Refuses to run over existing content
    unless forced (R1: never clobber user work)."""
    project = project_repo.load_project(project_id)
    if not force and any(t.clips for t in project.tracks):
        raise ValueError(
            "project already has content — pass force=true to regenerate")
    job = {"id": uuid.uuid4().hex[:12], "project_id": project_id,
           "status": "running", "stage": "starting", "progress": 0.0,
           "log": [], "llm_calls": 0, "tokens_out": 0}
    with _jobs_lock:
        _jobs[job["id"]] = job
    threading.Thread(target=_run, args=(job, project_id, prompt, language),
                     daemon=True).start()
    return job


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None
