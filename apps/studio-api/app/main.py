from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_config
from .logging_setup import setup_logging

log = logging.getLogger(__name__)

# Bump when cutting a notable backend change you want to confirm is deployed.
# The About box surfaces this alongside the desktop app version + live engine
# versions, so "did my reinstall/update actually take?" is answerable at a
# glance (stale build → these numbers don't move).
BACKEND_BUILD = "2026.07.12"


def create_app() -> FastAPI:
    setup_logging()
    cfg = get_config()
    cfg.ensure_dirs()

    app = FastAPI(title="mITyStudio API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        from .services.capabilities import detect_capabilities
        return {"status": "ok", "root": str(cfg.root), "capabilities": detect_capabilities()}

    @app.get("/api/version")
    def version() -> dict:
        """Everything needed to double-check WHAT is actually running — the
        installed app version and which engines/voicebanks are live. If a
        reinstall didn't take, the numbers here won't move."""
        import os
        import sys

        from .services.capabilities import detect_capabilities
        from .services.vocal_engine import VOCAL_ENGINE_VERSION
        from .services import svs_engine
        try:
            from .services.render.soundfont_renderer import ENGINE_VERSION
        except Exception:  # noqa: BLE001
            ENGINE_VERSION = "?"
        svs = svs_engine.svs_status()
        return {
            "app_version": os.environ.get("MITY_APP_VERSION") or "dev",
            "backend_build": BACKEND_BUILD,
            "python": sys.version.split()[0],
            "engines": {"instrument": str(ENGINE_VERSION),
                        "vocal": VOCAL_ENGINE_VERSION},
            "capabilities": detect_capabilities(),
            "singing_engine": {
                "svs_runtime": svs["runtime_available"],
                "vocoder_installed": svs["vocoder_installed"],
                "voicebanks": [b["name"] for b in svs["banks"]],
                "voicebank_problems": svs["problems"],
            },
        }

    @app.get("/api/updates/check")
    def updates_check() -> dict:
        """Is a newer release published on GitHub? Cached (1h). The desktop
        shell updates itself via electron-updater; this feeds the in-app
        banner for browser/dev use and the About box."""
        from .services.update_check import check
        return check()

    @app.get("/api/learning")
    def learning() -> dict:
        """What the studio has learned from this user — inspectable so the
        learning is transparent, never a black box: mix taste, favourite
        genres, how many saves it learned from, and the recurring issues the
        improvement loop feeds back to the producer."""
        from .services import preferences
        return {**preferences.summary(),
                "recurring_issues": preferences.recurring_issues()}

    from .api import (routes_assets, routes_projects, routes_settings,
                      routes_scores, routes_chat, routes_render,
                      routes_vocals, routes_export, routes_voice)
    for r in (routes_assets, routes_projects, routes_settings, routes_scores,
              routes_chat, routes_render, routes_vocals, routes_export,
              routes_voice):
        app.include_router(r.router)

    # desktop mode: serve the built frontend from the same origin
    import os
    ui_dist = os.environ.get("MITY_UI_DIST")
    if ui_dist and os.path.isdir(ui_dist):
        from fastapi.staticfiles import StaticFiles
        from starlette.responses import FileResponse as _FR

        app.mount("/assets", StaticFiles(directory=os.path.join(ui_dist, "assets")),
                  name="ui-assets")
        instruments = os.path.join(ui_dist, "instruments")
        if os.path.isdir(instruments):
            app.mount("/instruments", StaticFiles(directory=instruments),
                      name="ui-instruments")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):  # SPA fallback: every non-API route gets index.html
            candidate = os.path.join(ui_dist, path)
            if path and os.path.isfile(candidate):
                return _FR(candidate)
            return _FR(os.path.join(ui_dist, "index.html"))

        log.info("serving UI from %s", ui_dist)

    log.info("mITyStudio API ready (root=%s)", cfg.root)
    return app


app = create_app()
