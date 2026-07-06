"""SQLite database module.

Holds the asset registry, sample analyses, voice profiles, LLM settings and
export jobs. Generated metadata only — original asset files are never touched.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from .config import get_config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    asset_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    extension TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL DEFAULT '',
    modified_at TEXT,
    created_at TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'pending',
    tags TEXT NOT NULL DEFAULT '[]',
    user_description TEXT NOT NULL DEFAULT '',
    generated_description TEXT NOT NULL DEFAULT '',
    license_notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'scan',
    is_missing INTEGER NOT NULL DEFAULT 0,
    UNIQUE(relative_path)
);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);

CREATE TABLE IF NOT EXISTS sample_analyses (
    asset_id TEXT PRIMARY KEY REFERENCES assets(id),
    analysis TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS voice_profiles (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS export_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    data TEXT NOT NULL
);
"""


def get_db() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    db_path = str(get_config().db_path)
    if conn is None or getattr(_local, "db_path", None) != db_path:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
        _local.db_path = db_path
    return conn


def close_db() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
        _local.db_path = None


def row_to_dict(row: sqlite3.Row, json_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    d = dict(row)
    for f in json_fields:
        if f in d and isinstance(d[f], str):
            d[f] = json.loads(d[f])
    return d
