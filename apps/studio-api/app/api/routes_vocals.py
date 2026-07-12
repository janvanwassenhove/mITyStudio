from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import project_repo, vocal_engine
from ..services.project_repo import ProjectNotFound

router = APIRouter(prefix="/api/projects", tags=["vocals"])


@router.post("/{project_id}/vocals/sing-lyrics")
def sing_lyrics(project_id: str, track_id: str | None = None) -> dict:
    """Give every section that has lyrics a sung melody on the Lead Vocal
    track (created if missing). One click from lyrics to singing.
    track_id targets a specific vocal track instead (e.g. to re-phrase after
    changing its singing pace)."""
    from ..models.operations import ChatOperation
    from ..services import operation_applier

    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    lyric_sections = [s for s in project.sections
                      if any(l.section_id == s.id for l in project.lyrics.lines)]
    if not lyric_sections:
        raise HTTPException(422, "this project has no lyrics yet — add some "
                                 "via the chat ('add lyrics about …') first")
    track_ref, track_type = "Lead Vocal", "lead_vocal"
    if track_id:
        tr = next((t for t in project.tracks if t.id == track_id), None)
        if tr is None or tr.track_type not in ("lead_vocal", "backing_vocal"):
            raise HTTPException(404, "vocal track not found")
        track_ref, track_type = tr.id, tr.track_type
    ops = [ChatOperation(op_type="generate_melody",
                         params={"section": s.id, "track": track_ref,
                                 "track_type": track_type})
           for s in lyric_sections]
    results = operation_applier.apply_operations(project, ops)
    errors = [r.error for r in results if not r.applied and r.error]
    if any(r.applied for r in results):
        project_repo.save_project(project)
    return {"sections_sung": sum(1 for r in results if r.applied),
            "errors": errors}


@router.post("/{project_id}/vocals/render")
def render_vocals(project_id: str) -> dict:
    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    results = vocal_engine.render_vocal_stems(project)
    project_repo.save_project(project)
    return results
