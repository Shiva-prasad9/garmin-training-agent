"""Rest: too many days in a row without a break."""

from __future__ import annotations

from datetime import timedelta

from training_agent.core.models import Insight, PlanContext
from training_agent.planner.base import PlanInsight
from training_agent.planner.params import load_section

DEFAULTS = {"watch_days": 5, "act_days": 7, "min_minutes": 20}


class RestDays(PlanInsight):
    name = "rest_days"

    def __init__(self, params: dict | None = None):
        self.p = {**load_section(self.name, DEFAULTS), **(params or {})}

    def evaluate(self, ctx: PlanContext) -> Insight | None:
        trained = {a.start_time.date() for a in ctx.activities if a.duration_s >= self.p["min_minutes"] * 60}
        streak, day = 0, ctx.day - timedelta(days=1)
        while day in trained and streak < 30:
            streak, day = streak + 1, day - timedelta(days=1)
        if streak < self.p["watch_days"]:
            return None
        act = streak >= self.p["act_days"]
        return Insight(id=self.name, area="recovery", status="act" if act else "watch", priority=78 if act else 56,
                       headline=f"You have trained {streak} days in a row without a rest day.",
                       meaning="Adaptation happens during rest. A planned day off helps the training you have done to stick.",
                       action="Take today off, or keep it to a short, very easy session.",
                       evidence=[f"{streak} consecutive days with a workout of 20+ minutes"])
