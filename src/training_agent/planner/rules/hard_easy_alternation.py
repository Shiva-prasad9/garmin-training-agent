"""Hard/easy alternation: after a hard day, the next day is easy."""

from __future__ import annotations

from datetime import timedelta

from training_agent.core.models import Intensity, PlanContext, RuleVerdict
from training_agent.planner.base import PlannerRule
from training_agent.planner.load import estimate_effort, hard_threshold, is_hard, load_rates
from training_agent.planner.params import load_section

DEFAULTS = {"hard_load_percentile": 0.75, "hard_zone_share": 0.25, "lookback_days": 90}


class HardEasyAlternation(PlannerRule):
    name = "hard_easy_alternation"

    def __init__(self, params: dict | None = None):
        self.p = {**load_section(self.name, DEFAULTS), **(params or {})}

    def evaluate(self, ctx: PlanContext) -> RuleVerdict:
        p = self.p
        yesterday = ctx.day - timedelta(days=1)
        since = ctx.day - timedelta(days=p["lookback_days"])
        history = [a for a in ctx.activities if since <= a.start_time.date() < ctx.day]
        rates = load_rates(history)
        threshold = hard_threshold(history, rates, p["hard_load_percentile"])

        done = [a for a in history if a.start_time.date() == yesterday]
        if done:  # what actually happened wins over what was planned
            hard = [a for a in done if is_hard(a, threshold, rates, p["hard_zone_share"])]
            if hard:
                a = hard[0]
                e = estimate_effort(a, rates)
                return RuleVerdict(rule=self.name, max_intensity=Intensity.EASY, reasons=[
                    f"Yesterday's {a.sport.value} was a hard session (effort about {e.value:.0f}), so today is easy."])
        elif any(s.date == yesterday and s.intensity == Intensity.HARD for s in ctx.chosen):
            return RuleVerdict(rule=self.name, max_intensity=Intensity.EASY,
                               reasons=["A hard session was planned for yesterday, so today is easy."])
        return RuleVerdict(rule=self.name, max_intensity=Intensity.HARD, reasons=["No hard session yesterday."])
