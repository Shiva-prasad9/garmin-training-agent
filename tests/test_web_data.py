"""Dashboard data and API tests with a temporary database."""
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from training_agent.core.models import Activity, DailyMetrics, Sport
from training_agent.storage.sqlite import SqliteRepository
from training_agent.web.app import create_app
from training_agent.web.data import build_overview

LAST = date(2026, 10, 31)


def _repo(tmp_path, with_data=True):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    if with_data:
        repo.save_metrics([
            DailyMetrics(date=LAST - timedelta(days=i), sleep_hours=7, sleep_score=80, hrv_last_night_ms=50,
                         resting_hr=48, body_battery_morning=80, hrv_status="BALANCED")
            for i in range(40)
        ])
        repo.save_activities([
            Activity(id="garmin:1", source="garmin", sport=Sport.BIKE, start_time=datetime(2026, 10, 30, 8),
                     duration_s=3600, training_load=100.0),
            Activity(id="garmin:2", source="garmin", sport=Sport.RUN, start_time=datetime(2026, 10, 28, 8),
                     duration_s=1800, avg_hr=150.0, training_load=50.0),
        ])
    return repo


def test_overview_window_and_status(tmp_path):
    data = build_overview(_repo(tmp_path), days=10)
    assert len(data["series"]) == 10 and data["latest_date"] == "2026-10-31"
    assert data["status"]["body_battery_morning"]["baseline"] == 80
    assert data["status"]["hrv_status"] == "BALANCED"


def test_activities_and_weekly_load(tmp_path):
    data = build_overview(_repo(tmp_path), days=10)
    assert [a["sport"] for a in data["activities"]] == ["bike", "run"]  # newest first
    assert data["activities"][0]["avg_hr"] is None
    assert len(data["weekly_load"]) == 6
    assert data["weekly_load"][-1]["bike"] == 100.0 and data["weekly_load"][-1]["run"] == 50.0


def test_empty_database(tmp_path):
    assert build_overview(_repo(tmp_path, with_data=False)) == {"empty": True}


def test_api_endpoint_and_days_validation(tmp_path):
    client = TestClient(create_app(_repo(tmp_path)))
    assert client.get("/api/overview?days=7").json()["days"] == 7
    assert client.get("/api/overview?days=1").status_code == 422


def test_frontend_files_are_served(tmp_path):
    client = TestClient(create_app(_repo(tmp_path)))
    assert "Training System" in client.get("/").text
    for path in ("/style.css", "/js/main.js", "/js/panels/index.js", "/js/charts.js"):
        assert client.get(path).status_code == 200, path


def test_dashboard_ignores_strava_only_workouts(tmp_path):
    repo = _repo(tmp_path)
    repo.save_activities([Activity(id="strava:9", source="strava_export", sport=Sport.RUN,
                                   start_time=datetime(2026, 10, 29, 8), duration_s=1800, relative_effort=50.0)])
    data = build_overview(repo, days=10)
    assert [a["id"] for a in data["activities"]] == ["garmin:1", "garmin:2"]
    assert data["weekly_load"][-1]["run"] == 50.0  # Garmin run only


def test_weekly_load_has_a_swim_column(tmp_path):
    data = build_overview(_repo(tmp_path), days=10)
    assert set(data["weekly_load"][0]) == {"week", "bike", "run", "gym", "swim", "other"}
