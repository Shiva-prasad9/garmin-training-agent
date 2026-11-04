"""Pick the week's targets from the enabled plan sources (first one with a plan wins)."""

from __future__ import annotations

from datetime import date, timedelta

from training_agent.core.models import WeekTargets
from training_agent.core.plugin import load_enabled_plugins
from training_agent.planner.base import WeekPlanSource
from training_agent.planner.params import ROOT


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def targets_for_week(week_start: date, sources: list[WeekPlanSource]) -> WeekTargets:
    for source in sources:
        targets = source.targets_for_week(week_start)
        if targets is not None:
            return targets
    raise RuntimeError("No week plan source produced targets; enable one under week_plans in features.yaml")


def load_sources(config_path=ROOT / "config" / "features.yaml") -> list[WeekPlanSource]:
    return load_enabled_plugins(config_path, "week_plans")


def week_progress(targets: WeekTargets, activities: list, day: date, long_ride_minutes: float = 150):
    """Which of the week's slots are still open on `day`, and what was done so far (Monday to yesterday).

    A recorded workout uses up one slot of its sport (a ride of `long_ride_minutes` or more uses the long
    slot first); every day without a workout uses up a rest slot.
    """
    from training_agent.core.models import Sport

    remaining = list(targets.slots)
    done: list[str] = []
    week_start = monday_of(day)
    active_days = set()
    for a in sorted(activities, key=lambda x: x.start_time):
        d = a.start_time.date()
        if not (week_start <= d < day):
            continue
        active_days.add(d)
        minutes = a.duration_s / 60
        done.append(f"{d:%a} {a.sport.value} {minutes:.0f} min")
        same = [s for s in remaining if s.sport == a.sport]
        if not same:
            continue
        pick = same[0]
        if len(same) > 1:
            wanted = "long" if minutes >= long_ride_minutes else "short"
            pick = next((s for s in same if s.kind == wanted), same[0])
        remaining.remove(pick)
    rest_days = sum(1 for k in range((day - week_start).days) if week_start + timedelta(days=k) not in active_days)
    for _ in range(rest_days):
        rest = next((s for s in remaining if s.sport == Sport.REST), None)
        if rest:
            remaining.remove(rest)
    return remaining, done


DROP_ORDER = ["strength", "short", "long"]  # dropped first to last; other kinds (key sessions) are dropped last


def fit_to_days(remaining: list, day: date):
    """Drop sessions the week no longer has room for (a rest slot still owed keeps its day).

    Returns (kept, dropped). Strength goes first, then the short ride, then the long ride.
    """
    from training_agent.core.models import Sport

    days_left = 7 - day.weekday()  # including today
    rest_owed = sum(1 for s in remaining if s.sport == Sport.REST)
    capacity = max(days_left - rest_owed, 0)
    sessions = [s for s in remaining if s.sport != Sport.REST]
    kept, dropped = list(remaining), []
    while len(sessions) > capacity:
        victim = min(sessions, key=lambda s: DROP_ORDER.index(s.kind) if s.kind in DROP_ORDER else len(DROP_ORDER))
        sessions.remove(victim)
        kept.remove(victim)
        dropped.append(victim)
    return kept, dropped
