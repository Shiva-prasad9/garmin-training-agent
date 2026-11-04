"""Effort estimates for workouts and hard-day detection (pure functions, no I/O).

Effort sources, best first (decision D016):
  1. Garmin training load, when a heart-rate recording exists
  2. Strava Relative Effort x 1.42
  3. Strava Perceived Relative Effort (from the athlete's 1-10 rating) x 1.42, rough
  4. duration x the athlete's typical load per minute for the sport, an estimate
"""

from __future__ import annotations

from datetime import date, timedelta

from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from training_agent.core.models import Activity, Sport

STRAVA_TO_LOAD = 1.42  # Garmin-scale load per Strava relative-effort point (calibrated on 21 workouts)
MIN_GARMIN_LOAD = 1.0  # below this Garmin's load means "nothing recorded" (rides without heart rate)
MIN_RATE_SAMPLES = 3
DEFAULT_RATE = {Sport.BIKE: 1.3, Sport.RUN: 2.5, Sport.GYM: 0.15}  # load per minute, used until enough history exists
MIN_EFFORT_MINUTES = 20


@dataclass(frozen=True)
class Effort:
    value: float
    source: str  # "garmin_load" | "strava_effort" | "perceived_effort" | "duration_estimate" | "none"

    @property
    def is_estimate(self) -> bool:
        return self.source in ("perceived_effort", "duration_estimate")


def _measured(a: Activity) -> Effort | None:
    """Sources 1 and 2: effort that comes from a heart-rate recording."""
    if a.avg_hr is not None and (a.training_load or 0) >= MIN_GARMIN_LOAD:
        return Effort(a.training_load, "garmin_load")
    if a.relative_effort:
        return Effort(a.relative_effort * STRAVA_TO_LOAD, "strava_effort")
    return None


def load_rates(activities: list[Activity]) -> dict[Sport, float]:
    """The athlete's typical load per minute for each sport, from workouts with measured effort."""
    per_sport: dict[Sport, list[float]] = defaultdict(list)
    for a in activities:
        m = _measured(a)
        if m and a.duration_s >= MIN_EFFORT_MINUTES * 60:
            per_sport[a.sport].append(m.value / (a.duration_s / 60))
    return {s: median(v) for s, v in per_sport.items() if len(v) >= MIN_RATE_SAMPLES}


def estimate_effort(a: Activity, rates: dict[Sport, float]) -> Effort:
    """Best available effort for a workout, on the Garmin load scale."""
    m = _measured(a)
    if m:
        return m
    if a.perceived_relative_effort:
        return Effort(a.perceived_relative_effort * STRAVA_TO_LOAD, "perceived_effort")
    rate = rates.get(a.sport) or DEFAULT_RATE.get(a.sport)
    if rate and a.duration_s >= 5 * 60:
        scale = min(max(a.perceived_exertion / 5, 0.4), 2.0) if a.perceived_exertion else 1.0  # rating 5 = typical
        return Effort(a.duration_s / 60 * rate * scale, "duration_estimate")
    return Effort(0.0, "none")


def hard_threshold(activities: list[Activity], rates: dict[Sport, float],
                   percentile: float = 0.75, min_samples: int = 8) -> float | None:
    """Effort level above which a workout counts as hard for this athlete (None if too little history)."""
    values = [estimate_effort(a, rates).value for a in activities
              if a.sport != Sport.GYM and a.duration_s >= MIN_EFFORT_MINUTES * 60]
    values = sorted(v for v in values if v > 0)
    if len(values) < min_samples:
        return None
    return values[min(len(values) - 1, int(percentile * len(values)))]


def is_hard(a: Activity, threshold: float | None, rates: dict[Sport, float], zone_share: float = 0.25) -> bool:
    """Hard = lots of time in heart-rate zones 4-5, or effort in the athlete's top quarter. Gym never counts."""
    if a.sport == Sport.GYM:
        return False
    z = a.hr_zone_seconds
    if z and len(z) >= 5 and sum(z) >= MIN_EFFORT_MINUTES * 60 and (z[3] + z[4]) / sum(z) >= zone_share:
        return True
    return threshold is not None and estimate_effort(a, rates).value >= threshold


def weekly_load_ratio(activities: list[Activity], day: date, chronic_weeks: int = 8, lookback_days: int = 90,
                      min_history_days: int = 28) -> tuple[float, float, int] | None:
    """(load of the last 7 days, average weekly load before that, weeks averaged), or None with too little history.

    Shared by the weekly load rule and the load-balance insight so they always agree.
    """
    history = [a for a in activities if day - timedelta(days=lookback_days) <= a.start_time.date() < day]
    if not history:
        return None
    history_days = (day - min(a.start_time.date() for a in history)).days
    if history_days < min_history_days:
        return None
    rates = load_rates(history)

    def total(first_back: int, last_back: int) -> float:
        lo, hi = day - timedelta(days=first_back), day - timedelta(days=last_back)
        return sum(estimate_effort(a, rates).value for a in history if lo <= a.start_time.date() <= hi)

    weeks = max(1, min(chronic_weeks, (history_days - 7) // 7))  # fewer weeks while history is short
    return total(7, 1), total(7 + 7 * weeks, 8) / weeks, weeks
