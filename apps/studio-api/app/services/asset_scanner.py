"""AssetScanner: discover user assets in the workspace folders.

Rules:
- never modify, move or rename original files
- detect new files, detect content changes via hash
- mark files that disappeared as missing (metadata is kept)
- preserve user metadata (tags, descriptions, license notes) on rescan
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_config
from ..models.asset import (AUDIO_EXTENSIONS, SCORE_EXTENSIONS,
                            SOUNDFONT_EXTENSIONS, Asset)
from . import asset_repo

log = logging.getLogger(__name__)

# Hashing 5 GB of samples fully on every scan would be slow; hash first+last
# 64 KB plus size, which reliably detects content changes for audio files.
_HASH_CHUNK = 65536


def _content_hash(path: Path, size: int) -> str:
    h = hashlib.sha256()
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(_HASH_CHUNK))
        if size > 2 * _HASH_CHUNK:
            f.seek(-_HASH_CHUNK, 2)
            h.update(f.read(_HASH_CHUNK))
    return h.hexdigest()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _scan_folder(folder: Path, asset_type: str, extensions: set[str],
                 stats: dict) -> set[str]:
    """Scan one folder; returns the set of relative paths seen."""
    cfg = get_config()
    seen: set[str] = set()
    if not folder.exists():
        return seen
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        rel = path.relative_to(cfg.root).as_posix()
        seen.add(rel)
        try:
            stat = path.stat()
            chash = _content_hash(path, stat.st_size)
        except OSError as e:
            log.warning("cannot read %s: %s", path, e)
            continue
        existing = asset_repo.get_asset_by_relative_path(rel)
        if existing is None:
            asset = Asset(
                id=uuid.uuid4().hex,
                asset_type=asset_type,  # type: ignore[arg-type]
                filename=path.name,
                original_path=str(path),
                relative_path=rel,
                extension=path.suffix.lower(),
                file_size=stat.st_size,
                content_hash=chash,
                modified_at=_iso(stat.st_mtime),
                created_at=_iso(stat.st_ctime),
            )
            asset_repo.upsert_asset(asset)
            stats["new"] += 1
        else:
            changed = existing.content_hash != chash
            if changed or existing.is_missing:
                # file content changed or file came back: refresh file facts,
                # keep user metadata untouched
                existing.file_size = stat.st_size
                existing.content_hash = chash
                existing.modified_at = _iso(stat.st_mtime)
                existing.is_missing = False
                if changed:
                    existing.analysis_status = "pending"
                    stats["changed"] += 1
                asset_repo.upsert_asset(existing)
            else:
                stats["unchanged"] += 1
    return seen


def rescan() -> dict:
    """Scan all asset folders. Returns scan statistics."""
    cfg = get_config()
    stats = {"new": 0, "changed": 0, "unchanged": 0, "missing": 0}
    seen: set[str] = set()
    seen |= _scan_folder(cfg.scores_dir, "score", SCORE_EXTENSIONS, stats)
    seen |= _scan_folder(cfg.soundfonts_dir, "soundfont", SOUNDFONT_EXTENSIONS, stats)
    seen |= _scan_folder(cfg.samples_dir, "sample", AUDIO_EXTENSIONS, stats)
    seen |= _scan_folder(cfg.voice_recordings_dir, "voice_recording",
                         AUDIO_EXTENSIONS, stats)

    # mark scanned-type assets whose file disappeared (never delete metadata)
    for asset in asset_repo.list_assets():
        if asset.asset_type in ("score", "soundfont", "sample", "voice_recording") \
                and asset.relative_path not in seen and not asset.is_missing:
            asset.is_missing = True
            asset_repo.upsert_asset(asset)
            stats["missing"] += 1
    log.info("rescan complete: %s", stats)
    return stats
