"""Route and per-sample detail: parsing, storage, the daily fetch and the endpoint."""
from datetime import date, datetime

from fastapi.testclient import TestClient

from training_agent.collectors.base import Collector
from training_agent.collectors.garmin_personal_api import parse_activity_detail
from training_agent.core.models import Activity, ActivityDetail, Sport
from training_agent.pipeline import fetch_missing_details
from training_agent.storage.sqlite import SqliteRepository
from training_agent.web.app import create_app

SUMMARY = {"summaryDTO": {"distance": 30000.0, "duration": 5400.0, "movingDuration": 5100.0, "elapsedDuration": 5700.0,
                          "averageSpeed": 5.5, "averageMovingSpeed": 5.9, "maxSpeed": 12.0, "elevationGain": 410.0,
                          "elevationLoss": 405.0, "maxElevation": 820.0, "minElevation": 600.0, "averageHR": 140.0,
                          "maxHR": 170.0, "minHR": 90.0, "calories": 800.0, "averageTemperature": 18.0}}
DETAILS = {
    "metricDescriptors": [{"metricsIndex": 0, "key": "sumDistance"}, {"metricsIndex": 1, "key": "directSpeed"},
                          {"metricsIndex": 2, "key": "directHeartRate"}, {"metricsIndex": 3, "key": "directElevation"},
                          {"metricsIndex": 4, "key": "sumDuration"}, {"metricsIndex": 5, "key": "directPower"}],
    "activityDetailMetrics": [{"metrics": [0.0, 5.0, 100.0, 600.0, 0.0, 0.0]},
                              {"metrics": [1000.0, 10.0, 130.0, 620.0, 120.0, 0.0]},
                              {"metrics": [2000.0, None, 150.0, 640.0, 240.0, 0.0]}],
    "geoPolylineDTO": {"polyline": [{"lat": 47.123456789, "lon": 11.5, "valid": True}, {"lat": 47.2, "lon": 11.6},
                                    {"lat": None, "lon": None}, {"lat": 47.3, "lon": 11.7, "valid": False}]},
}


def ride(aid="garmin:1", day=date(2026, 11, 3), sport=Sport.BIKE):
    return Activity(id=aid, source="garmin", sport=sport, start_time=datetime(day.year, day.month, day.day, 8), duration_s=5400)


def test_parse_converts_to_display_units_and_keeps_the_route():
    d = parse_activity_detail("garmin:1", SUMMARY, DETAILS)
    assert d.moving_s == 5100 and d.elapsed_s == 5700 and d.elevation_gain_m == 410 and d.min_hr == 90
    assert d.series["distance_km"] == [0.0, 1.0, 2.0]
    assert d.series["speed_kmh"] == [18.0, 36.0, None]  # m/s -> km/h, gaps stay gaps
    assert d.series["time_min"] == [0.0, 2.0, 4.0]
    assert "power_w" not in d.series  # all zeros: no power meter
    assert d.route == [(47.12346, 11.5), (47.2, 11.6)]  # rounded; points without coordinates or marked invalid are dropped


def test_parse_survives_missing_pieces():
    assert parse_activity_detail("garmin:2", None, DETAILS).series
    only_summary = parse_activity_detail("garmin:3", SUMMARY, None)
    assert only_summary.route == [] and only_summary.series == {} and only_summary.avg_hr == 140


def test_storage_roundtrip_and_delete_with_the_workout(tmp_path):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    repo.save_activities([ride()])
    repo.save_activity_detail(parse_activity_detail("garmin:1", SUMMARY, DETAILS))
    assert repo.get_activity_detail("garmin:1").route[0] == (47.12346, 11.5)
    assert repo.get_activity_detail("garmin:nope") is None
    repo.delete_activity("garmin:1")
    assert repo.get_activity_detail("garmin:1") is None


class FakeSource(Collector):
    name = "fake"

    def __init__(self):
        self.calls = []

    def collect_metrics(self, start, end):
        return []

    def collect_activities(self, start, end):
        return []

    def collect_activity_detail(self, activity):
        self.calls.append(activity.id)
        if activity.id == "garmin:bad":
            raise RuntimeError("boom")
        return ActivityDetail(activity_id=activity.id, avg_hr=120)


def test_fetch_downloads_only_missing_gps_workouts_and_survives_failures(tmp_path):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    src = FakeSource()
    acts = [ride("garmin:a"), ride("garmin:b", sport=Sport.SWIM), ride("garmin:c", sport=Sport.GYM),
            ride("garmin:bad"), ride("garmin:d", sport=Sport.RUN)]
    assert fetch_missing_details([src], repo, acts) == 2  # a and d; swim and gym skipped, bad logged and skipped
    assert sorted(src.calls) == ["garmin:a", "garmin:bad", "garmin:d"]
    src.calls.clear()
    assert fetch_missing_details([src], repo, acts) == 0 and src.calls == ["garmin:bad"]  # stored ones are not fetched again


def test_endpoint_returns_display_units_and_handles_missing_detail(tmp_path):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    repo.save_activities([ride("garmin:1"), ride("garmin:2", sport=Sport.SWIM)])
    repo.save_activity_detail(parse_activity_detail("garmin:1", SUMMARY, DETAILS))
    client = TestClient(create_app(repo, today=date(2026, 11, 4)))
    body = client.get("/api/activities/garmin:1").json()
    assert body["detail"]["avg_moving_speed_kmh"] == 21.24 and body["detail"]["route"][0] == [47.12346, 11.5]
    assert client.get("/api/activities/garmin:2").json()["detail"] is None
    assert client.get("/api/activities/garmin:zzz").status_code == 404


def test_activity_browser_filters_by_kind_and_counts_months(tmp_path):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    hike = ride("garmin:h", day=date(2026, 9, 5), sport=Sport.OTHER).model_copy(update={"source_sport": "hiking"})
    strava = ride("strava_export:s", day=date(2026, 10, 1)).model_copy(update={"source": "strava_export"})
    repo.save_activities([ride("garmin:1", day=date(2026, 11, 3)), ride("garmin:2", day=date(2026, 7, 1)), hike,
                          ride("garmin:old", day=date(2025, 1, 1)), strava,
                          ride("garmin:sw", day=date(2026, 11, 2), sport=Sport.SWIM)])
    client = TestClient(create_app(repo, today=date(2026, 11, 4)))
    all_ = client.get("/api/activity-log?days=180").json()
    assert all_["counts"] == {"bike": 2, "run": 0, "hike": 1, "swim": 1, "gym": 0, "other": 0}
    assert [a["id"] for a in all_["activities"]][0] == "garmin:1" and "strava_export:s" not in str(all_["activities"])
    assert all_["history_from"] == "2025-01-01" and all_["totals"]["count"] == 4
    assert [m["period"] for m in all_["months"]][0] == "2026-05-01" and all_["months"][-1]["period"] == "2026-11-01"
    assert all_["months"][-1]["bike"] == 1.5  # 5400 s
    bikes = client.get("/api/activity-log?kind=bike&days=60").json()
    assert [a["id"] for a in bikes["activities"]] == ["garmin:1"]
    assert client.get("/api/activity-log?kind=nonsense").status_code == 422
