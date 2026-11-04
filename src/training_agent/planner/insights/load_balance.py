"""Training load: is this week in the sweet spot compared with your usual week?"""

from __future__ import annotations

from training_agent.core.models import Insight, PlanContext
from training_agent.planner.base import PlanInsight
from training_agent.planner.load import weekly_load_ratio
from training_agent.planner.params import load_section

DEFAULTS = {"chronic_weeks": 8, "lookback_days": 90, "min_history_days": 28, "min_chronic_load": 150,
            "spike_ratio": 1.3, "high_ratio": 1.15, "low_ratio": 0.7}


class LoadBalance(PlanInsight):
    name = "load_balance"

    def __init__(self, params: dict | None = None):
        self.p = {**load_section(self.name, DEFAULTS), **(params or {})}

    def evaluate(self, ctx: PlanContext) -> Insight | None:
        p = self.p
        found = weekly_load_ratio(ctx.activities, ctx.day, p["chronic_weeks"], p["lookback_days"], p["min_history_days"])
        if found is None or found[1] < p["min_chronic_load"]:
            return None
        acute, chronic, weeks = found
        ratio = acute / chronic
        evidence = [f"last 7 days: load {acute:.0f}", f"your usual week ({weeks}-week average): {chronic:.0f}", f"that is {ratio:.0%} of normal"]
        meaning = "Fitness grows when load rises gradually. Big jumps raise the risk of fatigue and injury; long dips lose fitness."
        if ratio > p["spike_ratio"]:
            return Insight(id=self.name, area="load", status="act", priority=75, evidence=evidence, meaning=meaning,
                           headline=f"This week is a spike: {ratio:.0%} of your usual training load.",
                           action="Make the rest of this week easy so your body can catch up.")
        if ratio > p["high_ratio"]:
            return Insight(id=self.name, area="load", status="watch", priority=48, evidence=evidence, meaning=meaning,
                           headline=f"This week is on the high side: {ratio:.0%} of your usual load.",
                           action="Keep your hard sessions to one this week.")
        if ratio < p["low_ratio"]:
            return Insight(id=self.name, area="load", status="watch", priority=44, evidence=evidence, meaning=meaning,
                           headline=f"You have room to do more: this week is only {ratio:.0%} of your usual load.",
                           action="If you feel fresh, add one easy session or lengthen your long ride by about 10%.")
        return Insight(id=self.name, area="load", status="good", priority=28, evidence=evidence, meaning=meaning,
                       headline=f"Training load is in the sweet spot: {ratio:.0%} of your usual week.",
                       action="Stay with the plan.")
