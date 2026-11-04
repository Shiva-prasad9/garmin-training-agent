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


def test_swimming_is_its_own_sport_for_both_sources():
    from training_agent.collectors.strava_export import parse_rows
    g = parse_activity({"activityId": 7, "startTimeGMT": "2026-11-03 17:00:00", "duration": 1200.0,
                        "activityType": {"typeKey": "lap_swimming"}})
    assert g.sport == Sport.SWIM
    header = ["Activity ID", "Activity Date", "Activity Type", "Moving Time", "Distance"]
    acts, _ = parse_rows([header, ["9", "Nov 3, 2026, 5:00:00 PM", "Swim", "1200", "600"]])
    assert acts[0].sport == Sport.SWIM


def test_old_rows_filed_as_other_are_relabelled_as_swim(tmp_path):
    import sqlite3
    path = tmp_path / "t.sqlite"
    repo = SqliteRepository(path)
    old = parse_activity({"activityId": 8, "startTimeGMT": "2026-11-03 17:00:00", "duration": 1200.0,
                          "activityType": {"typeKey": "lap_swimming"}})
    repo.save_activities([old])
    with sqlite3.connect(path) as con:
        con.execute("UPDATE activities SET sport = 'other'")  # how it was stored before swimming existed
    reopened = SqliteRepository(path)
    assert reopened.get_activities(DAY, date(2026, 11, 3))[0].sport == Sport.SWIM
