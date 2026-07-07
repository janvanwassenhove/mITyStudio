from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import get_config
from ..models.asset import SCORE_EXTENSIONS, Asset
from ..services import asset_repo, project_repo, score_import
from ..services.score_import import ScoreImportResult

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.post("/upload", status_code=201)
async def upload_score(file: UploadFile = File(...)) -> Asset:
    """Upload a score/chord sheet/tab (MIDI, MusicXML, GP, PDF, or a photo
    as JPG/PNG) into scores/ and register it as a score asset."""
    cfg = get_config()
    name = file.filename or "score"
    ext = Path(name).suffix.lower()
    if ext not in SCORE_EXTENSIONS:
        raise HTTPException(422, f"unsupported score format {ext!r} "
                                 f"(supported: {', '.join(sorted(SCORE_EXTENSIONS))})")
    stem = re.sub(r"[^\w\- ]+", "_", Path(name).stem)[:80] or "score"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = cfg.scores_dir / f"{stem}_{stamp}{ext}"
    content = await file.read()
    if not content:
        raise HTTPException(422, "uploaded file is empty")
    dest.write_bytes(content)
    asset = Asset(
        id=uuid.uuid4().hex, asset_type="score", filename=dest.name,
        original_path=str(dest),
        relative_path=dest.relative_to(cfg.root).as_posix(),
        extension=ext, file_size=len(content),
        modified_at=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(), source="upload")
    asset_repo.upsert_asset(asset)
    return asset


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
