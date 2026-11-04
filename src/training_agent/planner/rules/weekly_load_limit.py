"""Weekly load limit: no sudden jumps in training load."""

from __future__ import annotations

from datetime import timedelta

from training_agent.core.models import Intensity, PlanContext, RuleVerdict
from training_agent.planner.base import PlannerRule
from training_agent.planner.load import estimate_effort, load_rates
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
        p, d = self.p, ctx.day
        history = [a for a in ctx.activities if d - timedelta(days=p["lookback_days"]) <= a.start_time.date() < d]
        if not history or (d - min(a.start_time.date() for a in history)).days < p["min_history_days"]:
            return self._ok("Not enough history yet to judge weekly load.")
        rates = load_rates(history)

        def total(first_back: int, last_back: int) -> float:
            lo, hi = d - timedelta(days=first_back), d - timedelta(days=last_back)
            return sum(estimate_effort(a, rates).value for a in history if lo <= a.start_time.date() <= hi)

        history_days = (d - min(a.start_time.date() for a in history)).days
        weeks = max(1, min(p["chronic_weeks"], (history_days - 7) // 7))  # fewer weeks while history is short
        acute = total(7, 1)  # the last 7 days
        chronic = total(7 + 7 * weeks, 8) / weeks  # average week over the weeks before that
        if chronic < p["min_chronic_load"]:
            return self._ok("Your recent weekly load is too low to judge a spike.")
        ratio = acute / chronic
        if ratio > p["max_ratio"]:
            return RuleVerdict(rule=self.name, max_intensity=Intensity.EASY, reasons=[
                f"Load over the last 7 days ({acute:.0f}) is {ratio:.0%} of your {weeks}-week average ({chronic:.0f}), "
                "so the rest of the week is easy."])
        return self._ok(f"Load over the last 7 days ({acute:.0f}) is {ratio:.0%} of your {weeks}-week average ({chronic:.0f}).")
