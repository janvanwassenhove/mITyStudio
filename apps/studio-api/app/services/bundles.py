"""Portable bundles: export/import a project (with every referenced sample,
soundfont and voice) or a single trained AI voice, as one zip. Reloading a
bundle on another machine reproduces the song — assets are registered, voice
profiles recreated, trained RVC weights installed, and stems re-render from
the imported sources.

Zip layouts
  voice bundle:
    voice.json                    {"profile": ..., "assets": [recording Assets]}
    recordings/<filename>
    rvc/<file>.pth / .index       (trained weights when present)
  project bundle:
    project.json
    manifest.json                 {"assets": [Asset dumps], "voices": [ids]}
    files/samples/<filename>
    files/soundfonts/<filename>
    voices/<profile_id>/…         (embedded voice bundles)
"""
from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

from ..config import get_config
from ..models.asset import Asset
from ..models.song import SongProject, new_id
from ..models.voice import VoiceProfile
from . import asset_repo, project_repo, voice_profiles

log = logging.getLogger(__name__)

_TYPE_DIRS = {"sample": "samples", "soundfont": "soundfonts",
              "voice_recording": "voices/recordings", "score": "scores"}


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------

def _add_asset_file(zf: zipfile.ZipFile, asset: Asset, arc_prefix: str) -> bool:
    src = Path(asset.original_path)
    if not src.exists():
        src = get_config().root / asset.relative_path
    if not src.exists():
        return False
    zf.write(src, f"{arc_prefix}/{asset.filename}")
    return True


def _export_voice_into(zf: zipfile.ZipFile, profile: VoiceProfile,
                       prefix: str, warnings: list[str]) -> None:
    from .rvc_convert import find_model_files
    rec_ids = list(profile.source_recording_ids)
    if profile.consent_recording_id:
        rec_ids.append(profile.consent_recording_id)
    assets = []
    for rid in dict.fromkeys(rec_ids):
        a = asset_repo.get_asset(rid)
        if a is None:
            warnings.append(f"voice {profile.name!r}: recording {rid} missing")
            continue
        if _add_asset_file(zf, a, f"{prefix}/recordings"):
            assets.append(a.model_dump())
        else:
            warnings.append(f"voice {profile.name!r}: file for "
                            f"{a.filename!r} not found")
    weights, index = find_model_files(profile)
    for f in (weights, index):
        if f is not None and f.exists():
            zf.write(f, f"{prefix}/rvc/{f.name}")
    zf.writestr(f"{prefix}/voice.json", json.dumps(
        {"profile": profile.model_dump(), "assets": assets}, indent=1))


def export_voice_bundle(profile_id: str) -> Path:
    profile = voice_profiles.get_profile(profile_id)
    if profile is None:
        raise KeyError("voice profile not found")
    cfg = get_config()
    out_dir = cfg.root / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in profile.name if c.isalnum() or c in " -_")[:40].strip() or "voice"
    out = out_dir / f"{safe}.mityvoice.zip"
    warnings: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        _export_voice_into(zf, profile, ".", warnings)
    if warnings:
        log.warning("voice export warnings: %s", warnings)
    return out


def export_project_bundle(project_id: str) -> Path:
    project = project_repo.load_project(project_id)
    cfg = get_config()
    out_dir = cfg.root / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in project.title if c.isalnum() or c in " -_")[:40].strip() or "project"
    out = out_dir / f"{safe}.mityproject.zip"

    # referenced assets: samples on clips, soundfonts on tracks
    asset_ids: set[str] = set()
    voice_ids: set[str] = set()
    for t in project.tracks:
        if t.instrument_config.soundfont_asset_id:
            asset_ids.add(t.instrument_config.soundfont_asset_id)
        if t.voice_profile_id:
            voice_ids.add(t.voice_profile_id)
        for c in t.clips:
            if c.source_asset_id:
                asset_ids.add(c.source_asset_id)

    warnings: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        dump = project.model_dump()
        dump["stems"] = []          # stems re-render from imported sources
        zf.writestr("project.json", json.dumps(dump, indent=1))
        manifest_assets = []
        for aid in sorted(asset_ids):
            a = asset_repo.get_asset(aid)
            if a is None:
                warnings.append(f"asset {aid} not in registry — skipped")
                continue
            sub = _TYPE_DIRS.get(a.asset_type, a.asset_type)
            if _add_asset_file(zf, a, f"files/{sub}"):
                manifest_assets.append(a.model_dump())
            else:
                warnings.append(f"file missing for {a.filename!r} — skipped")
        for vid in sorted(voice_ids):
            profile = voice_profiles.get_profile(vid)
            if profile is None:
                warnings.append(f"voice profile {vid} not found — skipped")
                continue
            _export_voice_into(zf, profile, f"voices/{vid}", warnings)
        zf.writestr("manifest.json", json.dumps(
            {"assets": manifest_assets, "voices": sorted(voice_ids),
             "warnings": warnings}, indent=1))
    return out


# --------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------

def _install_file(zf: zipfile.ZipFile, arcname: str, dump: dict,
                  warnings: list[str]) -> dict | None:
    """Extract one asset file into the workspace and register it. Returns the
    (possibly id-remapped) asset dump, or None when the file is unusable."""
    cfg = get_config()
    sub = _TYPE_DIRS.get(dump["asset_type"], dump["asset_type"])
    target_dir = cfg.root / sub
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / dump["filename"]
    try:
        data = zf.read(arcname)
    except KeyError:
        warnings.append(f"{dump['filename']!r} missing from bundle")
        return None
    if target.exists() and target.stat().st_size != len(data):
        stem, dot, ext = dump["filename"].rpartition(".")
        target = target_dir / f"{stem or ext} (imported){dot}{ext if stem else ''}"
        dump["filename"] = target.name
    if not target.exists():
        target.write_bytes(data)
    dump["original_path"] = str(target)
    dump["relative_path"] = target.relative_to(cfg.root).as_posix()
    dump["is_missing"] = False

    existing = asset_repo.get_asset(dump["id"])
    if existing is not None and existing.relative_path != dump["relative_path"]:
        dump["id"] = new_id()          # id collision with a different file
    asset_repo.upsert_asset(Asset(**dump))
    return dump


def _import_voice_from(zf: zipfile.ZipFile, prefix: str,
                       warnings: list[str]) -> tuple[str, str] | None:
    """Returns (old_profile_id, new_profile_id) or None."""
    try:
        meta = json.loads(zf.read(f"{prefix}/voice.json"))
    except KeyError:
        warnings.append(f"no voice.json under {prefix!r}")
        return None
    pdump = meta["profile"]
    old_id = pdump["id"]
    # face templates are deliberately NOT part of a bundle (biometric data
    # must not travel with a shared voice), so an imported profile must not
    # claim to be enrolled — and its face consent does not transfer either
    pdump["face_enrolled"] = False
    pdump["face_consent"] = False
    pdump["photo_path"] = ""

    id_map: dict[str, str] = {}
    for adump in meta.get("assets", []):
        old_aid = adump["id"]
        installed = _install_file(zf, f"{prefix}/recordings/{adump['filename']}",
                                  dict(adump), warnings)
        if installed:
            id_map[old_aid] = installed["id"]
    pdump["source_recording_ids"] = [id_map.get(r, r)
                                     for r in pdump["source_recording_ids"]]
    if pdump.get("consent_recording_id"):
        pdump["consent_recording_id"] = id_map.get(
            pdump["consent_recording_id"], pdump["consent_recording_id"])

    if voice_profiles.get_profile(old_id) is not None:
        warnings.append(f"voice {pdump['name']!r} already exists — reused")
        return (old_id, old_id)
    profile = VoiceProfile(**pdump)
    from ..db import get_db
    get_db().execute("INSERT INTO voice_profiles (id, data) VALUES (?, ?)",
                     (profile.id, profile.model_dump_json()))
    get_db().commit()

    # trained RVC weights → where rvc_convert looks for them
    from .rvc_convert import _applio_dir, model_name_for_profile
    logs = _applio_dir() / "logs" / model_name_for_profile(profile)
    for info in zf.infolist():
        if info.filename.startswith(f"{prefix}/rvc/") and not info.is_dir():
            logs.mkdir(parents=True, exist_ok=True)
            (logs / Path(info.filename).name).write_bytes(zf.read(info))
    return (old_id, profile.id)


def import_voice_bundle(path: Path) -> dict:
    warnings: list[str] = []
    with zipfile.ZipFile(path) as zf:
        result = _import_voice_from(zf, ".", warnings)
    if result is None:
        raise ValueError("not a voice bundle (voice.json missing)")
    profile = voice_profiles.get_profile(result[1])
    return {"profile_id": result[1], "name": profile.name if profile else "",
            "warnings": warnings}


def import_project_bundle(path: Path) -> dict:
    warnings: list[str] = []
    with zipfile.ZipFile(path) as zf:
        try:
            pdump = json.loads(zf.read("project.json"))
            manifest = json.loads(zf.read("manifest.json"))
        except KeyError:
            raise ValueError("not a project bundle "
                             "(project.json / manifest.json missing)")
        asset_map: dict[str, str] = {}
        for adump in manifest.get("assets", []):
            sub = _TYPE_DIRS.get(adump["asset_type"], adump["asset_type"])
            installed = _install_file(zf, f"files/{sub}/{adump['filename']}",
                                      dict(adump), warnings)
            if installed:
                asset_map[adump["id"]] = installed["id"]
        voice_map: dict[str, str] = {}
        for vid in manifest.get("voices", []):
            r = _import_voice_from(zf, f"voices/{vid}", warnings)
            if r:
                voice_map[r[0]] = r[1]

    # remap references, fresh ids where needed
    for t in pdump.get("tracks", []):
        cfgd = t.get("instrument_config", {})
        if cfgd.get("soundfont_asset_id"):
            cfgd["soundfont_asset_id"] = asset_map.get(
                cfgd["soundfont_asset_id"], cfgd["soundfont_asset_id"])
        if t.get("voice_profile_id"):
            t["voice_profile_id"] = voice_map.get(
                t["voice_profile_id"], t["voice_profile_id"])
        for c in t.get("clips", []):
            if c.get("source_asset_id"):
                c["source_asset_id"] = asset_map.get(
                    c["source_asset_id"], c["source_asset_id"])
    pdump["stems"] = []
    try:
        project_repo.load_project(pdump["id"])
        pdump["id"] = new_id()          # keep the existing project intact
        pdump["title"] = f"{pdump['title']} (imported)"
    except Exception:  # noqa: BLE001 — id free
        pass
    project = SongProject(**pdump)
    project_repo.save_project(project)
    return {"project_id": project.id, "title": project.title,
            "warnings": warnings}
