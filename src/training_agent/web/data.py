"""Data for the dashboard: plain functions that turn stored models into JSON-ready dicts.

Reads only through the storage Repository interface and the shared models.
The frontend does all display work (labels, colours); this module returns facts.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from training_agent.core.models import Activity
from training_agent.planner.baselines import SIGNALS, assess, load_params
from training_agent.storage.base import Repository

WEEKS_OF_LOAD = 6
SPORTS = ["bike", "run", "gym", "other"]
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

    all_acts = repo.get_activities(_FAR_PAST, _FAR_FUTURE)
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
