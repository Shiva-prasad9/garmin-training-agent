"""Baseline and data-quality tests on synthetic series."""
from datetime import date, timedelta

from training_agent.core.models import DailyMetrics
from training_agent.planner.baselines import BaselineParams, assess, load_params

START = date(2026, 1, 1)


def _series(n=40, overrides=None):
    """n days of steady metrics; overrides = {day_index: {field: value}}."""
    overrides = overrides or {}
    out = []
    for i in range(n):
        vals = dict(sleep_hours=7.0, sleep_score=80, hrv_last_night_ms=50 + (i % 3), resting_hr=48,
                    body_battery_morning=80)
        vals.update(overrides.get(i, {}))
        out.append(DailyMetrics(date=START + timedelta(days=i), **vals))
    return out


def test_no_baseline_early_then_baseline():
    a = assess(_series())
    assert a[3].signals["resting_hr"].baseline is None
    assert "insufficient_baseline" in a[3].flags
    assert a[30].signals["resting_hr"].baseline == 48


def test_short_sleep_flagged_and_excluded_from_baseline():
    a = assess(_series(overrides={20: {"sleep_hours": 0.6, "hrv_last_night_ms": 106}}))
    assert "short_sleep" in a[20].flags
    assert a[20].signals["hrv_last_night_ms"].z is None  # unreliable day gets no score
    assert a[30].signals["hrv_last_night_ms"].baseline < 60  # the 106 did not pollute it


def test_hrv_outlier_flagged():
    a = assess(_series(overrides={30: {"hrv_last_night_ms": 120}}))
    assert "hrv_outlier" in a[30].flags


def test_missing_values_flagged():
    a = assess(_series(overrides={25: {"sleep_hours": None, "hrv_last_night_ms": None}}))
    assert "missing_sleep" in a[25].flags and "missing_hrv" in a[25].flags


def test_today_is_not_in_its_own_baseline():
    a = assess(_series(overrides={35: {"resting_hr": 70}}))
    assert a[35].signals["resting_hr"].baseline == 48 and a[35].signals["resting_hr"].z > 3


def test_load_params_defaults_when_file_missing(tmp_path):
    assert load_params(tmp_path / "nope.yaml") == BaselineParams()
    assert load_params().window_days == 28


def _hrv_last_days(value, days=7, short_nights=0):
    """Steady 40 days, but HRV is `value` for the last `days` days; the first `short_nights` of those are short nights."""
    ov = {i: {"hrv_last_night_ms": value} for i in range(40 - days, 40)}
    for i in range(40 - days, 40 - days + short_nights):
        ov[i]["sleep_hours"] = 2.0
    return assess(_series(overrides=ov))[-1].signals["hrv_last_night_ms"]


def test_trend_down_when_recent_week_is_lower():
    s = _hrv_last_days(40)
    assert s.trend == "down" and s.trend_z < -1.5 and s.trend_n == 7


def test_trend_steady_when_week_matches_baseline():
    s = assess(_series())[-1].signals["hrv_last_night_ms"]
    assert s.trend == "steady" and abs(s.trend_z) < 1.5


def test_trend_up():
    assert _hrv_last_days(65).trend == "up"


def test_trend_needs_enough_valid_days():
    s = _hrv_last_days(40, short_nights=4)  # 4 of 7 nights unreliable -> only 3 valid
    assert s.trend is None and s.trend_n == 3


def test_no_trend_without_baseline():
    assert assess(_series())[3].signals["hrv_last_night_ms"].trend is None
