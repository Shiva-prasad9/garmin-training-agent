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


class PlannedSession(BaseModel):
    """One planned session produced by the planner."""

    date: date
    sport: Sport
    intensity: Intensity  # capped by rules, chosen by the LLM within the cap
    title: str
    rationale: str  # shown in the daily brief
    duration_min: int | None = None
    rule_flags: list[str] = Field(default_factory=list)  # guardrails that applied


class DailyBrief(BaseModel):
    """What the outputs stage publishes for one day."""

    date: date
    session: PlannedSession
    readiness: Readiness
    metrics: DailyMetrics | None = None
    upcoming: list[PlannedSession] = Field(default_factory=list)
