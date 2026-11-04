"""Build the PlanContext the planner and its rules work from (pure; the caller fetches the data)."""

from __future__ import annotations

from datetime import date

from training_agent.core.models import Activity, DailyMetrics, PlanContext, PlannedSession
from training_agent.planner.baselines import assess, load_params


def build_context(day: date, metrics: list[DailyMetrics], activities: list[Activity],
                  chosen: list[PlannedSession] | None = None) -> PlanContext:
    assessments = [a for a in assess(metrics, load_params()) if a.date <= day]
    return PlanContext(day=day, assessments=assessments, activities=activities, chosen=chosen or [])
