from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_config
from .logging_setup import setup_logging

log = logging.getLogger(__name__)


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

    from .api import (routes_assets, routes_projects, routes_settings,
                      routes_scores, routes_chat, routes_render,
                      routes_vocals, routes_export, routes_voice)
    for r in (routes_assets, routes_projects, routes_settings, routes_scores,
              routes_chat, routes_render, routes_vocals, routes_export,
              routes_voice):
        app.include_router(r.router)

    log.info("mITyStudio API ready (root=%s)", cfg.root)
    return app


app = create_app()
