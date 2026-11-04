"""Data for the dashboard: plain functions that turn stored models into JSON-ready dicts.

Reads only through the storage Repository interface and the shared models.
The frontend does all display work (labels, colours); this module returns facts.
"""

from __future__ import annotations

import re
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

    # The dashboard shows Garmin workouts and the athlete's own manual log. Strava history is for the agent only.
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


# ---------- daily plan and manual log ----------

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


# What can be logged by hand: choice -> (sport, label stored with the entry). The label also drives hiking/walking detection.
MANUAL_CHOICES = {"gym": (Sport.GYM, "Gym ({kind})"), "run": (Sport.RUN, "running"), "bike": (Sport.BIKE, "cycling"), "swim": (Sport.SWIM, "swimming"),
                  "hike": (Sport.OTHER, "hiking"), "walk": (Sport.OTHER, "walking"), "other": (Sport.OTHER, "other")}


def log_manual(repo: Repository, day: date, choice: str, minutes: int, effort: int, kind: str = "full",
               distance_km: float | None = None) -> dict:
    """Record a workout by hand (Garmin misses some, e.g. gym). Effort is the athlete's own 1-10 rating."""
    if choice not in MANUAL_CHOICES:
        raise ValueError(f"activity must be one of {list(MANUAL_CHOICES)}")
    if kind not in GYM_KINDS:
        raise ValueError(f"kind must be one of {GYM_KINDS}")
    sport, label = MANUAL_CHOICES[choice]
    taken = sum(1 for a in repo.get_activities(day, day, include_duplicates=True) if a.source == "manual")
    entry = Activity(id=f"manual:{choice}:{day.isoformat()}:{taken + 1}", source="manual", sport=sport,
                     source_sport=label.format(kind=kind), start_time=datetime.combine(day, time(18, 0)),
                     duration_s=minutes * 60.0, distance_m=distance_km * 1000 if distance_km else None,
                     perceived_exertion=float(effort))
    repo.save_activities([entry])
    return _activity_dict(entry)


def list_manual(repo: Repository, since: date) -> list[dict]:
    rows = [a for a in repo.get_activities(since, _FAR_FUTURE, include_duplicates=True) if a.source == "manual"]
    return [_activity_dict(a) for a in sorted(rows, key=lambda a: a.start_time, reverse=True)]


def delete_manual(repo: Repository, activity_id: str) -> None:
    if not activity_id.startswith("manual:"):
        raise ValueError("Only manual log entries can be deleted here")
    repo.delete_activity(activity_id)


# ---------- one workout in detail ----------

def build_activity_detail(repo: Repository, activity_id: str) -> dict | None:
    """The workout plus its downloaded detail in display units, or None if the workout is unknown.

    "detail" is None when the route and samples were not downloaded (swimming, gym, or not fetched yet).
    """
    act = next((a for a in repo.get_activities(_FAR_PAST, _FAR_FUTURE) if a.id == activity_id), None)
    if act is None:
        return None
    d = repo.get_activity_detail(activity_id)
    kmh = lambda v: round(v * 3.6, 2) if v is not None else None  # noqa: E731
    detail = None if d is None else {
        "distance_km": round(d.distance_m / 1000, 2) if d.distance_m else None,
        "duration_s": d.duration_s, "moving_s": d.moving_s, "elapsed_s": d.elapsed_s,
        "avg_speed_kmh": kmh(d.avg_speed_ms), "avg_moving_speed_kmh": kmh(d.avg_moving_speed_ms),
        "max_speed_kmh": kmh(d.max_speed_ms),
        "elevation_gain_m": d.elevation_gain_m, "elevation_loss_m": d.elevation_loss_m,
        "max_elevation_m": d.max_elevation_m, "min_elevation_m": d.min_elevation_m,
        "avg_hr": d.avg_hr, "max_hr": d.max_hr, "min_hr": d.min_hr,
        "calories": d.calories, "avg_temp_c": d.avg_temp_c,
        "series": d.series, "route": [list(p) for p in d.route],
    }
    return {"activity": _activity_dict(act), "detail": detail}


# ---------- activity browser (the Activities section) ----------

KINDS = ["bike", "run", "hike", "swim", "gym", "other"]


def activity_kind(a: Activity) -> str:
    """The sidebar category of a workout. Hiking and walking are 'other' sport with their own entry."""
    if a.sport.value in ("bike", "run", "swim", "gym"):
        return a.sport.value
    return "hike" if re.search(r"hik|walk", a.source_sport or "", re.I) else "other"


def build_activity_browser(repo: Repository, today: date, kind: str = "all", days: int = 180) -> dict:
    """Workouts of one kind (or all) over the last `days` days, with totals and hours per month.

    Like the overview, Strava history is left out: this page shows Garmin workouts and the athlete's own gym log.
    """
    everything = [a for a in repo.get_activities(_FAR_PAST, _FAR_FUTURE) if a.source != "strava_export"]
    start = today - timedelta(days=days - 1)
    window = [a for a in everything if start <= a.start_time.date() <= today]
    counts = {k: sum(1 for a in window if activity_kind(a) == k) for k in KINDS}
    picked = sorted((a for a in window if kind == "all" or activity_kind(a) == kind), key=lambda a: a.start_time, reverse=True)

    months: dict[date, dict[str, float]] = {}
    m, end = date(start.year, start.month, 1), date(today.year, today.month, 1)
    while m <= end:
        months[m] = {k: 0.0 for k in KINDS}
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    for a in picked:
        months[date(a.start_time.year, a.start_time.month, 1)][activity_kind(a)] += a.duration_s / 3600

    climbs = [a.elevation_gain_m for a in picked if a.elevation_gain_m]
    return {
        "kind": kind, "days": days, "counts": counts,
        "history_from": min((a.start_time.date() for a in everything), default=None),
        "totals": {"count": len(picked), "hours": round(sum(a.duration_s for a in picked) / 3600, 1),
                   "distance_km": round(sum(a.distance_m or 0 for a in picked) / 1000, 1),
                   "climbing_m": round(sum(climbs)) if climbs else None},
        "months": [{"period": k.isoformat(), **{s: round(v, 2) for s, v in row.items()}} for k, row in months.items()],
        "activities": [{**_activity_dict(a), "kind": activity_kind(a)} for a in picked],
    }
