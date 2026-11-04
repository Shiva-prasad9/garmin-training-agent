"""Recovery: are HRV and resting heart rate moving the right way over the week?"""

from __future__ import annotations

from training_agent.core.models import Insight, PlanContext
from training_agent.planner.base import PlanInsight


class RecoveryTrend(PlanInsight):
    name = "recovery_trend"

    def evaluate(self, ctx: PlanContext) -> Insight | None:
        today = ctx.assessment_for(ctx.day) or (ctx.assessments[-1] if ctx.assessments else None)
        if today is None:
            return None
        hrv, rhr = today.signals.get("hrv_last_night_ms"), today.signals.get("resting_hr")
        if not hrv or not rhr or hrv.trend is None or rhr.trend is None:
            return None
        bad = []
        if hrv.trend == "down":
            bad.append("HRV has been trending down")
        if rhr.trend == "up":
            bad.append("resting heart rate has been creeping up")
        if hrv.z is not None and hrv.z <= -1.5:
            bad.append("last night's HRV was unusually low")
        evidence = [f"HRV 7-day average {hrv.trend_mean:.0f} ms (your usual {hrv.baseline:.0f})" if hrv.baseline else "HRV trend",
                    f"resting heart rate 7-day average {rhr.trend_mean:.0f} bpm (your usual {rhr.baseline:.0f})" if rhr.baseline else "resting heart rate trend"]
        meaning = "HRV and resting heart rate are Garmin's clearest signals of how well your body is absorbing training."
        if len(bad) >= 2:
            return Insight(id=self.name, area="recovery", status="act", priority=80, evidence=evidence, meaning=meaning,
                           headline="Your recovery signals are slipping: " + " and ".join(bad) + ".",
                           action="Keep the next two days easy or take a rest day, then check again.")
        if bad:
            return Insight(id=self.name, area="recovery", status="watch", priority=52, evidence=evidence, meaning=meaning,
                           headline=f"One recovery signal needs watching: {bad[0]}.",
                           action="Keep today's effort easy and see whether it settles by tomorrow.")
        return Insight(id=self.name, area="recovery", status="good", priority=20, evidence=evidence, meaning=meaning,
                       headline="Your HRV and resting heart rate are steady or improving.",
                       action="You can train as planned.")
