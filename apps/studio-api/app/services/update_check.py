"""Release update check against the public GitHub repo.

The desktop app updates itself through electron-updater (ask-first flow in
apps/desktop/electron/updater.js); this endpoint serves everyone else — the
browser/dev UI shows a "new release available" banner linking to the
release page, and the About box can show what the latest version is.

One GitHub API call per hour at most (cached in-process); failures degrade
to "no update info" — never an error surfaced to the user.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request

log = logging.getLogger(__name__)

REPO = "janvanwassenhove/mITyStudio"
_TTL_S = 3600.0
_cache: dict = {"t": 0.0, "data": None}


def _current_version() -> str:
    # the desktop shell passes its real version; dev/web has none
    return os.environ.get("MITY_APP_VERSION", "").strip()


def _ver_tuple(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3])


def check(force: bool = False) -> dict:
    now = time.time()
    if not force and _cache["data"] is not None \
            and now - _cache["t"] < _TTL_S:
        return _cache["data"]

    current = _current_version()
    data: dict = {
        "current": current or "dev",
        "latest": None,
        "update_available": False,
        "url": f"https://github.com/{REPO}/releases/latest",
        "notes": "",
    }
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/releases/latest",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "mITyStudio-update-check"})
        with urllib.request.urlopen(req, timeout=6) as r:
            rel = json.load(r)
        latest = str(rel.get("tag_name") or "").lstrip("v")
        data["latest"] = latest or None
        data["url"] = rel.get("html_url") or data["url"]
        data["notes"] = (rel.get("body") or "")[:2000]
        cur_t, lat_t = _ver_tuple(current), _ver_tuple(latest)
        # a dev build ("" → empty tuple) never nags about updates
        data["update_available"] = bool(cur_t and lat_t and lat_t > cur_t)
    except Exception as e:  # noqa: BLE001 — offline is a normal condition
        log.debug("update check failed: %s", e)

    _cache.update(t=now, data=data)
    return data
