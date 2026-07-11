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


class QuickAddTrackRequest(BaseModel):
    track_type: str
    name: str | None = None
    generate: bool = True                 # create a starter part for the song
    voice_profile_id: str | None = None   # vocal tracks: sing with this voice
    lyrics: list[str] | None = None       # vocal tracks: custom lyric lines
    vocal_style: str = "sing"             # sing | rap
    sections: list[str] | None = None     # vocal: which sections to sing
    #   (ids or names; None = every section that has lyrics — duet support:
    #    give each vocal track its own subset)
    # instrument sound variant (a preset from the SoundFont catalog);
    # None = auto-match at render time
    soundfont_asset_id: str | None = None
    bank: int | None = None
    program: int | None = None
    preset: str = ""


_GENERATOR_FOR_TYPE = {
    "drums": "generate_drums", "bass": "generate_bassline",
    "guitar": "generate_chords", "keys": "generate_chords",
    "strings": "generate_chords", "brass": "generate_chords",
    "synth": "generate_melody",
}


@router.post("/{project_id}/tracks/quick-add")
def quick_add_track(project_id: str, req: QuickAddTrackRequest) -> dict:
    """One-click 'GarageBand style' track: adds the track and (optionally)
    generates a starter part across the whole song. Vocal tracks get lyrics,
    a melody and — if given — a consented voice profile."""
    from ..models.operations import ChatOperation
    from ..services import operation_applier

    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")

    is_vocal = req.track_type in ("lead_vocal", "backing_vocal")
    name = req.name or {"lead_vocal": "Lead Vocal",
                        "backing_vocal": "Backing Vocal"}.get(
        req.track_type, req.track_type.replace("_", " ").title())

    ops: list[ChatOperation] = []
    # an empty project gets a starter structure so there is something to play
    if not project.sections and req.generate:
        for sec, bars, energy in (("Verse", 8, 0.5), ("Chorus", 8, 0.9)):
            ops.append(ChatOperation(op_type="add_section",
                                     params={"name": sec, "length_bars": bars,
                                             "energy": energy}))

    if is_vocal:
        params: dict = {"name": name, "track_type": req.track_type,
                        "vocal_style": req.vocal_style}
        if req.voice_profile_id:
            params["voice_profile_id"] = req.voice_profile_id
        ops.append(ChatOperation(op_type="create_vocal_track", params=params))
        if req.generate:
            lyric_sections = [s for s in project.sections
                              if any(l.section_id == s.id
                                     for l in project.lyrics.lines)]
            if req.lyrics:
                # custom lyrics: write them, then sing the last section
                ops.append(ChatOperation(op_type="rewrite_lyrics",
                                         params={"lines": req.lyrics,
                                                 "section": "__last__"}))
                ops.append(ChatOperation(op_type="generate_melody",
                                         params={"track": name,
                                                 "track_type": req.track_type}))
            elif lyric_sections:
                # existing lyrics: put a singing clip on every lyric section
                # (or the requested subset — duet support)
                wanted = req.sections
                targets = [s for s in lyric_sections
                           if wanted is None or s.id in wanted
                           or s.name in wanted]
                for s in targets or lyric_sections:
                    ops.append(ChatOperation(
                        op_type="generate_melody",
                        params={"section": s.id, "track": name,
                                "track_type": req.track_type}))
            else:
                lines = [
                    f"This is the song they call {project.title}",
                    "Every beat is carrying us away",
                    "Sing it back like you mean it",
                    "We were made for days like today",
                ]
                ops.append(ChatOperation(op_type="rewrite_lyrics",
                                         params={"lines": lines,
                                                 "section": "__last__"}))
                ops.append(ChatOperation(op_type="generate_melody",
                                         params={"track": name,
                                                 "track_type": req.track_type}))
    else:
        ops.append(ChatOperation(op_type="add_track",
                                 params={"name": name,
                                         "track_type": req.track_type}))
        if req.soundfont_asset_id and req.bank is not None and req.program is not None:
            ops.append(ChatOperation(op_type="assign_soundfont",
                                     params={"track": name,
                                             "soundfont_asset_id": req.soundfont_asset_id,
                                             "bank": req.bank,
                                             "program": req.program,
                                             "preset": req.preset}))
        gen = _GENERATOR_FOR_TYPE.get(req.track_type)
        if req.generate and gen:
            ops.append(ChatOperation(op_type=gen,
                                     params={"section": "all", "track": name,
                                             "track_type": req.track_type}))

    # "__last__" sentinel → default section resolution in the applier
    for op in ops:
        if op.params.get("section") == "__last__":
            op.params.pop("section")

    results = operation_applier.apply_operations(project, ops)
    errors = [r.error for r in results if not r.applied and r.error]
    if any(r.applied for r in results):
        ref_errors = project_repo.validate_references(project)
        if ref_errors:
            raise HTTPException(422, ref_errors)
        project_repo.save_project(project)
    return {"track_name": name,
            "applied": [r.summary for r in results if r.applied],
            "errors": errors,
            "project": project.model_dump()}


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
