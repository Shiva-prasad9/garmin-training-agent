"""Sleep: how the last week compares with the athlete's sleep goal."""

from __future__ import annotations

from datetime import timedelta

from training_agent.core.models import Insight, PlanContext
from training_agent.planner.base import PlanInsight
from training_agent.planner.params import load_athlete, load_section

DEFAULTS = {"window_days": 7, "min_nights": 4, "act_deficit_h": 1.0, "watch_deficit_h": 0.5}


class SleepDebt(PlanInsight):
    name = "sleep_debt"

    def __init__(self, params: dict | None = None, athlete: dict | None = None):
        self.p = {**load_section(self.name, DEFAULTS), **(params or {})}
        self.target = float((athlete if athlete is not None else load_athlete()).get("sleep_target_h", 7.5))

    def evaluate(self, ctx: PlanContext) -> Insight | None:
        first = ctx.day - timedelta(days=self.p["window_days"] - 1)
        nights = [a.signals["sleep_hours"].value for a in ctx.assessments
                  if first <= a.date <= ctx.day and "short_sleep" not in a.flags
                  and a.signals.get("sleep_hours") and a.signals["sleep_hours"].value is not None]
        if len(nights) < self.p["min_nights"]:
            return None
        avg, deficit = sum(nights) / len(nights), self.target - sum(nights) / len(nights)
        evidence = [f"{len(nights)}-night average {avg:.1f} h", f"your goal {self.target:g} h", f"shortest night {min(nights):.1f} h"]
        meaning = "Most recovery happens in sleep. A steady shortfall slows how well you adapt to training."
        if deficit >= self.p["act_deficit_h"] or deficit >= self.p["watch_deficit_h"]:
            minutes = int(max(30, min(90, round(deficit * 60 / 15) * 15)))
            act = deficit >= self.p["act_deficit_h"]
            return Insight(id=self.name, area="sleep", status="act" if act else "watch", priority=85 if act else 58,
                           headline=f"You slept {avg:.1f} h a night on average this week, {deficit:.1f} h under your {self.target:g} h goal.",
                           meaning=meaning, evidence=evidence,
                           action=f"Go to bed about {minutes} minutes earlier tonight, and keep it up for the next week.")
        return Insight(id=self.name, area="sleep", status="good", priority=15,
                       headline=f"Sleep is on target: {avg:.1f} h a night this week.", meaning=meaning, evidence=evidence,
                       action="Keep your bedtime steady.")
