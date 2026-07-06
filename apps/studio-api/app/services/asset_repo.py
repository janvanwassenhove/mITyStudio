"""Asset registry persistence (SQLite)."""
from __future__ import annotations

import json
from typing import Any

from ..db import get_db
from ..models.asset import Asset

_JSON_FIELDS = ("tags",)
_COLUMNS = ("id", "asset_type", "filename", "original_path", "relative_path",
            "extension", "file_size", "content_hash", "modified_at",
            "created_at", "analysis_status", "tags", "user_description",
            "generated_description", "license_notes", "source", "is_missing")


def _to_asset(row: Any) -> Asset:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    d["is_missing"] = bool(d["is_missing"])
    return Asset(**d)


def upsert_asset(asset: Asset) -> None:
    d = asset.model_dump()
    d["tags"] = json.dumps(d["tags"])
    d["is_missing"] = int(d["is_missing"])
    cols = ", ".join(_COLUMNS)
    placeholders = ", ".join(f":{c}" for c in _COLUMNS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in _COLUMNS if c != "id")
    get_db().execute(
        f"INSERT INTO assets ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        d,
    )
    get_db().commit()


def get_asset(asset_id: str) -> Asset | None:
    row = get_db().execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
    return _to_asset(row) if row else None


def get_asset_by_relative_path(relative_path: str) -> Asset | None:
    row = get_db().execute(
        "SELECT * FROM assets WHERE relative_path=?", (relative_path,)
    ).fetchone()
    return _to_asset(row) if row else None


def list_assets(asset_type: str | None = None, include_missing: bool = True) -> list[Asset]:
    q = "SELECT * FROM assets"
    params: list[Any] = []
    clauses = []
    if asset_type:
        clauses.append("asset_type=?")
        params.append(asset_type)
    if not include_missing:
        clauses.append("is_missing=0")
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY filename COLLATE NOCASE"
    return [_to_asset(r) for r in get_db().execute(q, params).fetchall()]


def update_metadata(asset_id: str, *, tags: list[str] | None = None,
                    user_description: str | None = None,
                    license_notes: str | None = None,
                    generated_description: str | None = None,
                    analysis_status: str | None = None) -> Asset | None:
    asset = get_asset(asset_id)
    if asset is None:
        return None
    if tags is not None:
        asset.tags = tags
    if user_description is not None:
        asset.user_description = user_description
    if license_notes is not None:
        asset.license_notes = license_notes
    if generated_description is not None:
        asset.generated_description = generated_description
    if analysis_status is not None:
        asset.analysis_status = analysis_status  # type: ignore[assignment]
    upsert_asset(asset)
    return asset
