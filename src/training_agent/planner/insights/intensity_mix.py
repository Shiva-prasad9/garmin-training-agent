"""Intensity mix: most endurance training should be easy, with a little hard work on top."""

from __future__ import annotations

from datetime import timedelta

from training_agent.core.models import Insight, PlanContext
from training_agent.planner.base import PlanInsight
from training_agent.planner.params import load_athlete, load_section

DEFAULTS = {"window_days": 28, "min_sessions": 4, "good_easy_share": 0.70, "low_easy_share": 0.55}


class IntensityMix(PlanInsight):
    name = "intensity_mix"

    def __init__(self, params: dict | None = None, athlete: dict | None = None):
        self.p = {**load_section(self.name, DEFAULTS), **(params or {})}
        self.max_hr = float((athlete if athlete is not None else load_athlete()).get("max_hr", 195))

    def evaluate(self, ctx: PlanContext) -> Insight | None:
        p = self.p
        first = ctx.day - timedelta(days=p["window_days"])
        zoned = [a for a in ctx.activities if first <= a.start_time.date() < ctx.day and a.hr_zone_seconds and sum(a.hr_zone_seconds) > 0]
        if len(zoned) < p["min_sessions"]:
            return None
        total = sum(sum(a.hr_zone_seconds) for a in zoned)
        easy = sum(a.hr_zone_seconds[0] + a.hr_zone_seconds[1] for a in zoned) / total
        hard = sum(a.hr_zone_seconds[3] + a.hr_zone_seconds[4] for a in zoned) / total
        evidence = [f"{easy:.0%} of your training time was easy (zones 1-2)", f"{hard:.0%} was hard (zones 4-5)",
                    f"based on {len(zoned)} workouts with heart rate in the last {p['window_days']} days"]
        meaning = "Endurance gains come mostly from lots of easy work. When easy days drift into the middle, you get tired without getting faster."
        ceiling = round(0.75 * self.max_hr)
        if easy < p["low_easy_share"]:
            return Insight(id=self.name, area="intensity", status="watch", priority=62, evidence=evidence, meaning=meaning,
                           headline=f"Only {easy:.0%} of your training was easy. Too much of it sits in the medium-to-hard middle.",
                           action=f"Make easy days truly easy: keep your heart rate under {ceiling} bpm, and save the effort for one hard session a week.")
        if easy < p["good_easy_share"]:
            return Insight(id=self.name, area="intensity", status="watch", priority=46, evidence=evidence, meaning=meaning,
                           headline=f"{easy:.0%} of your training was easy: close to the usual target of about 70-80%.",
                           action=f"On your next easy session, hold your heart rate under {ceiling} bpm.")
        return Insight(id=self.name, area="intensity", status="good", priority=24, evidence=evidence, meaning=meaning,
                       headline=f"Your mix is well balanced: {easy:.0%} easy, {hard:.0%} hard.",
                       action="Keep easy days easy.")
