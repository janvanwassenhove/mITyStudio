from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import get_config
from ..models.song import SongProject
from ..services import midi_export, project_repo
from ..services.project_repo import ProjectNotFound
from ..services.render import sample_renderer, soundfont_renderer

router = APIRouter(prefix="/api/projects", tags=["render"])


def _load(project_id: str) -> SongProject:
    try:
        return project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")


@router.post("/{project_id}/midi/export")
def export_midi(project_id: str) -> dict:
    project = _load(project_id)
    try:
        outputs = midi_export.export_project_midi(project)
    except midi_export.MidiExportError as e:
        raise HTTPException(422, str(e))
    project_repo.save_project(project)
    return {"midi_files": outputs, "count": len(outputs)}


@router.post("/{project_id}/render/instrument-stems")
def render_instrument_stems(project_id: str) -> dict:
    project = _load(project_id)
    results = soundfont_renderer.render_instrument_stems(project)
    project_repo.save_project(project)
    return results


@router.post("/{project_id}/render/sample-stems")
def render_sample_stems(project_id: str) -> dict:
    project = _load(project_id)
    results = sample_renderer.render_sample_stems(project)
    project_repo.save_project(project)
    return results


@router.post("/{project_id}/render/apply-effects")
def apply_effects(project_id: str) -> dict:
    """Effects are applied non-destructively during mixdown; this endpoint
    reports which effect chains would apply and validates them."""
    project = _load(project_id)
    from ..services.render.effects import PLACEHOLDER_EFFECTS
    report = []
    for t in project.tracks:
        enabled = [e for e in t.effects.effects if e.enabled]
        if enabled:
            report.append({
                "track": t.name,
                "effects": [e.effect_type for e in enabled],
                "placeholders": [e.effect_type for e in enabled
                                 if e.effect_type in PLACEHOLDER_EFFECTS],
            })
    return {"tracks_with_effects": report,
            "note": "effects are applied during mixdown (non-destructive)"}


@router.get("/{project_id}/stems/{track_id}/file")
def serve_stem(project_id: str, track_id: str, stem_type: str | None = None) -> FileResponse:
    project = _load(project_id)
    stems = [s for s in project.stems if s.track_id == track_id]
    if stem_type:
        stems = [s for s in stems if s.stem_type == stem_type]
    if not stems:
        raise HTTPException(404, "stem not found")
    path = get_config().root / stems[0].path
    if not path.exists():
        raise HTTPException(410, "stem file missing on disk")
    return FileResponse(path, media_type="audio/wav", filename=path.name)
