"""Strava parsing (fake CSV with the export's duplicate columns) and duplicate merging."""
from datetime import datetime, timedelta

from training_agent.collectors.strava_export import parse_rows
from training_agent.core.activities import merge_duplicates
from training_agent.core.models import Activity, Sport
from training_agent.storage.sqlite import SqliteRepository

HEADER = ["Activity ID", "Activity Date", "Activity Type", "Elapsed Time", "Distance", "Max Heart Rate",
          "Relative Effort", "Filename", "Elapsed Time", "Moving Time", "Distance", "Average Heart Rate",
          "Max Heart Rate", "Perceived Exertion", "Average Watts", "Elevation Gain", "Perceived Relative Effort"]


def _row(id_, date, typ, dist_km="10.5", dist_m="10500.0", hr="150", rel="60", pe="", watts="", moving="3000", pre=""):
    return [id_, date, typ, "3100", dist_km, "", rel, f"activities/{id_}.fit.gz", "3100", moving, dist_m, hr,
            "172", pe, watts, "120", pre]


def test_parse_strava_rows():
    rows = [HEADER,
            _row("11", "Nov 3, 2026, 6:15:05 AM", "Ride", hr="", rel="", watts="115", pe="6", pre="140"),
            _row("12", "Oct 30, 2026, 5:00:00 PM", "Weight Training", dist_km="0", dist_m="0.0", pe="5"),
            _row("13", "not a date", "Run")]
    acts, skipped = parse_rows(rows)
    assert skipped == 1 and len(acts) == 2
    ride, gym = acts
    assert ride.id == "strava:11" and ride.sport == Sport.BIKE and ride.distance_m == 10500.0  # metres, not km
    assert ride.avg_hr is None and ride.avg_power_w == 115 and ride.duration_s == 3000  # moving time
    assert ride.start_time == datetime(2026, 11, 3, 6, 15, 5)
    assert ride.relative_effort is None and ride.perceived_relative_effort == 140  # no HR: effort from the 1-10 rating
    assert gym.sport == Sport.GYM and gym.distance_m is None and gym.perceived_exertion == 5
    assert gym.max_hr == 172  # duplicated column: first non-empty copy wins


def _act(id_, source, start, **kw):
    return Activity(id=id_, source=source, sport=Sport.BIKE, start_time=start, duration_s=3600, **kw)


T = datetime(2026, 10, 31, 12, 0)


def test_merge_keeps_garmin_and_carries_strava_effort():
    out = merge_duplicates([
        _act("strava:1", "strava_export", T + timedelta(seconds=40), relative_effort=88.0, perceived_exertion=6.0),
        _act("garmin:1", "garmin", T, training_load=300.0, avg_hr=140.0),
    ])
    assert len(out) == 1 and out[0].id == "garmin:1"
    assert out[0].relative_effort == 88.0 and out[0].training_load == 300.0


def test_merge_prefers_garmin_even_if_strava_starts_earlier():
    out = merge_duplicates([_act("strava:2", "strava_export", T - timedelta(minutes=2)), _act("garmin:2", "garmin", T)])
    assert [a.id for a in out] == ["garmin:2"]


def test_merge_keeps_distinct_workouts_and_same_source_neighbours():
    out = merge_duplicates([
        _act("strava:3", "strava_export", T), _act("strava:4", "strava_export", T + timedelta(seconds=30)),
        _act("garmin:5", "garmin", T + timedelta(hours=5)),
    ])
    assert len(out) == 3


def test_storage_merges_on_read_but_keeps_both_rows(tmp_path):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    repo.save_activities([_act("garmin:1", "garmin", T, training_load=300.0),
                          _act("strava:1", "strava_export", T, relative_effort=88.0)])
    day = T.date()
    assert len(repo.get_activities(day, day)) == 1
    assert len(repo.get_activities(day, day, include_duplicates=True)) == 2
    assert repo.get_activities(day, day)[0].relative_effort == 88.0
