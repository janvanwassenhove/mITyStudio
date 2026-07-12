"""Test fixtures: every test runs against an isolated temp workspace root."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Isolated workspace root with the standard folder layout."""
    from app import config as config_mod
    from app import db as db_mod

    monkeypatch.setenv("MITY_ROOT", str(tmp_path))
    # unit tests exercise the DSP engines; the neural clone engine (XTTS)
    # is too heavy for tests and is validated manually
    monkeypatch.setenv("MITY_DISABLE_CLONE_ENGINE", "1")
    monkeypatch.setenv("MITY_DISABLE_AUDIO_TAGGING", "1")
    config_mod.reset_config()
    cfg = config_mod.get_config()
    cfg.ensure_dirs()
    yield cfg
    db_mod.close_db()
    config_mod.reset_config()


@pytest.fixture()
def client(workspace):
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
