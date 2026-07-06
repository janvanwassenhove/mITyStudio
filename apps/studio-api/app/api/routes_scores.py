from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import asset_repo, project_repo, score_import
from ..services.score_import import ScoreImportResult

router = APIRouter(prefix="/api/scores", tags=["scores"])


class ImportToProjectRequest(BaseModel):
    create_project: bool = False
    title: str | None = None
    style: str = ""


@router.post("/{asset_id}/import")
def import_score(asset_id: str, req: ImportToProjectRequest | None = None) -> dict:
    asset = asset_repo.get_asset(asset_id)
    if asset is None:
        raise HTTPException(404, "asset not found")
    if asset.asset_type != "score":
        raise HTTPException(400, f"asset is {asset.asset_type}, not a score")
    if asset.is_missing:
        raise HTTPException(410, "score file is missing on disk")

    result: ScoreImportResult = score_import.import_score(asset)
    payload = result.model_dump()

    if req and req.create_project:
        if not result.supported or not result.detected_tracks:
            raise HTTPException(422, {"message": "score could not be imported",
                                      "warnings": result.warnings})
        title = req.title or asset.filename.rsplit(".", 1)[0]
        project = score_import.project_from_import(result, title, req.style)
        project_repo.save_project(project)
        payload["project_id"] = project.id
    return payload
