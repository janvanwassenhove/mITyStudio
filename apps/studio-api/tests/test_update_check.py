"""Release update detection (ask-first auto-update)."""
from __future__ import annotations

import io
import json

from app.services import update_check


def test_version_tuple_parsing():
    assert update_check._ver_tuple("v1.1.23") == (1, 1, 23)
    assert update_check._ver_tuple("1.2.0") == (1, 2, 0)
    assert update_check._ver_tuple("") == ()
    assert update_check._ver_tuple("dev") == ()


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_check_detects_newer_release(monkeypatch):
    monkeypatch.setenv("MITY_APP_VERSION", "1.1.5")
    monkeypatch.setattr(update_check, "_cache", {"t": 0.0, "data": None})
    payload = json.dumps({"tag_name": "v1.1.9",
                          "html_url": "https://github.com/x/releases/v1.1.9",
                          "body": "notes"}).encode()
    monkeypatch.setattr(update_check.urllib.request, "urlopen",
                        lambda req, timeout=0: _FakeResp(payload))
    d = update_check.check(force=True)
    assert d["update_available"] is True
    assert d["latest"] == "1.1.9" and d["current"] == "1.1.5"

    # same version → no update; dev build → never nags
    monkeypatch.setenv("MITY_APP_VERSION", "1.1.9")
    assert update_check.check(force=True)["update_available"] is False
    monkeypatch.delenv("MITY_APP_VERSION")
    assert update_check.check(force=True)["update_available"] is False


def test_check_degrades_gracefully_offline(monkeypatch):
    monkeypatch.setenv("MITY_APP_VERSION", "1.1.5")
    monkeypatch.setattr(update_check, "_cache", {"t": 0.0, "data": None})

    def _boom(req, timeout=0):
        raise OSError("no network")
    monkeypatch.setattr(update_check.urllib.request, "urlopen", _boom)
    d = update_check.check(force=True)
    assert d["update_available"] is False
    assert d["latest"] is None
    assert "github.com" in d["url"]        # still a usable link


def test_endpoint_serves_cached_result(client, workspace, monkeypatch):
    from app.services import update_check as uc
    monkeypatch.setattr(uc, "_cache", {"t": 9e12, "data": {
        "current": "1.1.5", "latest": "1.2.0", "update_available": True,
        "url": "https://github.com/janvanwassenhove/mITyStudio/releases",
        "notes": ""}})
    r = client.get("/api/updates/check")
    assert r.status_code == 200
    assert r.json()["update_available"] is True


def test_pipeline_vocal_intent_detection():
    from app.services.song_pipeline import _wants_vocals
    assert _wants_vocals({}, "a sung synthwave song with vocals")
    assert _wants_vocals({}, "een gezongen popnummer met zang")
    assert _wants_vocals({"vocals": True}, "instrumental")
    assert not _wants_vocals({}, "an instrumental jazz trio piece")
