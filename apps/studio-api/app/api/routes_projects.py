from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, UploadFile

from ..config import get_config
from pydantic import BaseModel, Field

from ..models.song import SongProject
from ..services import playback_manifest, project_repo
from ..services.project_repo import ProjectNotFound

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1)
    style: str = ""
    bpm: float = 120.0
    key: str = "C major"
    time_signature: str = "4/4"


@router.post("", status_code=201)
def create_project(req: CreateProjectRequest) -> SongProject:
    project, errors = project_repo.validate_project_data(req.model_dump())
    if project is None:
        raise HTTPException(422, errors)
    return project_repo.save_project(project)


@router.get("")
def list_projects() -> list[dict]:
    return project_repo.list_projects()


class GenerateSongRequest(BaseModel):
    prompt: str = Field(min_length=1)     # "a happy bossa nova pop song"
    language: str = "en"
    force: bool = False                   # allow overwriting existing content


@router.post("/{project_id}/generate-song", status_code=202)
def generate_song(project_id: str, req: GenerateSongRequest) -> dict:
    """Full-song pipeline (docs/song-quality.md §6): producer spec →
    deterministic skeleton → parallel AI composers → metrics → one bounded
    critic pass. Runs as a background job; poll the status endpoint."""
    from ..services import song_pipeline
    try:
        project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    try:
        job = song_pipeline.start(project_id, req.prompt,
                                  language=req.language, force=req.force)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"job_id": job["id"], "status": job["status"]}


@router.get("/{project_id}/generate-song/{job_id}")
def generate_song_status(project_id: str, job_id: str) -> dict:
    from ..services import song_pipeline
    job = song_pipeline.get_job(job_id)
    if job is None or job.get("project_id") != project_id:
        raise HTTPException(404, "job not found")
    return job


@router.get("/{project_id}")
def get_project(project_id: str) -> SongProject:
    try:
        return project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")


@router.put("/{project_id}")
def update_project(project_id: str, data: dict) -> SongProject:
    try:
        project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    data["id"] = project_id
    project, errors = project_repo.validate_project_data(data)
    if project is None:
        raise HTTPException(422, errors)
    if errors:
        raise HTTPException(422, errors)
    saved = project_repo.save_project(project)
    # learn from what the USER keeps/edits (only this route — never the
    # pipeline's internal saves, which would relearn our own defaults)
    from ..services import preferences
    preferences.observe(saved)
    return saved


class QuickAddTrackRequest(BaseModel):
    track_type: str
    name: str | None = None
    generate: bool = True                 # create a starter part for the song
    voice_profile_id: str | None = None   # vocal tracks: sing with this voice
    lyrics: list[str] | None = None       # vocal tracks: custom lyric lines
    vocal_style: str = "sing"             # sing | rap
    sections: list[str] | None = None     # vocal: which sections to sing
    #   (ids or names; None = every section that has lyrics — duet support:
    #    give each vocal track its own subset)
    # instrument sound variant (a preset from the SoundFont catalog);
    # None = auto-match at render time
    soundfont_asset_id: str | None = None
    bank: int | None = None
    program: int | None = None
    preset: str = ""
    synth_patch: str = ""                 # built-in synth patch (no SoundFont)


_GENERATOR_FOR_TYPE = {
    "drums": "generate_drums", "bass": "generate_bassline",
    "guitar": "generate_chords", "keys": "generate_chords",
    "strings": "generate_chords", "brass": "generate_chords",
    "synth": "generate_melody",
}


@router.post("/{project_id}/tracks/quick-add")
def quick_add_track(project_id: str, req: QuickAddTrackRequest) -> dict:
    """One-click 'GarageBand style' track: adds the track and (optionally)
    generates a starter part across the whole song. Vocal tracks get lyrics,
    a melody and — if given — a consented voice profile."""
    from ..models.operations import ChatOperation
    from ..services import operation_applier

    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")

    is_vocal = req.track_type in ("lead_vocal", "backing_vocal")
    name = req.name or {"lead_vocal": "Lead Vocal",
                        "backing_vocal": "Backing Vocal"}.get(
        req.track_type, req.track_type.replace("_", " ").title())
    # Ensure a unique track name. add_track and the generate op both reference
    # the track by name; if a same-named track already exists (e.g. a second
    # "Drums"), the generate op would resolve to the OLD track and the new one
    # would stay empty — the "Write the part for me" no-op bug.
    existing = {t.name.lower() for t in project.tracks}
    if name.lower() in existing:
        base, n = name, 2
        while f"{base} {n}".lower() in existing:
            n += 1
        name = f"{base} {n}"

    ops: list[ChatOperation] = []
    # an empty project gets a starter structure so there is something to play
    if not project.sections and req.generate:
        for sec, bars, energy in (("Verse", 8, 0.5), ("Chorus", 8, 0.9)):
            ops.append(ChatOperation(op_type="add_section",
                                     params={"name": sec, "length_bars": bars,
                                             "energy": energy}))

    if is_vocal:
        params: dict = {"name": name, "track_type": req.track_type,
                        "vocal_style": req.vocal_style}
        if req.voice_profile_id:
            params["voice_profile_id"] = req.voice_profile_id
        ops.append(ChatOperation(op_type="create_vocal_track", params=params))
        if req.generate:
            lyric_sections = [s for s in project.sections
                              if any(l.section_id == s.id
                                     for l in project.lyrics.lines)]
            if req.lyrics:
                # custom lyrics: write them, then sing the last section
                ops.append(ChatOperation(op_type="rewrite_lyrics",
                                         params={"lines": req.lyrics,
                                                 "section": "__last__"}))
                ops.append(ChatOperation(op_type="generate_melody",
                                         params={"track": name,
                                                 "track_type": req.track_type}))
            elif lyric_sections:
                # existing lyrics: put a singing clip on every lyric section
                # (or the requested subset — duet support)
                wanted = req.sections
                targets = [s for s in lyric_sections
                           if wanted is None or s.id in wanted
                           or s.name in wanted]
                for s in targets or lyric_sections:
                    ops.append(ChatOperation(
                        op_type="generate_melody",
                        params={"section": s.id, "track": name,
                                "track_type": req.track_type}))
            else:
                lines = [
                    f"This is the song they call {project.title}",
                    "Every beat is carrying us away",
                    "Sing it back like you mean it",
                    "We were made for days like today",
                ]
                ops.append(ChatOperation(op_type="rewrite_lyrics",
                                         params={"lines": lines,
                                                 "section": "__last__"}))
                ops.append(ChatOperation(op_type="generate_melody",
                                         params={"track": name,
                                                 "track_type": req.track_type}))
    else:
        ops.append(ChatOperation(op_type="add_track",
                                 params={"name": name,
                                         "track_type": req.track_type}))
        # a "synth:<id>" asset id from the catalog picks the built-in synth
        synth_patch = req.synth_patch or (
            (req.soundfont_asset_id or "").split("synth:")[-1]
            if (req.soundfont_asset_id or "").startswith("synth:") else "")
        if synth_patch:
            ops.append(ChatOperation(op_type="assign_synth",
                                     params={"track": name,
                                             "synth_patch": synth_patch}))
        elif req.soundfont_asset_id and req.bank is not None and req.program is not None:
            ops.append(ChatOperation(op_type="assign_soundfont",
                                     params={"track": name,
                                             "soundfont_asset_id": req.soundfont_asset_id,
                                             "bank": req.bank,
                                             "program": req.program,
                                             "preset": req.preset}))
        gen = _GENERATOR_FOR_TYPE.get(req.track_type)
        if req.generate and gen:
            # instant part from the procedural generator; when an AI provider
            # is configured it REFINES this part in the background (an LLM
            # takes minutes to compose — the button must stay instant)
            ops.append(ChatOperation(op_type=gen,
                                     params={"section": "all", "track": name,
                                             "track_type": req.track_type}))

    # "__last__" sentinel → default section resolution in the applier
    for op in ops:
        if op.params.get("section") == "__last__":
            op.params.pop("section")

    results = operation_applier.apply_operations(project, ops)

    # AI-path safety net: if the LLM's ops left the new track without clips,
    # the procedural generator rescues it — the button must never no-op
    if not is_vocal and req.generate:
        gen = _GENERATOR_FOR_TYPE.get(req.track_type)
        trk = next((t for t in project.tracks if t.name == name), None)
        if gen and trk is not None and not trk.clips:
            results.extend(operation_applier.apply_operations(
                project, [ChatOperation(op_type=gen,
                                        params={"section": "all",
                                                "track": name,
                                                "track_type": req.track_type})]))

    errors = [r.error for r in results if not r.applied and r.error]
    ai_refining = False
    if any(r.applied for r in results):
        ref_errors = project_repo.validate_references(project)
        if ref_errors:
            raise HTTPException(422, ref_errors)
        project_repo.save_project(project)
        if not is_vocal and req.generate:
            trk = next((t for t in project.tracks if t.name == name), None)
            if trk is not None:
                ai_refining = _refine_part_in_background(
                    project.id, trk.id, req.track_type)
    return {"track_name": name,
            "applied": [r.summary for r in results if r.applied],
            "errors": errors,
            "ai_refining": ai_refining,
            "project": project.model_dump()}


def _refine_part_in_background(project_id: str, track_id: str,
                               track_type: str) -> bool:
    """When a real LLM provider is configured, have it COMPOSE the new
    track's part (write_notes — actual notes matched to style/key/tempo) and
    replace the instant procedural part when it responds. Runs detached: a
    reasoning model takes minutes, the add-track button stays instant.
    Returns True when a refinement was scheduled."""
    import threading

    from ..services import operation_applier, operation_planner
    from ..services.llm.settings import load_settings
    if load_settings().provider == "mock":
        return False

    def worker() -> None:
        try:
            project = project_repo.load_project(project_id)
            track = next((t for t in project.tracks if t.id == track_id),
                         None)
            if track is None:
                return
            sections = ", ".join(s.name for s in project.sections)
            msg = (f"Compose the {track_type} part for track {track.name!r} "
                   f"(replace its current placeholder part). Song: style "
                   f"{project.style or 'pop'!r}, key {project.key}, "
                   f"{project.bpm:g} bpm; sections: {sections}. Write one op "
                   f"per section and PREFER write_notes with a genre-true "
                   f"pattern (variation and fills welcome, stay in key). Do "
                   f"not modify any other track and do not add sections.")
            _reply, llm_ops, _warnings, usage = operation_planner.plan(
                project, msg)
            allowed = {"write_notes", "generate_drums", "generate_bassline",
                       "generate_chords", "generate_melody"}
            safe = []
            for op in llm_ops:
                if op.op_type not in allowed:
                    continue
                op.params["track"] = track_id   # rename-proof, other-track-proof
                op.params.setdefault("track_type", track_type)
                safe.append(op)
            if not any(op.op_type == "write_notes" for op in safe):
                return   # the LLM added nothing beyond what we already have
            # freshest project state — the user may have edited meanwhile
            project = project_repo.load_project(project_id)
            if not any(t.id == track_id for t in project.tracks):
                return   # track was deleted while the AI was thinking
            results = operation_applier.apply_operations(project, safe)
            if any(r.applied for r in results):
                project_repo.save_project(project)
                log.info("AI refined the %s part for track %s (%s)",
                         track_type, track_id,
                         (usage or {}).get("model", "llm"))
        except Exception as e:  # noqa: BLE001 — refinement is best-effort
            log.warning("AI part refinement failed: %s", e)

    threading.Thread(target=worker, daemon=True,
                     name=f"ai-part-{track_id[:8]}").start()
    return True


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict:
    try:
        project_repo.delete_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    return {"deleted": project_id}


@router.get("/{project_id}/export/bundle")
def export_project_bundle(project_id: str):
    """Portable bundle: project + every referenced sample/soundfont/voice
    (recordings + trained model) in one zip — reimport reproduces the song."""
    from fastapi.responses import FileResponse

    from ..services import bundles
    try:
        path = bundles.export_project_bundle(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    return FileResponse(path, filename=path.name,
                        media_type="application/zip")


@router.post("/import")
async def import_project_bundle(file: UploadFile) -> dict:
    from ..services import bundles
    cfg_tmp = get_config().analysis_cache_dir / "imports"
    cfg_tmp.mkdir(parents=True, exist_ok=True)
    tmp = cfg_tmp / (file.filename or "bundle.zip")
    tmp.write_bytes(await file.read())
    try:
        return bundles.import_project_bundle(tmp)
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        tmp.unlink(missing_ok=True)


class UpdateLyricLineRequest(BaseModel):
    text: str


@router.put("/{project_id}/lyrics/lines/{line_id}")
def update_lyric_line(project_id: str, line_id: str,
                      req: UpdateLyricLineRequest) -> dict:
    """Edit one lyric line. The section's vocal melody is re-synced to the
    new syllables and its stems re-render on the next play."""
    from ..services import lyrics_editing

    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    try:
        result = lyrics_editing.update_line(project, line_id, req.text)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if result["changed"]:
        project_repo.save_project(project)
    result["project"] = project.model_dump()
    return result


@router.get("/{project_id}/lyrics/history")
def lyrics_history(project_id: str) -> list[dict]:
    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    return [{"id": v.id, "timestamp": v.timestamp, "label": v.label,
             "line_count": len(v.lines),
             "preview": (v.lines[0].text[:60] if v.lines else "")}
            for v in reversed(project.lyrics.history)]


@router.post("/{project_id}/lyrics/restore/{version_id}")
def restore_lyrics(project_id: str, version_id: str) -> dict:
    from ..services import lyrics_editing

    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    try:
        result = lyrics_editing.restore_version(project, version_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    project_repo.save_project(project)
    result["project"] = project.model_dump()
    return result


@router.post("/{project_id}/validate")
def validate_project(project_id: str) -> dict:
    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    errors = project_repo.validate_references(project)
    return {"valid": not errors, "errors": errors}


@router.get("/{project_id}/playback-manifest")
def get_playback_manifest(project_id: str) -> dict:
    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    return playback_manifest.build_manifest(project)
