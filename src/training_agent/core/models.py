"""Shared data contracts.

Stages (collect, store, plan, publish) communicate exclusively through these
models. No stage imports another stage's internals. Fields were chosen from
what the Garmin Personal API actually returns (see scripts/garmin_probe.py).

Convention: every signal that may be missing is Optional (None). Consumers
must tolerate gaps. To add data later, add an Optional field; nothing breaks.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Sport(str, Enum):
    RUN = "run"
    BIKE = "bike"
    GYM = "gym"
    REST = "rest"
    OTHER = "other"


class Intensity(str, Enum):
    """Allowed intensity, ordered REST < EASY (Z1-Z2) < MODERATE < HARD."""

    REST = "rest"
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"


class Readiness(str, Enum):
    """Coarse readiness band derived by the planner from DailyMetrics."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DailyMetrics(BaseModel):
    """One day of Garmin recovery signals, as reported by Garmin (not recomputed)."""

    date: date
    source: str = "garmin"
    sleep_hours: float | None = None
    sleep_score: int | None = None
    hrv_last_night_ms: int | None = None
    hrv_weekly_avg_ms: int | None = None
    hrv_status: str | None = None
    resting_hr: int | None = None
    body_battery_morning: int | None = None
    body_battery_min: int | None = None
    body_battery_max: int | None = None
    stress_avg: int | None = None
    recovery_hours: float | None = None  # not exposed by the personal API so far


class SignalAssessment(BaseModel):
    """One signal on one day, compared with the athlete's own recent baseline."""

    value: float | None = None
    baseline: float | None = None  # median of the previous valid days
    spread: float | None = None  # robust spread (scaled MAD, with a floor)
    z: float | None = None  # (value - baseline) / spread; None if value invalid or no baseline
    # Short-term trend: plain average of the last N valid days versus the baseline.
    trend: str | None = None  # "up" | "down" | "steady"; None = not enough valid days
    trend_mean: float | None = None
    trend_z: float | None = None  # (mean - baseline) / (spread / sqrt(days used))
    trend_n: int = 0  # valid days that went into the average


class DailyAssessment(BaseModel):
    """Data-quality flags and baseline comparison for one day.

    flags: missing_sleep, short_sleep, missing_hrv, hrv_outlier, insufficient_baseline.
    signals: keyed by DailyMetrics field name.
    """

    date: date
    flags: list[str] = Field(default_factory=list)
    signals: dict[str, SignalAssessment] = Field(default_factory=dict)


class Activity(BaseModel):
    """One completed workout from any source (Garmin, Strava export)."""

    id: str  # source-prefixed, e.g. "garmin:123"
    source: str
    sport: Sport
    source_sport: str | None = None  # original type label from the source
    start_time: datetime
    duration_s: float
    distance_m: float | None = None
    avg_hr: float | None = None  # None for rides without HR (e.g. Sigma ROX 4.0)
    max_hr: float | None = None
    training_load: float | None = None  # Garmin activityTrainingLoad
    hr_zone_seconds: list[float] | None = None  # time in zones 1-5
    raw_ref: str | None = None  # reference to raw file under data/raw/, never modified
    relative_effort: float | None = None  # Strava Relative Effort (needs heart rate)
    perceived_exertion: float | None = None  # athlete-entered, 1-10
    perceived_relative_effort: float | None = None  # Strava effort computed from the 1-10 rating (no HR)
    avg_power_w: float | None = None  # Strava estimates this for rides without a power meter
    elevation_gain_m: float | None = None


class PlannedSession(BaseModel):
    """One planned session produced by the planner."""

    date: date
    sport: Sport
    intensity: Intensity  # capped by rules, chosen by the LLM within the cap
    title: str
    rationale: str  # shown in the daily brief
    duration_min: int | None = None
    rule_flags: list[str] = Field(default_factory=list)  # guardrails that applied
    recommended_intensity: Intensity | None = None  # what the rules advised; differs from `intensity` on override
    overridden: bool = False  # True when the athlete chose above the recommendation
    warnings: list[str] = Field(default_factory=list)


class DailyBrief(BaseModel):
    """What the outputs stage publishes for one day."""

    date: date
    session: PlannedSession
    readiness: Readiness
    metrics: DailyMetrics | None = None
    upcoming: list[PlannedSession] = Field(default_factory=list)


# ---------- planner contracts ----------

INTENSITY_ORDER = [Intensity.REST, Intensity.EASY, Intensity.MODERATE, Intensity.HARD]


def lowest(*levels: Intensity) -> Intensity:
    """The most restrictive of several intensity levels."""
    return min(levels, key=INTENSITY_ORDER.index)


class RuleVerdict(BaseModel):
    """What one planner rule says about a day: the highest intensity it allows, and why."""

    rule: str
    max_intensity: Intensity
    reasons: list[str] = Field(default_factory=list)


class PlanContext(BaseModel):
    """Everything a planner rule may look at. Rules never fetch data themselves.

    assessments: daily baseline comparisons (see DailyAssessment), oldest first.
    activities: workouts from all sources, duplicates already merged.
    chosen: sessions the athlete accepted (so an override shapes the days that follow).
    """

    day: date
    assessments: list[DailyAssessment] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)
    chosen: list[PlannedSession] = Field(default_factory=list)

    def assessment_for(self, d: date) -> DailyAssessment | None:
        return next((a for a in self.assessments if a.date == d), None)


class Prescription(BaseModel):
    """Concrete targets for a session, derived from the athlete's own history."""

    sport: Sport
    intensity: Intensity
    duration_min: float | None = None
    distance_km: float | None = None
    pace_min_per_km: float | None = None  # runs
    speed_kmh: float | None = None  # rides
    hr_low: int | None = None
    hr_high: int | None = None
    based_on: int = 0  # number of past sessions behind these numbers
    note: str = ""


class SessionOption(BaseModel):
    """One choice offered to the athlete for a day. All options can be chosen; risk only warns."""

    intensity: Intensity
    sport: Sport | None = None
    title: str
    prescription: Prescription | None = None
    risk: str = "recommended"  # "recommended" | "caution" | "not_advised"
    reasons: list[str] = Field(default_factory=list)
    tomorrow: str | None = None  # what choosing this means for the next day
