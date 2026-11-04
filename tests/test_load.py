"""Effort estimates (decision D016) and hard-day detection."""
from datetime import datetime, timedelta

from training_agent.core.models import Activity, Sport
from training_agent.planner.load import estimate_effort, hard_threshold, is_hard, load_rates

T = datetime(2026, 10, 1, 8, 0)


def act(sport=Sport.BIKE, minutes=60, **kw):
    return Activity(id=f"x:{kw.pop('i', 1)}", source="garmin", sport=sport, start_time=T, duration_s=minutes * 60, **kw)


def test_garmin_load_wins_when_heart_rate_exists():
    e = estimate_effort(act(avg_hr=140.0, training_load=200.0, relative_effort=50.0), {})
    assert (e.value, e.source) == (200.0, "garmin_load")


def test_tiny_garmin_load_without_hr_is_ignored_and_strava_effort_used():
    e = estimate_effort(act(avg_hr=None, training_load=0.1, relative_effort=100.0), {})
    assert e.source == "strava_effort" and round(e.value) == 142


def test_perceived_effort_used_when_no_heart_rate_effort():
    e = estimate_effort(act(avg_hr=None, training_load=0.1, perceived_relative_effort=100.0), {})
    assert e.source == "perceived_effort" and e.is_estimate and round(e.value) == 142


def test_duration_estimate_is_last_resort():
    rates = load_rates([act(i=i, avg_hr=140.0, training_load=120.0) for i in range(3)])  # 2.0 per minute
    e = estimate_effort(act(avg_hr=None, minutes=100), rates)
    assert e.source == "duration_estimate" and round(e.value) == 200
    assert estimate_effort(act(sport=Sport.GYM, avg_hr=None, minutes=60), rates).source == "none"


def test_default_rate_until_enough_history():
    assert round(estimate_effort(act(avg_hr=None, minutes=60), {}).value) == 78  # 1.3 per minute


def test_hard_threshold_and_is_hard():
    loads = [60, 80, 100, 100, 120, 120, 140, 160]
    history = [act(i=i, avg_hr=140.0, training_load=float(v)) for i, v in enumerate(loads)]
    rates = load_rates(history)
    thr = hard_threshold(history, rates)
    assert thr == 140  # top quarter starts here
    assert is_hard(act(avg_hr=140.0, training_load=300.0), thr, rates)
    assert not is_hard(act(avg_hr=140.0, training_load=60.0), thr, rates)
    assert not is_hard(act(sport=Sport.GYM, avg_hr=95.0, training_load=300.0), thr, rates)  # gym never hard


def test_hard_by_zone_time_even_with_modest_load():
    zones = [0, 0, 0, 1200, 1200]  # 40 of 60 minutes in zones 4-5
    assert is_hard(act(avg_hr=150.0, training_load=50.0, hr_zone_seconds=zones), None, {})


def test_no_threshold_without_enough_history():
    assert hard_threshold([act(avg_hr=140.0, training_load=100.0)], {}) is None
