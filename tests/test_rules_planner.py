"""The rules planner: recommendation, options, override record, tomorrow preview, week accounting."""
from datetime import date, datetime, time, timedelta

from training_agent.core.models import (Activity, DailyMetrics, Intensity, PlanContext, SessionSlot, Sport,
                                        WeekTargets)
from training_agent.planner.base import WeekPlanSource
from training_agent.planner.baselines import assess
from training_agent.planner.rules.hard_easy_alternation import HardEasyAlternation
from training_agent.planner.rules.readiness_gate import ReadinessGate
from training_agent.planner.rules.weekly_load_limit import WeeklyLoadLimit
from training_agent.planner.rules_planner import RulesPlanner
from training_agent.planner.week_plan import week_progress
from training_agent.planner.week_plans.fixed_template import FixedTemplate

START = date(2026, 1, 1)  # a Thursday
WEDNESDAY, SUNDAY = 42, 46  # series lengths that end on a Wednesday / Sunday


def make_context(n=WEDNESDAY, overrides=None, activities=None):
    overrides = overrides or {}
    metrics = []
    for i in range(n):
        vals = dict(sleep_hours=7.0, sleep_score=80, hrv_last_night_ms=50 + (i % 3), resting_hr=48, body_battery_morning=80)
        vals.update(overrides.get(i, {}))
        metrics.append(DailyMetrics(date=START + timedelta(days=i), **vals))
    day = metrics[-1].date
    return PlanContext(day=day, assessments=assess(metrics), activities=activities or [])


def planner(sources=None):
    # The weekly load limit has its own tests; here it is relaxed so the synthetic busy weeks do not trigger it.
    rules = [ReadinessGate(), HardEasyAlternation(), WeeklyLoadLimit({"max_ratio": 5.0})]
    return RulesPlanner(rules=rules, sources=sources or [FixedTemplate()])


def workout(day, offset, sport=Sport.BIKE, minutes=60, load=100.0, hr=140.0, zones=None, i=[0]):
    i[0] += 1
    return Activity(id=f"w:{i[0]}", source="garmin", sport=sport,
                    start_time=datetime.combine(day, time(8)) - timedelta(days=offset), duration_s=minutes * 60,
                    distance_m=minutes * 400.0, training_load=load, avg_hr=hr, hr_zone_seconds=zones)


def history(day, with_recent_hard=True):
    """Workouts every 3 days with loads cycling 60/100/140; optionally one big recent one (3 days ago)."""
    acts = [workout(day, 4 + 3 * k, load=(60, 100, 140)[k % 3]) for k in range(19)]
    if with_recent_hard:
        acts.append(workout(day, 3, load=320.0))
    return acts


LAST = WEDNESDAY - 1
DAY = START + timedelta(days=LAST)


def option(plan, level):
    return next(o for o in plan.options if o.intensity == level)


def test_normal_day_recommends_moderate_and_offers_all_four_options():
    plan = planner().plan_day(make_context(activities=history(DAY)))
    assert plan.cap == Intensity.HARD and plan.recommended == Intensity.MODERATE
    assert [o.intensity for o in plan.options] == [Intensity.REST, Intensity.EASY, Intensity.MODERATE, Intensity.HARD]
    assert option(plan, Intensity.MODERATE).risk == "recommended" and option(plan, Intensity.HARD).risk == "ok"


def test_key_session_is_recommended_when_no_hard_session_recently():
    plan = planner().plan_day(make_context(activities=history(DAY, with_recent_hard=False)))
    assert plan.recommended == Intensity.HARD and option(plan, Intensity.HARD).title.startswith("Hard")


def test_capped_easy_but_sessions_owed_gives_an_easy_session():
    plan = planner().plan_day(make_context(overrides={LAST: {"sleep_score": 60}}, activities=history(DAY)))
    assert plan.cap == Intensity.EASY and plan.recommended == Intensity.EASY


def test_tired_with_a_free_day_left_recommends_rest():
    done = [workout(DAY, 2, sport=Sport.GYM, hr=95.0, load=8.0), workout(DAY, 1, sport=Sport.GYM, hr=95.0, load=8.0)]
    plan = planner().plan_day(make_context(overrides={LAST: {"sleep_score": 60}}, activities=history(DAY) + done))
    assert plan.recommended == Intensity.REST


def test_risk_labels_and_reasons_when_capped():
    plan = planner().plan_day(make_context(overrides={LAST: {"sleep_score": 60}}, activities=history(DAY)))
    risks = {o.intensity: o.risk for o in plan.options}
    assert risks == {Intensity.REST: "ok", Intensity.EASY: "recommended", Intensity.MODERATE: "caution",
                     Intensity.HARD: "not_advised"}
    assert any("Sleep score unusually low" in r for r in option(plan, Intensity.HARD).reasons)


def test_choosing_above_the_cap_is_recorded_as_an_override():
    p = planner()
    plan = p.plan_day(make_context(overrides={LAST: {"sleep_score": 60}}, activities=history(DAY)))
    hard = p.to_session(plan, Intensity.HARD)
    assert hard.overridden and hard.recommended_intensity == Intensity.EASY
    assert "readiness_gate" in hard.rule_flags and hard.warnings
    easy = p.to_session(plan, Intensity.EASY)
    assert not easy.overridden and easy.warnings == []


def test_tomorrow_preview_reflects_the_choice():
    plan = planner().plan_day(make_context(activities=history(DAY)))
    assert "capped at easy" in option(plan, Intensity.HARD).tomorrow
    assert "open to a hard session" in option(plan, Intensity.EASY).tomorrow


def test_session_is_shortened_the_day_after_a_hard_one():
    after_hard = planner().plan_day(make_context(activities=history(DAY) + [workout(DAY, 1, load=320.0)]))
    after_easy = planner().plan_day(make_context(activities=history(DAY) + [workout(DAY, 1, load=60.0)]))
    assert after_hard.cap == Intensity.EASY
    easy_hard_day, easy_easy_day = option(after_hard, Intensity.EASY), option(after_easy, Intensity.EASY)
    assert easy_hard_day.prescription.duration_min < easy_easy_day.prescription.duration_min
    assert any("Shortened" in r for r in easy_hard_day.reasons)


def test_complete_week_recommends_rest_and_marks_extra_sessions():
    sunday = START + timedelta(days=SUNDAY - 1)
    week = [workout(sunday, 6, sport=Sport.GYM, hr=95.0, load=8.0), workout(sunday, 5, sport=Sport.RUN, minutes=60),
            workout(sunday, 4, sport=Sport.GYM, hr=95.0, load=8.0), workout(sunday, 3, sport=Sport.BIKE, minutes=200),
            workout(sunday, 2, sport=Sport.GYM, hr=95.0, load=8.0), workout(sunday, 1, sport=Sport.BIKE, minutes=60)]
    plan = planner().plan_day(make_context(n=SUNDAY, activities=history(sunday) + week))
    assert plan.recommended == Intensity.REST and plan.remaining_slots[0].sport == Sport.REST
    assert any("Extra session" in r for r in option(plan, Intensity.EASY).reasons)


def test_week_progress_uses_up_matching_slots():
    template = FixedTemplate().targets_for_week(date(2026, 2, 9))
    acts = [workout(DAY, 2, sport=Sport.BIKE, minutes=200), workout(DAY, 1, sport=Sport.RUN, minutes=60)]
    remaining, done = week_progress(template, acts, DAY)
    assert sorted((s.sport.value, s.kind) for s in remaining) == [
        ("bike", "short"), ("gym", "strength"), ("gym", "strength"), ("gym", "strength"), ("rest", "rest")]
    assert len(done) == 2


class EventLikePlan(WeekPlanSource):
    name = "event_like"

    def targets_for_week(self, week_start):
        return WeekTargets(week_start=week_start, source=self.name, phase="build",
                           slots=[SessionSlot(sport=Sport.RUN, kind="long"), SessionSlot(sport=Sport.RUN, kind="intervals")])


def test_a_different_plan_source_changes_what_is_offered_without_touching_the_planner():
    plan = planner(sources=[EventLikePlan(), FixedTemplate()]).plan_day(make_context(activities=history(DAY)))
    assert plan.week_source == "event_like" and plan.week_phase == "build"
    assert all("run" in o.title.lower() for o in plan.options if o.sport is not None)


def test_a_week_that_is_behind_drops_gym_sessions_first():
    plan = planner().plan_day(make_context(activities=history(DAY)))  # Wednesday, nothing done: 6 sessions, 5 days
    assert [s.kind for s in plan.dropped_slots] == ["strength"]
    assert sum(1 for s in plan.remaining_slots if s.kind == "strength") == 2
    assert {"10k", "short", "long"} <= {s.kind for s in plan.remaining_slots}  # key sessions are kept
    assert "behind" in plan.summary


def test_a_week_with_room_drops_nothing():
    monday = START + timedelta(days=SUNDAY - 7)
    plan = planner().plan_day(make_context(n=SUNDAY - 6, activities=history(monday)))
    assert plan.dropped_slots == []


def test_rest_day_is_protected_when_dropping():
    from training_agent.planner.week_plan import fit_to_days
    template = FixedTemplate().targets_for_week(date(2026, 2, 9))
    kept, dropped = fit_to_days(template.slots, date(2026, 2, 13))  # Friday: 3 days left, rest still owed
    assert sum(1 for s in kept if s.sport == Sport.REST) == 1
    assert len(kept) - 1 == 2 and len(dropped) == 4  # two sessions fit next to the rest day; gym, short ride, then gym go
    assert [s.kind for s in dropped][:3] == ["strength", "strength", "strength"]
