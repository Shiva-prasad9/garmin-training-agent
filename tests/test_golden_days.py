"""Golden days: fixed scenarios (tests/golden/*.yaml) with the planner's expected outcome.

Each scenario describes a day (recovery metrics, workouts, chosen sessions) and what the planner must say.
They run with the real rule thresholds in config/rules.yaml, so changing a threshold shows up here as a
visible change. Run before every merge. See tests/golden/README.md for the format.
"""
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
import yaml

from training_agent.core.models import (Activity, DailyMetrics, Intensity, PlanContext, PlannedSession, Sport)
from training_agent.planner.baselines import assess
from training_agent.planner.rules_planner import RulesPlanner
from training_agent.planner.week_plans.fixed_template import FixedTemplate

SCENARIOS = sorted(Path(__file__).parent.joinpath("golden").glob("*.yaml"))
START = date(2026, 1, 1)
MONDAY = date(2026, 2, 9)
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
BASE = {"sleep_hours": 7.0, "sleep_score": 80, "hrv": 50, "resting_hr": 48, "body_battery": 80}


def build_context(sc: dict):
    end = MONDAY + timedelta(days=WEEKDAYS[sc.get("weekday", "wed")])
    base = {**BASE, **sc.get("baseline", {})}
    overrides = {d["days_ago"]: d for d in sc.get("metrics", [])}
    metrics = []
    for i in range((end - START).days + 1):
        ago = (end - (START + timedelta(days=i))).days
        o = overrides.get(ago, {})
        pick = lambda key, default: o[key] if key in o else default  # noqa: E731  (None means "missing")
        metrics.append(DailyMetrics(
            date=START + timedelta(days=i),
            sleep_hours=pick("sleep_hours", base["sleep_hours"]), sleep_score=pick("sleep_score", base["sleep_score"]),
            hrv_last_night_ms=pick("hrv", base["hrv"] + i % 3), resting_hr=pick("resting_hr", base["resting_hr"]),
            body_battery_morning=pick("body_battery", base["body_battery"])))

    activities, n = [], 0

    def add(days_ago, sport, minutes, load, hr, zones=None):
        nonlocal n
        n += 1
        activities.append(Activity(
            id=f"g:{n}", source="garmin", sport=Sport(sport), duration_s=minutes * 60, distance_m=minutes * 380.0,
            training_load=load, avg_hr=hr, hr_zone_seconds=zones,
            start_time=datetime.combine(end - timedelta(days=days_ago), time(8))))

    hist = sc.get("history")
    if hist:  # a workout every `every` days for 70 days, loads and sports cycling
        for k in range(1, 70 // hist.get("every", 2) + 1):
            days_ago = k * hist.get("every", 2)
            if days_ago in {a["days_ago"] for a in sc.get("activities", [])}:
                continue
            load = hist["loads"][(k - 1) % len(hist["loads"])]
            sport = hist.get("sports", ["bike", "run"])[(k - 1) % len(hist.get("sports", ["bike", "run"]))]
            add(days_ago, sport, 60 if sport == "run" else 100, load if sport != "gym" else 8, 95.0 if sport == "gym" else 140.0)
    for a in sc.get("activities", []):
        add(a["days_ago"], a["sport"], a["minutes"], a["load"], a.get("hr", 140.0), a.get("zones"))
    chosen = [PlannedSession(date=end - timedelta(days=c["days_ago"]), sport=Sport(c["sport"]),
                             intensity=Intensity(c["intensity"]), title="chosen", rationale="")
              for c in sc.get("chosen", [])]
    return PlanContext(day=end, assessments=assess(metrics), activities=activities, chosen=chosen)


def option(plan, level):
    return next(o for o in plan.options if o.intensity == Intensity(level))


@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_golden_day(path):
    sc = yaml.safe_load(path.read_text())
    planner = RulesPlanner(sources=[FixedTemplate()])  # real rules and thresholds from config
    plan = planner.plan_day(build_context(sc))
    expect = sc["expect"]
    why = f"[{path.stem}] {sc.get('description', '')}\n  cap={plan.cap.value} recommended={plan.recommended.value}\n  {plan.summary}"

    if "cap" in expect:
        assert plan.cap.value == expect["cap"], why
    if "recommended" in expect:
        assert plan.recommended.value == expect["recommended"], why
    for level, label in expect.get("risk", {}).items():
        assert option(plan, level).risk == label, f"{level}: {option(plan, level).risk} != {label}\n{why}"
    everything = [r for v in plan.verdicts for r in v.reasons] + [r for o in plan.options for r in o.reasons]
    for text in expect.get("reasons_contain", []):
        assert any(text in r for r in everything), f"no reason contains {text!r}\n{why}\n  {everything}"
    for level, text in expect.get("tomorrow_contains", {}).items():
        assert text in option(plan, level).tomorrow, f"tomorrow ({level}): {option(plan, level).tomorrow}\n{why}"
    for level, text in expect.get("title_starts", {}).items():
        assert option(plan, level).title.startswith(text), f"{option(plan, level).title}\n{why}"
    if "dropped" in expect:
        assert [s.kind for s in plan.dropped_slots] == expect["dropped"], why
    for kind in expect.get("remaining_has", []):
        assert kind in [s.kind for s in plan.remaining_slots], why
    if "summary_contains" in expect:
        assert expect["summary_contains"] in plan.summary, why
    if "choose" in expect:
        picked = planner.to_session(plan, Intensity(expect["choose"]["intensity"]))
        c = expect["choose"]
        assert picked.overridden == c["overridden"], why
        if "recommended_intensity" in c:
            assert picked.recommended_intensity.value == c["recommended_intensity"], why
        for flag in c.get("flags_contain", []):
            assert flag in picked.rule_flags, f"{flag} not in {picked.rule_flags}\n{why}"
