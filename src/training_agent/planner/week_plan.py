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
