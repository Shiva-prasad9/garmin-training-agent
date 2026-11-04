"""Data for the dashboard: plain functions that turn stored models into JSON-ready dicts.

Reads only through the storage Repository interface and the shared models.
The frontend does all display work (labels, colours); this module returns facts.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path

from training_agent.core.models import Activity, Intensity, Sport
from training_agent.core.plugin import load_enabled_plugins
from training_agent.planner.baselines import SIGNALS, assess, load_params
from training_agent.planner.context import build_context
from training_agent.storage.base import Repository

WEEKS_OF_LOAD = 6
CONFIG = Path(__file__).resolve().parents[3] / "config" / "features.yaml"
GYM_KINDS = ("upper", "lower", "full", "other")
SPORTS = ["bike", "run", "gym", "swim", "other"]
_FAR_PAST, _FAR_FUTURE = date(2000, 1, 1), date(2100, 1, 1)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _activity_dict(a: Activity) -> dict:
    return {
        "id": a.id,
        "sport": a.sport.value,
        "source_sport": a.source_sport,
        "start": a.start_time.isoformat(),
        "duration_min": round(a.duration_s / 60, 1),
        "distance_km": round(a.distance_m / 1000, 2) if a.distance_m else None,
        "avg_hr": a.avg_hr,
        "training_load": a.training_load,
        "zones_s": a.hr_zone_seconds,
    }


def weekly_load(activities: list[Activity], last_day: date, weeks: int = WEEKS_OF_LOAD) -> list[dict]:
    """Summed training load per sport for each of the last `weeks` weeks (Monday start)."""
    first = _monday(last_day) - timedelta(weeks=weeks - 1)
    rows = {first + timedelta(weeks=i): {s: 0.0 for s in SPORTS} for i in range(weeks)}
    for a in activities:
        week = _monday(a.start_time.date())
        if week in rows:
            sport = a.sport.value if a.sport.value in SPORTS else "other"
            rows[week][sport] += a.training_load or 0.0
    return [{"week": w.isoformat(), **{s: round(v, 1) for s, v in vals.items()}} for w, vals in rows.items()]


def build_overview(repo: Repository, days: int = 10) -> dict:
    """Everything the dashboard needs for a window of `days` days ending at the latest stored day."""
    metrics = repo.get_metrics(_FAR_PAST, _FAR_FUTURE)
    if not metrics:
        return {"empty": True}
    by_date = {m.date: m for m in metrics}
    assessments = assess(metrics, load_params())
    latest = assessments[-1]
    start = latest.date - timedelta(days=days - 1)

    series = []
    for a in assessments:
        if a.date < start:
            continue
        row = {"date": a.date.isoformat(), "flags": a.flags, "hrv_status": by_date[a.date].hrv_status}
        row.update({sig: a.signals[sig].model_dump() for sig in SIGNALS})
        series.append(row)

    # The dashboard shows Garmin workouts and the athlete's own gym log. Strava history is for the agent only.
    all_acts = [a for a in repo.get_activities(_FAR_PAST, _FAR_FUTURE) if a.source != "strava_export"]
    window_acts = [a for a in all_acts if a.start_time.date() >= start]
    window_acts.sort(key=lambda a: a.start_time, reverse=True)

    return {
        "empty": False,
        "days": days,
        "latest_date": latest.date.isoformat(),
        "days_behind": (date.today() - latest.date).days,
        "status": series[-1],
        "series": series,
        "activities": [_activity_dict(a) for a in window_acts],
        "weekly_load": weekly_load(all_acts, latest.date),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


# ---------- daily plan and gym log ----------

@lru_cache(maxsize=1)
def _planner():
    planners = load_enabled_plugins(CONFIG, "planner")
    if not planners:
        raise RuntimeError("Enable a planner under `planner` in config/features.yaml")
    return planners[0]


def _plan_for(repo: Repository, day: date):
    metrics = [m for m in repo.get_metrics(_FAR_PAST, _FAR_FUTURE) if m.date <= day]
    activities = repo.get_activities(_FAR_PAST, _FAR_FUTURE)
    earlier = [s for s in repo.get_plan(day - timedelta(days=14), day) if s.date < day]  # today's own choice is excluded
    ctx = build_context(day, metrics, activities, earlier)
    return _planner().plan_day(ctx)


def build_plan(repo: Repository, day: date) -> dict:
    """The recommendation and every option for `day`, plus what the athlete already chose for it."""
    plan = _plan_for(repo, day)
    chosen = repo.get_plan(day, day)
    return {"plan": plan.model_dump(mode="json"), "chosen": [s.model_dump(mode="json") for s in chosen]}


def choose_option(repo: Repository, day: date, intensity: Intensity) -> dict:
    """Save the chosen option for `day` (replacing an earlier choice). Choosing above the cap is allowed and recorded."""
    plan = _plan_for(repo, day)
    session = _planner().to_session(plan, intensity)
    repo.delete_plan(day)
    repo.save_plan([session])
    return session.model_dump(mode="json")


def clear_choice(repo: Repository, day: date) -> None:
    repo.delete_plan(day)


def log_gym(repo: Repository, day: date, minutes: int, effort: int, kind: str) -> dict:
    """Record a gym session by hand (Garmin often misses them). Effort is the athlete's 1-10 rating."""
    if kind not in GYM_KINDS:
        raise ValueError(f"kind must be one of {GYM_KINDS}")
    taken = sum(1 for a in repo.get_activities(day, day, include_duplicates=True) if a.source == "manual")
    entry = Activity(id=f"manual:gym:{day.isoformat()}:{taken + 1}", source="manual", sport=Sport.GYM,
                     source_sport=f"Gym ({kind})", start_time=datetime.combine(day, time(18, 0)),
                     duration_s=minutes * 60.0, perceived_exertion=float(effort))
    repo.save_activities([entry])
    return _activity_dict(entry)


def list_manual(repo: Repository, since: date) -> list[dict]:
    rows = [a for a in repo.get_activities(since, _FAR_FUTURE, include_duplicates=True) if a.source == "manual"]
    return [_activity_dict(a) for a in sorted(rows, key=lambda a: a.start_time, reverse=True)]


def delete_manual(repo: Repository, activity_id: str) -> None:
    if not activity_id.startswith("manual:"):
        raise ValueError("Only manual log entries can be deleted here")
    repo.delete_activity(activity_id)
