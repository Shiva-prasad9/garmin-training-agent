"""Rules-based daily planner.

Combines the caps of all enabled rules, the week's open slots (from the active week plan source) and
the athlete's own session targets into a DayPlan: one recommendation plus an option for every intensity.
Every option can be chosen; the risk label only warns. No LLM involved (that layer comes later and works
inside these options).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, time, timedelta

from training_agent.core.models import (
    INTENSITY_ORDER, Activity, DayPlan, Intensity, PlanContext, PlannedSession, RuleVerdict, SessionOption,
    SessionSlot, Sport, lowest,
)
from training_agent.core.plugin import load_enabled_plugins
from training_agent.planner.base import Planner, PlannerRule, WeekPlanSource
from training_agent.planner.load import DEFAULT_RATE, hard_threshold, is_hard, load_rates
from training_agent.planner.params import ROOT, load_athlete, load_section
from training_agent.planner.prescriptions import DEFAULT_RIDE_BANDS, prescribe
from training_agent.planner.week_plan import fit_to_days, load_sources, monday_of, targets_for_week, week_progress

log = logging.getLogger(__name__)

DEFAULTS = {
    "key_session_gap_days": 5,  # recommend a hard key session if there was none in this many days
    "fatigue_volume_factor": 0.85,  # shorten sessions the day after a hard one
    "long_ride_minutes": 150,
    "load_factor": {"easy": 0.7, "moderate": 1.0, "hard": 1.4},  # effort per minute vs the athlete's typical
    "lookback_days": 90,
}
GYM_RATE = 0.15  # load per minute for strength work, used only when previewing tomorrow

# How well a kind of session suits each intensity (higher is better); decides which open slot is used.
KIND_SUIT = {
    "long": {Intensity.EASY: 1, Intensity.MODERATE: 3, Intensity.HARD: 3},   # a long ride is a moderate or hard day
    "short": {Intensity.EASY: 3, Intensity.MODERATE: 3, Intensity.HARD: 1},
    "strength": {Intensity.EASY: 3, Intensity.MODERATE: 3, Intensity.HARD: 2},
    "distance": {Intensity.EASY: 2, Intensity.MODERATE: 3, Intensity.HARD: 3},  # kinds such as "10k"
}
DEFAULT_SUIT = {Intensity.EASY: 2, Intensity.MODERATE: 2, Intensity.HARD: 2}
SPORT_WORD = {Sport.BIKE: "ride", Sport.RUN: "run", Sport.GYM: "strength session"}
ZONE_SHARES = {  # time in HR zones 1-5 of a planned session, used only for the tomorrow preview
    Intensity.EASY: [0.5, 0.5, 0, 0, 0], Intensity.MODERATE: [0, 0.2, 0.6, 0.2, 0], Intensity.HARD: [0, 0, 0.2, 0.4, 0.4],
}


def rank(level: Intensity) -> int:
    return INTENSITY_ORDER.index(level)


def _suit(kind: str, intensity: Intensity) -> int:
    key = "distance" if re.fullmatch(r"\d+(?:\.\d+)?k", kind) else kind
    return KIND_SUIT.get(key, DEFAULT_SUIT)[intensity]


class RulesPlanner(Planner):
    name = "rules_planner"

    def __init__(self, rules: list[PlannerRule] | None = None, sources: list[WeekPlanSource] | None = None,
                 params: dict | None = None, insights: list | None = None):
        config = ROOT / "config" / "features.yaml"
        self.rules = rules if rules is not None else load_enabled_plugins(config, "planner_rules")
        self.sources = sources if sources is not None else load_sources(config)
        self.insights = insights if insights is not None else load_enabled_plugins(config, "insights")
        self.p = {**DEFAULTS, **load_section("planner", {}), **(params or {})}
        athlete = load_athlete()
        self.max_hr = float(athlete.get("max_hr", 195))
        self.ride_bands = tuple(athlete.get("ride_bands_min", DEFAULT_RIDE_BANDS))

    # ---------- main entry ----------
    def plan_day(self, ctx: PlanContext) -> DayPlan:
        verdicts = [r.evaluate(ctx) for r in self.rules]
        cap = lowest(Intensity.HARD, *[v.max_intensity for v in verdicts])
        targets = targets_for_week(monday_of(ctx.day), self.sources)
        remaining, done = week_progress(targets, ctx.activities, ctx.day, self.p["long_ride_minutes"])
        remaining, dropped = fit_to_days(remaining, ctx.day)
        yesterday_sport = self._yesterday_sport(ctx)
        fatigue = any(v.rule == "hard_easy_alternation" and v.max_intensity != Intensity.HARD for v in verdicts)
        volume_factor = self.p["fatigue_volume_factor"] if fatigue else 1.0

        recommended = self._recommend(ctx, cap, remaining, targets.slots, yesterday_sport)
        options = [self._option(ctx, level, cap, recommended, verdicts, remaining, targets.slots,
                                yesterday_sport, volume_factor) for level in INTENSITY_ORDER]
        limits = [r for v in verdicts if v.max_intensity != Intensity.HARD for r in v.reasons]
        rec = next(o for o in options if o.intensity == recommended)
        summary = f"Recommended: {rec.title.lower()}." + (f" Held back by: {'; '.join(limits)}" if limits else "")
        if dropped:
            names = ", ".join(f"{s.sport.value} ({s.kind})" for s in dropped)
            summary += f" The week is behind, so it drops: {names}."
        return DayPlan(day=ctx.day, cap=cap, recommended=recommended, verdicts=verdicts, options=options, insights=self._insights(ctx),
                       week_source=targets.source, week_phase=targets.phase, remaining_slots=remaining, dropped_slots=dropped,
                       done_this_week=done, summary=summary)

    def _insights(self, ctx: PlanContext) -> list:
        """Guidance from the insight plugins, most important first. One failing plugin never breaks the plan."""
        found = []
        for plugin in self.insights:
            try:
                item = plugin.evaluate(ctx)
            except Exception:  # advisory only
                log.exception("insight %s failed", plugin.name)
                continue
            if item:
                found.append(item)
        return sorted(found, key=lambda i: -i.priority)

    def to_session(self, plan: DayPlan, intensity: Intensity) -> PlannedSession:
        option = next(o for o in plan.options if o.intensity == intensity)
        above_cap = rank(intensity) > rank(plan.cap)
        pres = option.prescription
        return PlannedSession(
            date=plan.day, sport=option.sport or Sport.REST, intensity=intensity, title=option.title,
            rationale=" ".join(option.reasons) if option.reasons else "Within what your recovery signals allow.",
            duration_min=round(pres.duration_min) if pres and pres.duration_min else None,
            rule_flags=[v.rule for v in plan.verdicts if rank(v.max_intensity) < rank(intensity)],
            recommended_intensity=plan.recommended, overridden=above_cap, warnings=option.reasons if above_cap else [],
        )

    # ---------- recommendation ----------
    def _recent_hard(self, ctx: PlanContext) -> bool:
        since = ctx.day - timedelta(days=self.p["key_session_gap_days"])
        history = [a for a in ctx.activities if ctx.day - timedelta(days=self.p["lookback_days"]) <= a.start_time.date() < ctx.day]
        rates = load_rates(history)
        threshold = hard_threshold(history, rates)
        recorded = any(is_hard(a, threshold, rates) for a in history if a.start_time.date() >= since)
        planned = any(s.intensity == Intensity.HARD and since <= s.date < ctx.day for s in ctx.chosen)
        return recorded or planned

    def _recommend(self, ctx, cap, remaining, template, yesterday_sport) -> Intensity:
        if cap == Intensity.REST:
            return Intensity.REST
        sessions_left = [s for s in remaining if s.sport != Sport.REST]
        rest_owed = any(s.sport == Sport.REST for s in remaining)
        days_left = 7 - ctx.day.weekday()  # including today
        free_day = days_left > len(sessions_left)
        if rest_owed and (not sessions_left or (rank(cap) <= rank(Intensity.EASY) and free_day)):
            return Intensity.REST
        if cap == Intensity.HARD and not self._recent_hard(ctx):
            slot, _ = self._choose_slot(remaining, template, Intensity.HARD, yesterday_sport)
            if slot and _suit(slot.kind, Intensity.HARD) == 3:
                return Intensity.HARD
        return lowest(cap, Intensity.MODERATE)

    # ---------- options ----------
    @staticmethod
    def _yesterday_sport(ctx: PlanContext) -> Sport | None:
        y = ctx.day - timedelta(days=1)
        done = [a for a in ctx.activities if a.start_time.date() == y]
        if done:
            return max(done, key=lambda a: a.duration_s).sport
        planned = [s for s in ctx.chosen if s.date == y]
        return planned[0].sport if planned else None

    @staticmethod
    def _choose_slot(remaining, template, intensity, yesterday_sport):
        """Best open slot for this intensity; if the week is already complete, an extra session from the template."""
        candidates = [s for s in remaining if s.sport != Sport.REST]
        extra = not candidates
        if extra:
            seen, candidates = set(), []
            for s in template:
                if s.sport != Sport.REST and (s.sport, s.kind) not in seen:
                    seen.add((s.sport, s.kind))
                    candidates.append(s)
        if not candidates:
            return None, False

        def score(s: SessionSlot) -> float:
            value = _suit(s.kind, intensity)
            if s.sport == yesterday_sport and s.sport in (Sport.RUN, Sport.BIKE):
                value -= 1.5  # avoid the same endurance sport two days running
            return value

        return max(candidates, key=score), extra

    def _option(self, ctx, level, cap, recommended, verdicts, remaining, template, yesterday_sport, volume_factor):
        limiting = [r for v in verdicts if rank(v.max_intensity) < rank(level) for r in v.reasons]
        diff = rank(level) - rank(cap)
        risk = "recommended" if level == recommended else "ok" if diff <= 0 else "caution" if diff == 1 else "not_advised"

        if level == Intensity.REST:
            option = SessionOption(intensity=level, sport=None, title="Rest day", risk=risk, reasons=limiting)
            option.tomorrow = self._tomorrow(ctx, None, level, None)
            return option

        slot, extra = self._choose_slot(remaining, template, level, yesterday_sport)
        if slot is None:
            return SessionOption(intensity=level, title="No session in this week's plan", risk=risk, reasons=limiting)
        history = ctx.activities
        prescription = prescribe(slot.sport, level, history, kind=slot.kind, max_hr=self.max_hr,
                                 volume_factor=volume_factor, today=ctx.day, ride_bands=self.ride_bands)
        word = SPORT_WORD.get(slot.sport, slot.sport.value)
        detail = f" ({slot.kind})" if slot.kind not in ("general", "strength") else ""
        reasons = list(limiting)
        if extra:
            reasons.append("Extra session: this week's plan is already complete.")
        if volume_factor < 1:
            reasons.append("Shortened because yesterday was a hard session.")
        option = SessionOption(intensity=level, sport=slot.sport, title=f"{level.value.capitalize()} {word}{detail}",
                               prescription=prescription, risk=risk, reasons=reasons)
        option.tomorrow = self._tomorrow(ctx, slot.sport, level, prescription.duration_min if prescription else 45)
        return option

    # ---------- tomorrow preview ----------
    def _tomorrow(self, ctx: PlanContext, sport: Sport | None, level: Intensity, minutes: float | None) -> str:
        """What this choice would do to tomorrow's limits (rules that need tomorrow's own readings are skipped)."""
        tomorrow = ctx.day + timedelta(days=1)
        activities = list(ctx.activities)
        chosen = list(ctx.chosen)
        if sport is not None and minutes:
            history = [a for a in ctx.activities if ctx.day - timedelta(days=self.p["lookback_days"]) <= a.start_time.date() < ctx.day]
            rate = load_rates(history).get(sport) or DEFAULT_RATE.get(sport, GYM_RATE)
            load = max(minutes * rate * self.p["load_factor"][level.value], 1.0)
            zones = [minutes * 60 * share for share in ZONE_SHARES[level]]
            activities.append(Activity(
                id=f"plan:{ctx.day}", source="plan", sport=sport, start_time=datetime.combine(ctx.day, time(12)),
                duration_s=minutes * 60, avg_hr=1.0, training_load=load, hr_zone_seconds=zones))
            chosen.append(PlannedSession(date=ctx.day, sport=sport, intensity=level, title="preview", rationale=""))
        sim = ctx.model_copy(update={"day": tomorrow, "activities": activities, "chosen": chosen})
        verdicts = [r.evaluate(sim) for r in self.rules if not r.uses_daily_readings]
        cap = lowest(Intensity.HARD, *[v.max_intensity for v in verdicts])
        if cap == Intensity.HARD:
            return "Tomorrow stays open to a hard session if you recover well."
        why = " ".join(r for v in verdicts if v.max_intensity == cap for r in v.reasons)
        return f"Tomorrow would be capped at {cap.value}: " + why.replace("so today is easy", "so tomorrow is easy")
