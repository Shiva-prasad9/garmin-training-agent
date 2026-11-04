"""Progression: how your longest session compares with before, and the next small step up."""

from __future__ import annotations

from datetime import timedelta

from training_agent.core.models import Insight, PlanContext, Sport
from training_agent.planner.base import PlanInsight


class Progression(PlanInsight):
    name = "progression"

    def evaluate(self, ctx: PlanContext) -> Insight | None:
        today = ctx.assessment_for(ctx.day)
        fresh = True
        if today:
            fresh = all(s is None or s.z is None or s.z > -1.5 for s in (today.signals.get("hrv_last_night_ms"), today.signals.get("sleep_score")))
        for sport, word in ((Sport.BIKE, "ride"), (Sport.RUN, "run")):
            recent = [a.duration_s for a in ctx.activities if sport == a.sport and ctx.day - timedelta(days=28) <= a.start_time.date() < ctx.day]
            before = [a.duration_s for a in ctx.activities if sport == a.sport and ctx.day - timedelta(days=84) <= a.start_time.date() < ctx.day - timedelta(days=28)]
            if len(recent) < 2 or not before:
                continue
            top = lambda xs: sum(sorted(xs, reverse=True)[:2]) / len(sorted(xs, reverse=True)[:2]) / 60  # two longest, so one outlier day does not mislead  # noqa: E731
            longest, earlier = top(recent), top(before)
            step = max(5, round(longest * 0.10 / 5) * 5)
            evidence = [f"typical long {word} in the last 4 weeks: {longest:.0f} min", f"typical long {word} in the 8 weeks before: {earlier:.0f} min"]
            meaning = "Endurance builds when your longest session grows slowly, about 10% at a time."
            if longest < earlier * 0.7:
                return Insight(id=self.name, area="progress", status="watch", priority=40, evidence=evidence, meaning=meaning,
                               headline=f"Your long {word}s have shortened ({longest:.0f} min, down from {earlier:.0f} min).",
                               action=f"Rebuild gradually: add about {step} minutes to your next long {word}.")
            if fresh:
                return Insight(id=self.name, area="progress", status="good", priority=30, evidence=evidence, meaning=meaning,
                               headline=f"Your long {word}s are holding at about {longest:.0f} minutes.",
                               action=f"When you feel fresh, make your next long {word} about {step} minutes longer.")
            return Insight(id=self.name, area="progress", status="good", priority=18, evidence=evidence, meaning=meaning,
                           headline=f"Your long {word}s are holding at about {longest:.0f} minutes.",
                           action=f"Hold the length for now; build the long {word} once recovery looks normal again.")
        return None
