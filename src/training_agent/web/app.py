"""Dashboard web app (FastAPI). Serves the JSON endpoints and the static frontend.

Storage comes from config/features.yaml via the plugin loader, so this file never names a concrete
database. Run with scripts/serve.py. Reading is open to the network when started with --lan; changing
anything (choosing a session, logging gym) is only accepted from this computer, because there is no login.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from training_agent.core.models import Intensity
from training_agent.core.plugin import load_enabled_plugins
from training_agent.storage.base import Repository
from training_agent.web import data

ROOT = Path(__file__).resolve().parents[3]
STATIC = Path(__file__).resolve().parent / "static"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


class ChooseBody(BaseModel):
    intensity: Intensity


class ManualBody(BaseModel):
    sport: Literal["gym", "run", "bike", "swim", "hike", "walk", "other"] = "gym"
    minutes: int = Field(ge=5, le=720)
    effort: int = Field(ge=1, le=10, description="your own 1-10 rating of how hard it was")
    kind: Literal["upper", "lower", "full", "other"] = "full"  # only used for strength sessions
    distance_km: float | None = Field(default=None, gt=0, le=1000)
    day: date | None = None  # defaults to today; up to 90 days back


def create_app(repo: Repository | None = None, today: date | None = None) -> FastAPI:
    """`today` is for tests; normally the real date is used."""
    if repo is None:
        repos = load_enabled_plugins(ROOT / "config" / "features.yaml", "storage")
        if not repos:
            raise RuntimeError("Enable a storage plugin in config/features.yaml")
        repo = repos[0]

    app = FastAPI(title="Training agent dashboard", docs_url=None, redoc_url=None)
    now = lambda: today or date.today()  # noqa: E731

    def local_only(request: Request) -> None:
        host = request.client.host if request.client else ""
        if host not in LOCAL_HOSTS:
            raise HTTPException(403, "Changes are only accepted from the computer the dashboard runs on.")

    @app.get("/api/overview")
    def overview(days: int = Query(10, ge=3, le=60)) -> dict:
        return data.build_overview(repo, days)

    @app.get("/api/plan")
    def plan() -> dict:
        return data.build_plan(repo, now())

    @app.post("/api/plan/choose")
    def choose(body: ChooseBody, request: Request) -> dict:
        local_only(request)
        return data.choose_option(repo, now(), body.intensity)

    @app.post("/api/plan/clear")
    def clear(request: Request) -> dict:
        local_only(request)
        data.clear_choice(repo, now())
        return {"cleared": True}

    @app.get("/api/activity-log")
    def activity_log(kind: Literal["all", "bike", "run", "hike", "swim", "gym", "other"] = "all",
                     days: int = Query(180, ge=7, le=400)) -> dict:
        out = data.build_activity_browser(repo, now(), kind, days)
        out["history_from"] = out["history_from"].isoformat() if out["history_from"] else None
        return out

    @app.get("/api/activities/{activity_id:path}")
    def activity_detail(activity_id: str) -> dict:
        found = data.build_activity_detail(repo, activity_id)
        if found is None:
            raise HTTPException(404, "Unknown workout.")
        return found

    @app.get("/api/manual")
    def manual_list() -> list[dict]:
        return data.list_manual(repo, now() - timedelta(days=90))

    @app.post("/api/manual")
    def manual_add(body: ManualBody, request: Request) -> dict:
        local_only(request)
        day = body.day or now()
        if not (now() - timedelta(days=90) <= day <= now()):
            raise HTTPException(422, "The day must be today or within the last 90 days.")
        return data.log_manual(repo, day, body.sport, body.minutes, body.effort, body.kind, body.distance_km)

    @app.delete("/api/manual/{activity_id:path}")
    def manual_delete(activity_id: str, request: Request) -> dict:
        local_only(request)
        try:
            data.delete_manual(repo, activity_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"deleted": activity_id}

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
