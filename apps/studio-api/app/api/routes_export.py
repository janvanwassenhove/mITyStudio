from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..config import get_config
from ..services import mix_export, project_repo
from ..services.mix_export import ExportJob
from ..services.project_repo import ProjectNotFound

router = APIRouter(prefix="/api/projects", tags=["export"])


class ExportMixRequest(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["wav"])


def _load(project_id: str):
    try:
        return project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")


@router.post("/{project_id}/export/mix")
def export_mix(project_id: str, req: ExportMixRequest) -> ExportJob:
    project = _load(project_id)
    formats = [f.lower() for f in req.formats if f.lower() in ("wav", "mp3")]
    if not formats:
        raise HTTPException(422, "formats must include 'wav' and/or 'mp3'")
    return mix_export.export_mix(project, formats)


@router.post("/{project_id}/export/package")
def export_package(project_id: str) -> ExportJob:
    project = _load(project_id)
    return mix_export.export_package(project)


@router.get("/{project_id}/exports")
def list_exports(project_id: str) -> list[ExportJob]:
    _load(project_id)
    return mix_export.list_jobs(project_id)


@router.get("/{project_id}/exports/download")
def download_export(project_id: str, path: str) -> FileResponse:
    cfg = get_config()
    full = (cfg.root / path).resolve()
    exports_root = (cfg.exports_dir / project_id).resolve()
    if not str(full).startswith(str(exports_root)):
        raise HTTPException(403, "path outside project exports")
    if not full.exists():
        raise HTTPException(404, "file not found")
    media = {".wav": "audio/wav", ".mp3": "audio/mpeg",
             ".zip": "application/zip"}.get(full.suffix.lower(),
                                            "application/octet-stream")
    return FileResponse(full, media_type=media, filename=full.name)
