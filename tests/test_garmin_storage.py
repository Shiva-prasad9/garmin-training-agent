"""Parsing and storage tests using fake payloads shaped like the real Garmin responses."""
from datetime import date

from training_agent.collectors.garmin_personal_api import parse_activity, parse_metrics
from training_agent.core.models import Sport
from training_agent.storage.sqlite import SqliteRepository

DAY = date(2026, 10, 31)


def _metrics():
    return parse_metrics(
        DAY,
        sleep={"sleepTimeSeconds": 27000, "sleepScores": {"overall": {"value": 81}}},
        hrv={"hrvSummary": {"lastNightAvg": 55, "weeklyAvg": 52, "status": "BALANCED"}},
        battery=[{"bodyBatteryValuesArray": [[1, 78], [2, 70]]}],
        summary={"data": [{"heartRate": {"restingValue": 48}, "stress": {"avgLevel": 25},
                           "bodyBattery": {"minValue": 20, "maxValue": 80}}]},
    )


def test_parse_metrics_full():
    m = _metrics()
    assert m.sleep_hours == 7.5 and m.sleep_score == 81
    assert m.hrv_last_night_ms == 55 and m.hrv_status == "BALANCED"
    assert m.resting_hr == 48 and m.body_battery_morning == 78


def test_body_battery_morning_is_wake_peak_not_first_reading():
    readings = [[1000, 28], [22_000_000, 73], [30_000_000, 67], [60_000_000, 15]]
    kw = dict(hrv=None, summary=None, battery=[{"bodyBatteryValuesArray": readings}])
    with_sleep = parse_metrics(DAY, sleep={"sleepEndTimestampGMT": 22_000_000}, **kw)
    no_sleep = parse_metrics(DAY, sleep=None, **kw)
    assert with_sleep.body_battery_morning == 73
    assert no_sleep.body_battery_morning == 73


def test_parse_metrics_missing_everything_returns_none():
    assert parse_metrics(DAY, None, None, None, None) is None


def test_parse_activity_without_hr():
    a = parse_activity({"activityId": 1, "startTimeGMT": "2026-10-31 07:00:00", "duration": 3600.0, "elevationGain": 540.0,
                        "activityType": {"typeKey": "road_biking"}})
    assert a.sport == Sport.BIKE and a.avg_hr is None and a.hr_zone_seconds is None and a.elevation_gain_m == 540.0


def test_storage_roundtrip_and_upsert(tmp_path):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    act = parse_activity({"activityId": 2, "startTimeGMT": "2026-10-31 07:00:00", "duration": 10.0,
                          "activityType": {"typeKey": "running"}, "hrTimeInZone_1": 5.0})
    repo.save_metrics([_metrics()])
    repo.save_metrics([_metrics()])  # re-run must not duplicate
    repo.save_activities([act])
    assert len(repo.get_metrics(DAY, DAY)) == 1
    got = repo.get_activities(DAY, DAY)[0]
    assert got.sport == Sport.RUN and got.hr_zone_seconds == [5.0, 0.0, 0.0, 0.0, 0.0]
