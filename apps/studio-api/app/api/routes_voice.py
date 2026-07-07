from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import get_config
from ..models.asset import AUDIO_EXTENSIONS, Asset
from ..models.voice import CreateVoiceProfileRequest, VoiceProfile
from ..services import asset_repo, voice_profiles
from ..services.voice_profiles import ConsentRequired, InvalidSourceRecording

router = APIRouter(prefix="/api/voice", tags=["voice"])

# browsers record webm/ogg; accept those alongside standard audio formats
_UPLOAD_EXTENSIONS = AUDIO_EXTENSIONS | {".webm"}


@router.post("/recordings/upload", status_code=201)
async def upload_recording(file: UploadFile = File(...),
                           source: str = Form("upload"),
                           user_notes: str = Form("")) -> Asset:
    cfg = get_config()
    original_name = file.filename or "recording.wav"
    ext = Path(original_name).suffix.lower()
    if ext not in _UPLOAD_EXTENSIONS:
        raise HTTPException(422, f"unsupported audio format {ext!r}")
    if source not in ("upload", "live_recording"):
        raise HTTPException(422, "source must be upload or live_recording")

    stem = re.sub(r"[^\w\- ]+", "_", Path(original_name).stem)[:80] or "recording"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = cfg.voice_recordings_dir / f"{stem}_{stamp}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    if not content:
        raise HTTPException(422, "uploaded file is empty")
    dest.write_bytes(content)

    asset = Asset(
        id=uuid.uuid4().hex, asset_type="voice_recording",
        filename=dest.name, original_path=str(dest),
        relative_path=dest.relative_to(cfg.root).as_posix(),
        extension=ext, file_size=len(content),
        modified_at=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
        source=source, user_description=user_notes)
    asset_repo.upsert_asset(asset)

    # best-effort duration/channels metadata (never blocks the upload)
    try:
        from ..services.audio_io import read_audio
        data, rate = read_audio(dest)
        asset.generated_description = (
            f"{len(data) / rate:.2f}s, {data.shape[1]}ch @ {rate}Hz, {source}")
        asset_repo.upsert_asset(asset)
    except Exception:
        asset.generated_description = f"{source} (duration unknown)"
        asset_repo.upsert_asset(asset)
    return asset


@router.get("/profiles")
def list_profiles() -> list[VoiceProfile]:
    return voice_profiles.list_profiles()


@router.post("/profiles", status_code=201)
def create_profile(req: CreateVoiceProfileRequest) -> VoiceProfile:
    try:
        return voice_profiles.create_profile(req)
    except ConsentRequired as e:
        raise HTTPException(403, str(e))
    except InvalidSourceRecording as e:
        raise HTTPException(422, str(e))


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str) -> VoiceProfile:
    p = voice_profiles.get_profile(profile_id)
    if p is None:
        raise HTTPException(404, "voice profile not found")
    return p


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str) -> dict:
    if not voice_profiles.delete_profile(profile_id):
        raise HTTPException(404, "voice profile not found")
    return {"deleted": profile_id}


@router.patch("/profiles/{profile_id}")
def update_profile_notes(profile_id: str, body: dict) -> VoiceProfile:
    p = voice_profiles.get_profile(profile_id)
    if p is None:
        raise HTTPException(404, "voice profile not found")
    for field in ("usage_restrictions", "language_notes", "vocal_range",
                  "performer_alias", "status"):
        if field in body:
            setattr(p, field, body[field])
    voice_profiles.update_profile(p)
    return p
