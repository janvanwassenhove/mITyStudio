from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..models.song import SongProject
from ..services import playback_manifest, project_repo
from ..services.project_repo import ProjectNotFound

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
    return project_repo.save_project(project)


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
