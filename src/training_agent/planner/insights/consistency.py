"""Consistency: are the planned sessions actually happening, and which one is slipping?"""

from __future__ import annotations

from datetime import timedelta

from training_agent.core.models import Insight, PlanContext
from training_agent.planner.base import PlanInsight
from training_agent.planner.params import load_athlete

WEEKS = 4
NAMES = {"run": "run", "bike": "ride", "gym": "strength session"}


class Consistency(PlanInsight):
    name = "consistency"

    def __init__(self, athlete: dict | None = None):
        template = (athlete if athlete is not None else load_athlete()).get("weekly_template") or []
        self.planned = {}
        for slot in template:
            if slot.get("sport") in NAMES:
                self.planned[slot["sport"]] = self.planned.get(slot["sport"], 0) + int(slot.get("count", 1))

    def evaluate(self, ctx: PlanContext) -> Insight | None:
        if not self.planned:
            return None
        first = ctx.day - timedelta(days=7 * WEEKS)
        window = [a for a in ctx.activities if first <= a.start_time.date() < ctx.day]
        if not window or (ctx.day - min(a.start_time.date() for a in ctx.activities)).days < 14:
            return None
        per_week = {s: sum(1 for a in window if a.sport.value == s) / WEEKS for s in self.planned}
        done = sum(min(per_week[s], n) for s, n in self.planned.items())
        total = sum(self.planned.values())
        adherence = done / total
        gaps = sorted(((n - per_week[s]) / n, s) for s, n in self.planned.items())
        worst_gap, worst = gaps[-1]
        evidence = [f"{NAMES[s]}s per week: {per_week[s]:.1f} (plan {n})" for s, n in self.planned.items()]
        meaning = "Fitness comes from steady repetition. Showing up regularly matters more than any single hard session."
        if "gym" in self.planned:
            evidence.append("Strength sessions count only when Garmin recorded them or you logged them under Activities.")
        headline = f"Over the last {WEEKS} weeks you averaged {done:.1f} of {total} planned sessions a week."
        if worst_gap > 0.25 and adherence < 0.85:
            return Insight(id=self.name, area="consistency", status="watch", priority=55 if adherence < 0.6 else 45, evidence=evidence,
                           headline=f"{headline} The {NAMES[worst]} is the one slipping.", meaning=meaning,
                           action=f"Book your next {NAMES[worst]} in your calendar now.")
        return Insight(id=self.name, area="consistency", status="good", priority=22, evidence=evidence,
                       headline=f"{headline} That is a steady rhythm.", meaning=meaning, action="Keep this rhythm going.")
