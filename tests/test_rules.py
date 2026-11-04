"""Planner rules on synthetic scenarios (the seed of the golden-day tests)."""
from datetime import date, datetime, time, timedelta

import pytest

from training_agent.core.models import Activity, DailyMetrics, Intensity, PlanContext, PlannedSession, Sport
from training_agent.planner.baselines import assess
from training_agent.planner.rules.hard_easy_alternation import HardEasyAlternation
from training_agent.planner.rules.readiness_gate import ReadinessGate
from training_agent.planner.rules.weekly_load_limit import WeeklyLoadLimit

START = date(2026, 1, 1)
N = 40
DAY = START + timedelta(days=N - 1)  # the day being planned is the last day of the series


def make_context(overrides=None, activities=None, chosen=None, drop_today=False, day=DAY):
    """40 steady days (the last one is `day`); overrides = {day_index: {field: value}}."""
    overrides = overrides or {}
    metrics = []
    for i in range(N):
        vals = dict(sleep_hours=7.0, sleep_score=80, hrv_last_night_ms=50 + (i % 3), resting_hr=48,
                    body_battery_morning=80)
        vals.update(overrides.get(i, {}))
        metrics.append(DailyMetrics(date=START + timedelta(days=i), **vals))
    if drop_today:
        metrics = metrics[:-1]
    return PlanContext(day=day, assessments=assess(metrics), activities=activities or [], chosen=chosen or [])


def cap(rule, ctx):
    return rule.evaluate(ctx).max_intensity


# ---------------- readiness gate ----------------
gate = ReadinessGate()
LAST = N - 1


def test_normal_day_allows_hard():
    v = gate.evaluate(make_context())
    assert v.max_intensity == Intensity.HARD and "normal" in v.reasons[0]


def test_one_notable_signal_caps_at_moderate():
    assert cap(gate, make_context({LAST: {"body_battery_morning": 75}})) == Intensity.MODERATE


def test_two_notable_signals_cap_at_easy():
    assert cap(gate, make_context({LAST: {"body_battery_morning": 75, "resting_hr": 51}})) == Intensity.EASY


def test_one_unusual_signal_caps_at_easy_and_says_why():
    v = gate.evaluate(make_context({LAST: {"sleep_score": 60}}))
    assert v.max_intensity == Intensity.EASY and "Sleep score unusually low" in v.reasons[0]


def test_illness_pattern_means_rest():
    v = gate.evaluate(make_context({LAST: {"resting_hr": 52, "hrv_last_night_ms": 46}}))
    assert v.max_intensity == Intensity.REST and "illness" in v.reasons[0]


def test_declining_trend_alone_caps_at_moderate():
    ov = {i: {"hrv_last_night_ms": 46} for i in range(N - 7, N - 1)}  # six low nights, today normal
    v = gate.evaluate(make_context(ov))
    assert v.max_intensity == Intensity.MODERATE and "trending worse" in v.reasons[0]


def test_short_night_is_not_a_false_alarm():
    v = gate.evaluate(make_context({LAST: {"sleep_hours": 1.8, "sleep_score": 30, "hrv_last_night_ms": 105}}))
    assert v.max_intensity == Intensity.MODERATE  # careful, but not easy or rest
    assert any("short" in r.lower() for r in v.reasons)


def test_missing_sleep_and_hrv_is_careful():
    assert cap(gate, make_context({LAST: {"sleep_hours": None, "sleep_score": None, "hrv_last_night_ms": None}})) == Intensity.MODERATE


def test_no_data_for_today_is_easy():
    assert cap(gate, make_context(drop_today=True)) == Intensity.EASY


# ---------------- hard/easy alternation ----------------
alt = HardEasyAlternation()


def at(offset_days, sport=Sport.BIKE, load=100.0, hr=140.0, zones=None, i=[0]):
    i[0] += 1
    start = datetime.combine(DAY, time(8)) - timedelta(days=offset_days)
    return Activity(id=f"t:{i[0]}", source="garmin", sport=sport, start_time=start, duration_s=3600,
                    training_load=load, avg_hr=hr, hr_zone_seconds=zones)


def history():
    """Workouts every 3 days with loads cycling 60/100/140, so the athlete's 'hard' starts near 140."""
    return [at(4 + 3 * k, load=(60, 100, 140)[k % 3]) for k in range(19)]


def test_day_after_hard_workout_is_easy():
    v = alt.evaluate(make_context(activities=history() + [at(1, load=300.0)]))
    assert v.max_intensity == Intensity.EASY and "hard session" in v.reasons[0]


def test_day_after_easy_workout_allows_hard():
    assert cap(alt, make_context(activities=history() + [at(1, load=60.0)])) == Intensity.HARD


def test_gym_yesterday_does_not_count_as_hard():
    assert cap(alt, make_context(activities=history() + [at(1, sport=Sport.GYM, load=300.0, hr=95.0)])) == Intensity.HARD


def test_hard_by_heart_rate_zones():
    assert cap(alt, make_context(activities=history() + [at(1, load=60.0, zones=[0, 0, 0, 1800, 600])])) == Intensity.EASY


def planned(offset, intensity):
    return PlannedSession(date=DAY - timedelta(days=offset), sport=Sport.RUN, intensity=intensity,
                          title="x", rationale="x")


def test_chosen_hard_session_yesterday_counts_when_nothing_was_recorded():
    assert cap(alt, make_context(activities=history(), chosen=[planned(1, Intensity.HARD)])) == Intensity.EASY


def test_recorded_easy_workout_overrides_a_planned_hard_one():
    ctx = make_context(activities=history() + [at(1, load=60.0)], chosen=[planned(1, Intensity.HARD)])
    assert cap(alt, ctx) == Intensity.HARD


# ---------------- weekly load limit ----------------
weekly = WeeklyLoadLimit()


def weeks(this_week_load, weeks_back=5):
    """Four workouts of 75 load per week for earlier weeks; this week's four workouts carry `this_week_load` in total."""
    acts = []
    for w in range(weeks_back):
        for k in range(4):
            acts.append(at(1 + 7 * w + 2 * k, load=this_week_load / 4 if w == 0 else 75.0))
    return acts


def test_load_spike_caps_at_easy():
    v = weekly.evaluate(make_context(activities=weeks(600)))
    assert v.max_intensity == Intensity.EASY and "200%" in v.reasons[0]


def lumpy_history(recent_week_total=400.0):
    """Four lighter weeks (200 each) before four heavier ones (700 each); then a 400 week just now."""
    acts = [at(1 + 2 * k, load=recent_week_total / 4) for k in range(4)]
    for w in range(1, 9):
        for k in range(4):
            acts.append(at(1 + 7 * w + 2 * k, load=(200.0 if w <= 4 else 700.0) / 4))
    return acts


def test_eight_week_average_is_calmer_with_lumpy_training():
    ctx = make_context(activities=lumpy_history())
    assert cap(WeeklyLoadLimit({"chronic_weeks": 4}), ctx) == Intensity.EASY  # 400 vs 200: looks like a spike
    v = weekly.evaluate(ctx)  # default 8 weeks: 400 vs 450 is normal
    assert v.max_intensity == Intensity.HARD and "8-week" in v.reasons[0]


def test_steady_load_is_fine():
    assert cap(weekly, make_context(activities=weeks(300))) == Intensity.HARD


def test_not_enough_history_is_not_a_reason_to_restrict():
    recent = [at(1 + k, load=500.0) for k in range(6)]
    v = weekly.evaluate(make_context(activities=recent))
    assert v.max_intensity == Intensity.HARD and "Not enough history" in v.reasons[0]


def test_very_low_recent_load_is_too_noisy_to_judge():
    quiet = [at(10 + 7 * k, load=20.0) for k in range(4)] + [at(40, load=20.0), at(1, load=400.0)]
    assert cap(weekly, make_context(activities=quiet)) == Intensity.HARD


def test_all_rules_can_be_loaded_from_config():
    from training_agent.core.plugin import load_enabled_plugins
    names = {r.name for r in load_enabled_plugins("config/features.yaml", "planner_rules")}
    assert names == {"readiness_gate", "hard_easy_alternation", "weekly_load_limit"}
