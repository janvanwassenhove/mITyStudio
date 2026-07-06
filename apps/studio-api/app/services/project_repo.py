"""SongProject persistence: one folder per project under projects/,
containing project.json. Local-first and human-readable."""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from ..config import get_config
from ..models.song import SongProject
from . import asset_repo

log = logging.getLogger(__name__)


class ProjectNotFound(Exception):
    pass


class ProjectValidationFailed(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _project_path(project_id: str):
    return get_config().projects_dir / project_id / "project.json"


def save_project(project: SongProject) -> SongProject:
    project.touch()
    path = _project_path(project.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return project


def load_project(project_id: str) -> SongProject:
    path = _project_path(project_id)
    if not path.exists():
        raise ProjectNotFound(project_id)
    return SongProject.model_validate_json(path.read_text(encoding="utf-8"))


def list_projects() -> list[dict]:
    out = []
    projects_dir = get_config().projects_dir
    if not projects_dir.exists():
        return out
    for p in sorted(projects_dir.iterdir()):
        f = p / "project.json"
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append({
                "id": data.get("id", p.name),
                "title": data.get("title", p.name),
                "style": data.get("style", ""),
                "bpm": data.get("bpm"),
                "key": data.get("key"),
                "updated_at": data.get("updated_at"),
                "track_count": len(data.get("tracks", [])),
            })
        except (json.JSONDecodeError, OSError) as e:
            log.warning("unreadable project %s: %s", p, e)
    out.sort(key=lambda d: d.get("updated_at") or "", reverse=True)
    return out


def validate_project_data(data: dict) -> tuple[SongProject | None, list[str]]:
    """Structural (pydantic) + referential (asset registry) validation."""
    try:
        project = SongProject.model_validate(data)
    except ValidationError as e:
        return None, [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
                      for err in e.errors()]
    errors = validate_references(project)
    return (project, errors)


def validate_references(project: SongProject) -> list[str]:
    """Check that referenced assets exist and are of the right type."""
    errors: list[str] = []
    for t in project.tracks:
        sf_id = t.instrument_config.soundfont_asset_id
        if sf_id:
            a = asset_repo.get_asset(sf_id)
            if a is None:
                errors.append(f"track {t.name!r}: soundfont asset {sf_id} not found")
            elif a.asset_type != "soundfont":
                errors.append(f"track {t.name!r}: asset {sf_id} is {a.asset_type}, not a soundfont")
            elif a.is_missing:
                errors.append(f"track {t.name!r}: soundfont file {a.filename!r} is missing on disk")
        for c in t.clips:
            if c.clip_type == "sample" and c.source_asset_id:
                a = asset_repo.get_asset(c.source_asset_id)
                if a is None:
                    errors.append(f"track {t.name!r}: sample asset {c.source_asset_id} not found")
                elif a.asset_type not in ("sample", "voice_recording"):
                    errors.append(f"track {t.name!r}: asset {a.filename!r} is {a.asset_type}, not audio")
                elif a.is_missing:
                    errors.append(f"track {t.name!r}: sample file {a.filename!r} is missing on disk")
        if t.voice_profile_id:
            from . import voice_profiles
            if voice_profiles.get_profile(t.voice_profile_id) is None:
                errors.append(f"track {t.name!r}: voice profile {t.voice_profile_id} not found")
    return errors
