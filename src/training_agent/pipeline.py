"""One daily run: collect -> store -> plan -> publish.

The stages talk only through the shared models. Every stage comes from config/features.yaml
via the plugin loader, so this file never names a concrete collector, database, planner or output.
Plugins can be passed in for tests. A source that cannot be reached does not stop the run: the
brief is made from stored data and says so.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from training_agent.core.models import DailyBrief
from training_agent.core.plugin import load_enabled_plugins
from training_agent.planner.context import build_context

log = logging.getLogger("training_agent.pipeline")
ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "features.yaml"
FAR_PAST, FAR_FUTURE = date(2000, 1, 1), date(2100, 1, 1)


def _first(plugins: list, what: str):
    if not plugins:
        raise RuntimeError(f"Enable a {what} plugin in config/features.yaml")
    return plugins[0]


def run_daily(day: date | None = None, days: int = 3, collect: bool = True, config_path: Path | str = CONFIG,
              collectors: list | None = None, repo=None, planner=None, outputs: list | None = None) -> DailyBrief:
    """Refresh the last `days` days, plan `day` (default today) and publish the brief. Returns the brief."""
    day = day or date.today()
    config_path = Path(config_path)
    repo = repo or _first(load_enabled_plugins(config_path, "storage"), "storage")
    planner = planner or _first(load_enabled_plugins(config_path, "planner"), "planner")
    collectors = collectors if collectors is not None else load_enabled_plugins(config_path, "collectors")
    outputs = outputs if outputs is not None else load_enabled_plugins(config_path, "outputs")
    notes: list[str] = []

    if collect:
        start = day - timedelta(days=days - 1)
        for c in collectors:
            try:
                metrics = c.collect_metrics(start, day)
                activities = c.collect_activities(start, day)
                repo.save_metrics(metrics)
                repo.save_activities(activities)
                log.info("%s: %d days of metrics, %d workouts (%s to %s)", c.name, len(metrics), len(activities), start, day)
            except Exception as e:  # keep going with what is stored
                log.warning("%s failed: %s", c.name, e)
                notes.append(f"Could not refresh from {c.name} ({e}); using stored data.")

    metrics_all = repo.get_metrics(FAR_PAST, day)
    if not metrics_all:
        raise RuntimeError("No recovery data stored yet. Run scripts/backfill.py first.")
    latest = metrics_all[-1].date
    if latest < day:
        age = (day - latest).days
        notes.append(f"The newest recovery data is from {latest} ({age} day{'s' if age > 1 else ''} old). "
                     "Sync your watch, then run again.")

    activities = repo.get_activities(FAR_PAST, FAR_FUTURE)
    earlier = [s for s in repo.get_plan(day - timedelta(days=14), day) if s.date < day]
    plan = planner.plan_day(build_context(day, metrics_all, activities, earlier))
    brief = DailyBrief(date=day, plan=plan, metrics=next((m for m in metrics_all if m.date == day), None),
                       latest_data=latest, notes=notes)

    for out in outputs:
        try:
            out.publish(brief)
        except Exception:  # one broken output must not stop the others
            log.exception("output %s failed", out.name)
    return brief
