from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..models.asset import Asset, AssetMetadataPatch
from ..services import asset_repo, asset_scanner

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("")
def list_all(asset_type: str | None = None) -> list[Asset]:
    return asset_repo.list_assets(asset_type)


@router.get("/scores")
def list_scores() -> list[Asset]:
    return asset_repo.list_assets("score")


@router.get("/soundfonts")
def list_soundfonts() -> list[Asset]:
    return asset_repo.list_assets("soundfont")


@router.get("/samples")
def list_samples() -> list[Asset]:
    return asset_repo.list_assets("sample")


@router.get("/voice-recordings")
def list_voice_recordings() -> list[Asset]:
    return asset_repo.list_assets("voice_recording")


@router.post("/rescan")
def rescan() -> dict:
    return asset_scanner.rescan()


@router.get("/search")
def search(text: str | None = None, tags: str | None = None,
           bpm_min: float | None = None, bpm_max: float | None = None,
           key: str | None = None, asset_type: str | None = None) -> list[dict]:
    from ..services import sample_analysis
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return sample_analysis.search_assets(
        text=text, tags=tag_list, bpm_min=bpm_min, bpm_max=bpm_max,
        key=key, asset_type=asset_type)


@router.get("/{asset_id}")
def get_one(asset_id: str) -> Asset:
    asset = asset_repo.get_asset(asset_id)
    if asset is None:
        raise HTTPException(404, "asset not found")
    return asset


@router.patch("/{asset_id}/metadata")
def patch_metadata(asset_id: str, patch: AssetMetadataPatch) -> Asset:
    asset = asset_repo.update_metadata(
        asset_id, tags=patch.tags, user_description=patch.user_description,
        license_notes=patch.license_notes)
    if asset is None:
        raise HTTPException(404, "asset not found")
    return asset


_MEDIA_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".flac": "audio/flac",
                ".ogg": "audio/ogg", ".aiff": "audio/aiff", ".aif": "audio/aiff",
                ".m4a": "audio/mp4", ".mid": "audio/midi", ".midi": "audio/midi",
                ".pdf": "application/pdf"}


@router.get("/{asset_id}/file")
def serve_file(asset_id: str) -> FileResponse:
    """Serve the asset file for preview/download (read-only)."""
    asset = asset_repo.get_asset(asset_id)
    if asset is None:
        raise HTTPException(404, "asset not found")
    path = Path(asset.original_path)
    if not path.exists():
        raise HTTPException(410, "file is missing on disk")
    media = _MEDIA_TYPES.get(asset.extension, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=asset.filename)


@router.get("/{asset_id}/soundfont-presets")
def soundfont_presets(asset_id: str) -> dict:
    """Preset inventory (name/bank/program) of a SoundFont asset."""
    asset = asset_repo.get_asset(asset_id)
    if asset is None:
        raise HTTPException(404, "asset not found")
    if asset.asset_type != "soundfont":
        raise HTTPException(400, "not a soundfont")
    from ..services.sf2_parser import get_preset_inventory
    return get_preset_inventory(asset.id, Path(asset.original_path)) or {}


@router.post("/{asset_id}/analyse")
def analyse(asset_id: str) -> dict:
    from ..services import sample_analysis
    asset = asset_repo.get_asset(asset_id)
    if asset is None:
        raise HTTPException(404, "asset not found")
    if asset.asset_type not in ("sample", "voice_recording"):
        raise HTTPException(400, f"cannot analyse asset of type {asset.asset_type}")
    return sample_analysis.analyse_asset(asset)
