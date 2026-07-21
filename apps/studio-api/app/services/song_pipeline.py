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
  5. critic     ONE bounded call that may only fix what the metrics flag
                (fades, levels, effects that earn their place). Skipped
                when the metrics are clean.
  6. ledger     metrics + usage appended to analysis-cache/song-pipeline.jsonl
                so quality is comparable across runs (R4).

The whole run executes as a background job (the quick-add refinement
pattern: an LLM takes minutes; endpoints must stay instant).
"""
from __future__ import annotations

import json
import logging
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

MAX_CRITIC_ROUNDS = 1          # hard cap (R3); metrics gate entry anyway
MAX_COMPOSERS = 3              # parallel LLM composer calls

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _llm_available() -> bool:
    return load_settings().provider != "mock"


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
            "bpm": genres.suggest_bpm(fam), "key": "C major",
            "sections": [{"name": n, "length_bars": b, "energy": e}
                         for n, b, e in _SECTION_TEMPLATE],
            "instrumentation": band}


def _producer_spec(project: SongProject, prompt: str, language: str,
                   job: dict) -> dict:
    spec = _fallback_spec(prompt)
    if not _llm_available():
        return spec
    ask = (
        "Design a song SPEC for this request — structure only, no notes yet. "
        "Reply with ONE operation: create_song with params title, style, "
        "genre, bpm (inside the genre's tempo range), key, and an extra "
        "param \"plan\" = {\"sections\": [{\"name\", \"length_bars\", "
        "\"energy\" (0-1, shape a real dynamic arc: calm intro, big "
        "choruses)}...], \"instrumentation\": [track types]}. "
        f"Request: {prompt}")
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
        lo, hi = genres.profile_for(fam).tempo
        try:
            bpm = float(p.get("bpm", 0)) or genres.suggest_bpm(fam)
        except (TypeError, ValueError):
            bpm = genres.suggest_bpm(fam)
        spec.update({
            "title": str(p.get("title") or spec["title"])[:80],
            "style": str(p.get("style") or spec["style"]),
            "genre": fam,
            "bpm": min(max(bpm, lo - 15), hi + 15),   # near the genre range
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
# 5. critic (bounded)
# --------------------------------------------------------------------------

_CRITIC_OPS = {"set_clip_fades", "update_track", "add_effect",
               "update_effect", "update_mix", "generate_drums",
               "generate_bassline", "generate_chords", "generate_melody",
               "write_notes"}


def _critic_round(project: SongProject, metrics: dict, language: str,
                  job: dict) -> list[str]:
    issues = list(metrics["incomplete_reasons"])
    if metrics["static_arrangement"]:
        issues.append("the same instruments play in every section — vary "
                      "the arrangement")
    issues += metrics["density_flags"]
    if metrics["clipping"]:
        issues.append("stems clipping: lower track volumes")
    if not issues:
        return []
    ask = ("You are the producer doing ONE polish pass. Fix ONLY these "
           "measured issues — nothing else, and every effect must earn its "
           "place (no stacking):\n- " + "\n- ".join(issues[:8])
           + "\nFinish the song: intro fade-in and outro fade-out via "
             "set_clip_fades where musical.")
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

        _set(job, stage="metrics", progress=0.7)
        metrics = arrangement_metrics.analyse(project)
        job["metrics_before"] = arrangement_metrics.summary_line(metrics)

        if _llm_available():
            for _ in range(MAX_CRITIC_ROUNDS):
                clean = (metrics["is_complete_song"]
                         and not metrics["static_arrangement"]
                         and not metrics["density_flags"]
                         and not metrics["clipping"])
                if clean:
                    break
                _set(job, stage="critic", progress=0.85)
                fixes = _critic_round(project, metrics, language, job)
                if not fixes:
                    break
                job.setdefault("log", []).extend(fixes)
                project_repo.save_project(project)
                new_metrics = arrangement_metrics.analyse(project)
                if new_metrics["completeness"] < metrics["completeness"]:
                    break                      # never accept a regression
                metrics = new_metrics

        job["metrics"] = {k: metrics[k] for k in
                          ("completeness", "key_ratio", "duration_seconds",
                           "is_complete_song", "static_arrangement")}
        _ledger_append(project, prompt, job, time.time() - t0)
        _set(job, stage="done", progress=1.0, status="done",
             summary=arrangement_metrics.summary_line(metrics))
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
