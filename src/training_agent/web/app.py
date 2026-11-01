"""Dashboard web app (FastAPI). Serves one JSON endpoint and the static frontend.

Storage comes from config/features.yaml via the plugin loader, so this file never
names a concrete database. Run with scripts/serve.py.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

from training_agent.core.plugin import load_enabled_plugins
from training_agent.storage.base import Repository
from training_agent.web.data import build_overview

ROOT = Path(__file__).resolve().parents[3]
STATIC = Path(__file__).resolve().parent / "static"


def create_app(repo: Repository | None = None) -> FastAPI:
    if repo is None:
        repos = load_enabled_plugins(ROOT / "config" / "features.yaml", "storage")
        if not repos:
            raise RuntimeError("Enable a storage plugin in config/features.yaml")
        repo = repos[0]

    app = FastAPI(title="Training agent dashboard", docs_url=None, redoc_url=None)

    @app.get("/api/overview")
    def overview(days: int = Query(10, ge=3, le=60)) -> dict:
        return build_overview(repo, days)

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
