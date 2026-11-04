"""Weekly load limit: no sudden jumps in training load."""

from __future__ import annotations

from training_agent.core.models import Intensity, PlanContext, RuleVerdict
from training_agent.planner.base import PlannerRule
from training_agent.planner.load import weekly_load_ratio
from training_agent.planner.params import load_section

DEFAULTS = {"max_ratio": 1.3, "min_chronic_load": 150, "chronic_weeks": 8, "lookback_days": 90,
            "min_history_days": 28}


class WeeklyLoadLimit(PlannerRule):
    name = "weekly_load_limit"

    def __init__(self, params: dict | None = None):
        self.p = {**load_section(self.name, DEFAULTS), **(params or {})}

    def _ok(self, why: str) -> RuleVerdict:
        return RuleVerdict(rule=self.name, max_intensity=Intensity.HARD, reasons=[why])

    def evaluate(self, ctx: PlanContext) -> RuleVerdict:
        p = self.p
        found = weekly_load_ratio(ctx.activities, ctx.day, p["chronic_weeks"], p["lookback_days"], p["min_history_days"])
        if found is None:
            return self._ok("Not enough history yet to judge weekly load.")
        acute, chronic, weeks = found  # the last 7 days, and the average week before that
        if chronic < p["min_chronic_load"]:
            return self._ok("Your recent weekly load is too low to judge a spike.")
        ratio = acute / chronic
        if ratio > p["max_ratio"]:
            return RuleVerdict(rule=self.name, max_intensity=Intensity.EASY, reasons=[
                f"Load over the last 7 days ({acute:.0f}) is {ratio:.0%} of your {weeks}-week average ({chronic:.0f}), "
                "so the rest of the week is easy."])
        return self._ok(f"Load over the last 7 days ({acute:.0f}) is {ratio:.0%} of your {weeks}-week average ({chronic:.0f}).")
