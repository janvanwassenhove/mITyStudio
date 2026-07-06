from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import project_repo, vocal_engine
from ..services.project_repo import ProjectNotFound

router = APIRouter(prefix="/api/projects", tags=["vocals"])


@router.post("/{project_id}/vocals/render")
def render_vocals(project_id: str) -> dict:
    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")
    results = vocal_engine.render_vocal_stems(project)
    project_repo.save_project(project)
    return results
