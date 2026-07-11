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
                           user_notes: str = Form(""),
                           tags: str = Form("")) -> Asset:
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
        source=source, user_description=user_notes,
        tags=[t.strip() for t in tags.split(",") if t.strip()])
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


# --------------------------------------------------------------------------
# guided recording wizard
# --------------------------------------------------------------------------

@router.get("/device")
def device() -> dict:
    """Detected acceleration (CUDA > MPS > CPU) + honest training expectation."""
    from ..services.voice_wizard import TIER_EPOCHS, detect_device
    return {**detect_device(), "tiers": TIER_EPOCHS}


@router.get("/wizard/exercises")
def wizard_exercises(language: str = "en") -> list[dict]:
    """Exercises plus their karaoke guide (fixed notes/phrases) for the given
    language, so the UI can show exactly what to sing and when."""
    from ..services.voice_wizard import EXERCISES, guide_for
    return [{**e, "guide": guide_for(e["id"], language)} for e in EXERCISES]


@router.post("/engine/install")
def voice_engine_install() -> dict:
    """Install the optional neural voice stack (torch + XTTS) into the running
    venv, matched to the detected device. Runs in the background; poll
    /voice/engine/status for progress."""
    from ..services.voice_engine_install import start_install
    return start_install()


@router.get("/engine/status")
def voice_engine_status(log_lines: int = 60) -> dict:
    from ..services.voice_engine_install import install_status
    return install_status(log_lines)


@router.get("/wizard/guide/{exercise_id}")
def wizard_guide(exercise_id: str) -> FileResponse:
    """Synthesized guide clip the user hears before attempting a take."""
    from ..services.voice_wizard import EXERCISES, render_guide
    if exercise_id not in {e["id"] for e in EXERCISES}:
        raise HTTPException(404, "unknown exercise")
    return FileResponse(render_guide(exercise_id), media_type="audio/wav")


@router.post("/recordings/{asset_id}/qa")
def recording_qa(asset_id: str) -> dict:
    """Per-take quality check: clipping, noise floor, level, silence."""
    from ..services.voice_wizard import qa_take
    asset = asset_repo.get_asset(asset_id)
    if asset is None or asset.asset_type != "voice_recording":
        raise HTTPException(404, "voice recording not found")
    return qa_take(Path(asset.original_path))


@router.post("/recordings/{asset_id}/range-test")
def recording_range(asset_id: str) -> dict:
    """Detect the singer's comfortable range from a recorded scale."""
    from ..services.voice_wizard import detect_range
    asset = asset_repo.get_asset(asset_id)
    if asset is None or asset.asset_type != "voice_recording":
        raise HTTPException(404, "voice recording not found")
    result = detect_range(Path(asset.original_path))
    if "error" in result:
        raise HTTPException(422, result["error"])
    return result


@router.get("/profiles/{profile_id}/confidence")
def profile_confidence(profile_id: str) -> dict:
    """Honest expectation tags computed from the profile's training material."""
    from ..services.audio_io import AudioReadError, read_audio
    from ..services.voice_wizard import profile_confidence as conf
    profile = voice_profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, "voice profile not found")
    recordings = []
    for rid in profile.source_recording_ids:
        a = asset_repo.get_asset(rid)
        if a is None or a.is_missing:
            continue
        entry = {"minutes": 0.0, "wizard_take": "wizard" in (a.tags or [])}
        try:
            data, rate = read_audio(Path(a.original_path))
            entry["minutes"] = len(data) / rate / 60
        except AudioReadError:
            pass
        recordings.append(entry)
    return conf(profile, recordings)


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


from fastapi.responses import FileResponse
from pydantic import BaseModel


class VoiceTestRequest(BaseModel):
    text: str = "This is my studio voice. One two three, let's sing something beautiful."


@router.post("/profiles/{profile_id}/test")
def test_voice(profile_id: str, req: VoiceTestRequest) -> FileResponse:
    """Synthesize a short sentence in this voice through the full fidelity
    chain (XTTS clone → trained RVC model when ready). Returns a WAV."""
    profile = voice_profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, "voice profile not found")
    if not profile.consent_confirmed:
        raise HTTPException(403, "profile has no confirmed consent")
    from ..services.vocal_clone import (CloneSingingEngine, _tts_line,
                                        clone_engine_available)
    if not clone_engine_available():
        raise HTTPException(503, "The AI voice engine (XTTS) is not installed "
                            "in this build. Your recordings and profile are "
                            "saved — install the optional voice add-on to "
                            "enable cloning and singing previews.")
    engine = CloneSingingEngine(profile)
    refs = engine._speaker_wavs()
    if not refs:
        raise HTTPException(422, "profile has no usable source recordings")
    try:
        audio, rate, _ = _tts_line(req.text.strip()[:300], refs, "en")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"synthesis failed: {e}")

    from ..services.audio_io import write_wav
    cfg = get_config()
    out = cfg.analysis_cache_dir / "tts" / f"preview_{profile_id}.wav"
    write_wav(out, audio[:, None] if audio.ndim == 1 else audio, rate)

    from ..services.rvc_convert import convert_stem, rvc_model_ready
    rvc_used = False
    if rvc_model_ready(profile):
        rvc_out = out.with_name(out.stem + "_rvc.wav")
        # spoken test sentence — keep natural speech pitch
        if not convert_stem(out, rvc_out, profile, autotune=False) and rvc_out.exists():
            out = rvc_out
            rvc_used = True
    return FileResponse(out, media_type="audio/wav",
                        filename=f"voice_test{'_rvc' if rvc_used else ''}.wav",
                        headers={"X-RVC-Applied": str(rvc_used)})


@router.post("/profiles/{profile_id}/train")
def start_training(profile_id: str, tier: str = "full") -> dict:
    """Launch async RVC training for this voice (detached process). One at a
    time; progress shows in the profile badge. tier: 'quick' (~60 epochs,
    keeps CPU/MPS machines practical) or 'full' (200 epochs)."""
    import subprocess

    from ..services.voice_wizard import TIER_EPOCHS
    if tier not in TIER_EPOCHS:
        raise HTTPException(422, f"tier must be one of {list(TIER_EPOCHS)}")

    from ..services.rvc_convert import (_applio_dir, _applio_python,
                                        rvc_available, training_status)
    profile = voice_profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, "voice profile not found")
    if not profile.consent_confirmed:
        raise HTTPException(403, "profile has no confirmed consent")
    if not rvc_available():
        raise HTTPException(503, "training stack not installed (tools/Applio)")
    status = training_status(profile)
    if status["ready"] and status["stage"] == "complete":
        return {"started": False, "message": "this voice is already trained"}
    for other in voice_profiles.list_profiles():
        if training_status(other)["training_active"]:
            raise HTTPException(409, f"another voice ({other.name!r}) is "
                                     "training — the GPU handles one at a time")

    script = get_config().root / "tools" / "train_rvc.py"
    log_dir = get_config().root / "tools"
    # CREATE_NO_WINDOW: no console window pops up — progress is available in
    # the app via GET /voice/training-log instead
    creationflags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | NEW_PROCESS_GROUP
    with open(log_dir / "rvc-training-stdout.log", "ab") as out, \
         open(log_dir / "rvc-training-stderr.log", "ab") as err:
        subprocess.Popen([str(_applio_python()), str(script), profile_id,
                          str(TIER_EPOCHS[tier])],
                         cwd=str(_applio_dir()), stdout=out, stderr=err,
                         creationflags=creationflags)
    return {"started": True, "tier": tier, "epochs": TIER_EPOCHS[tier],
            "message": f"{tier} training of {profile.name!r} started "
                       f"({TIER_EPOCHS[tier]} epochs) — it runs in the "
                       "background; the badge shows progress and renders "
                       "improve as checkpoints land"}


@router.get("/training-log")
def training_log(lines: int = 200) -> dict:
    """Tail of the RVC training logs — shown on demand in the UI instead of
    a console window."""
    root = get_config().root / "tools"
    out: list[str] = []
    for name in ("rvc-training.log", "rvc-training-stderr.log"):
        p = root / name
        if p.exists():
            tail = p.read_text(encoding="utf-8",
                               errors="replace").splitlines()[-lines:]
            if tail:
                out.append(f"── {name} ──")
                out.extend(tail)
    return {"lines": out[-lines * 2:]}


@router.get("/profiles/{profile_id}/export")
def export_voice(profile_id: str):
    """Portable voice bundle: profile + consent + source recordings + trained
    RVC weights in one zip — importable on any mITyStudio."""
    from fastapi.responses import FileResponse

    from ..services import bundles
    try:
        path = bundles.export_voice_bundle(profile_id)
    except KeyError:
        raise HTTPException(404, "voice profile not found")
    return FileResponse(path, filename=path.name,
                        media_type="application/zip")


@router.post("/profiles/import")
async def import_voice(file: UploadFile) -> dict:
    from ..services import bundles
    tmp_dir = get_config().analysis_cache_dir / "imports"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_dir / (file.filename or "voice.zip")
    tmp.write_bytes(await file.read())
    try:
        return bundles.import_voice_bundle(tmp)
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        tmp.unlink(missing_ok=True)


@router.get("/rvc-status")
def rvc_status() -> dict:
    """Training/readiness of the per-voice RVC fidelity models."""
    from ..services.rvc_convert import rvc_available, training_status
    return {"rvc_installed": rvc_available(),
            "models": [training_status(p) for p in voice_profiles.list_profiles()]}


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
