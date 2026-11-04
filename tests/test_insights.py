"""Insights: plain guidance from the athlete's own data. Each one returns None without enough data."""
from datetime import date, datetime, timedelta

from training_agent.core.models import Activity, DailyAssessment, PlanContext, SignalAssessment, Sport
from training_agent.planner.insights.consistency import Consistency
from training_agent.planner.insights.intensity_mix import IntensityMix
from training_agent.planner.insights.load_balance import LoadBalance
from training_agent.planner.insights.progression import Progression
from training_agent.planner.insights.recovery_trend import RecoveryTrend
from training_agent.planner.insights.rest_days import RestDays
from training_agent.planner.insights.sleep_debt import SleepDebt
from training_agent.planner.rules_planner import RulesPlanner
from training_agent.planner.week_plans.fixed_template import FixedTemplate

DAY = date(2026, 11, 4)
ATHLETE = {"sleep_target_h": 7.5, "max_hr": 190,
           "weekly_template": [{"sport": "run", "count": 1}, {"sport": "bike", "count": 2}, {"sport": "gym", "count": 3}]}


def act(days_ago, sport=Sport.RUN, minutes=60, load=100.0, zones=None, n=[0]):
    n[0] += 1
    d = DAY - timedelta(days=days_ago)
    return Activity(id=f"garmin:{n[0]}", source="garmin", sport=sport, start_time=datetime(d.year, d.month, d.day, 8), duration_s=minutes * 60,
                    avg_hr=140, training_load=load, hr_zone_seconds=zones)


def sig(value, z=0.0, trend=None, baseline=None, mean=None):
    return SignalAssessment(value=value, z=z, trend=trend, baseline=baseline or value, trend_mean=mean or value)


def day_assess(days_ago, **signals):
    return DailyAssessment(date=DAY - timedelta(days=days_ago), signals=signals)


def ctx(assessments=(), activities=()):
    return PlanContext(day=DAY, assessments=list(assessments), activities=list(activities))


def test_sleep_debt_levels_and_missing_data():
    short = [day_assess(i, sleep_hours=sig(6.0)) for i in range(7)]
    i = SleepDebt(athlete=ATHLETE).evaluate(ctx(short))
    assert i.status == "act" and "1.5 h under" in i.headline and "earlier tonight" in i.action
    ok = [day_assess(i, sleep_hours=sig(7.4)) for i in range(7)]
    assert SleepDebt(athlete=ATHLETE).evaluate(ctx(ok)).status == "good"
    assert SleepDebt(athlete=ATHLETE).evaluate(ctx(short[:3])) is None
    partial = [DailyAssessment(date=DAY - timedelta(days=i), flags=["short_sleep"], signals={"sleep_hours": sig(1.0)}) for i in range(7)]
    assert SleepDebt(athlete=ATHLETE).evaluate(ctx(partial)) is None  # partial recordings are not counted


def test_recovery_trend_needs_two_bad_signs_to_act():
    bad = [DailyAssessment(date=DAY, signals={"hrv_last_night_ms": sig(40, z=-2, trend="down", baseline=50, mean=44),
                                              "resting_hr": sig(52, trend="up", baseline=48, mean=50)})]
    assert RecoveryTrend().evaluate(ctx(bad)).status == "act"
    one = [DailyAssessment(date=DAY, signals={"hrv_last_night_ms": sig(50, trend="steady"), "resting_hr": sig(52, trend="up", baseline=48, mean=50)})]
    assert RecoveryTrend().evaluate(ctx(one)).status == "watch"
    fine = [DailyAssessment(date=DAY, signals={"hrv_last_night_ms": sig(55, trend="up"), "resting_hr": sig(47, trend="steady")})]
    assert RecoveryTrend().evaluate(ctx(fine)).status == "good"
    assert RecoveryTrend().evaluate(ctx([])) is None


def test_load_balance_spike_sweet_spot_and_room_to_build():
    base = [act(d, load=60) for d in range(8, 70, 2)]  # steady history
    spike = base + [act(d, load=200) for d in (1, 2, 3, 4)]
    assert LoadBalance().evaluate(ctx(activities=spike)).status == "act"
    assert LoadBalance().evaluate(ctx(activities=base + [act(2, load=60)])).status in ("good", "watch")
    assert LoadBalance().evaluate(ctx(activities=[act(1)])) is None


def test_intensity_mix_flags_too_much_middle_and_praises_balance():
    middle = [act(d, zones=[100, 200, 1500, 900, 100]) for d in (2, 5, 9, 12, 16)]
    i = IntensityMix(athlete=ATHLETE).evaluate(ctx(activities=middle))
    assert i.status == "watch" and "under 142 bpm" in i.action  # 75% of max HR 190
    easy = [act(d, zones=[800, 1500, 300, 100, 0]) for d in (2, 5, 9, 12, 16)]
    assert IntensityMix(athlete=ATHLETE).evaluate(ctx(activities=easy)).status == "good"
    assert IntensityMix(athlete=ATHLETE).evaluate(ctx(activities=middle[:2])) is None


def test_consistency_names_the_slipping_session():
    done = [act(d, sport=Sport.RUN) for d in (3, 10, 17, 24)] + [act(d, sport=Sport.BIKE) for d in (2, 5, 9, 12, 16, 19, 23, 26)]
    i = Consistency(athlete=ATHLETE).evaluate(ctx(activities=done + [act(40)]))
    assert i.status == "watch" and "strength session is the one slipping" in i.headline and "Book your next strength session" in i.action
    assert Consistency(athlete=ATHLETE).evaluate(ctx(activities=[act(1)])) is None


def test_progression_suggests_ten_percent_when_fresh():
    rides = [act(d, sport=Sport.BIKE, minutes=120) for d in (3, 10)] + [act(d, sport=Sport.BIKE, minutes=120) for d in (40, 55)]
    i = Progression().evaluate(ctx(activities=rides))
    assert i.status == "good" and "about 10 minutes longer" in i.action
    tired = [day_assess(0, hrv_last_night_ms=sig(40, z=-2))]
    assert "once recovery looks normal" in Progression().evaluate(ctx(tired, rides)).action


def test_rest_days_counts_the_streak():
    week = [act(d, minutes=30) for d in range(1, 8)]
    i = RestDays().evaluate(ctx(activities=week))
    assert i.status == "act" and "7 days in a row" in i.headline
    assert RestDays().evaluate(ctx(activities=week[:3])) is None


def test_planner_sorts_insights_and_survives_a_broken_one():
    class Broken:
        name = "broken"

        def evaluate(self, c):
            raise RuntimeError("boom")

    short = [day_assess(i, sleep_hours=sig(6.0)) for i in range(7)]
    planner = RulesPlanner(sources=[FixedTemplate()], insights=[Broken(), SleepDebt(athlete=ATHLETE), RestDays()])
    plan = planner.plan_day(ctx(short, [act(d, minutes=30) for d in range(1, 8)]))
    assert [i.id for i in plan.insights] == ["sleep_debt", "rest_days"]  # priority 85, then 78; the broken one is skipped
