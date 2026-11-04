"""Session targets (duration, distance, pace or speed, heart-rate range) from the athlete's own history.

Past workouts are sorted into easy / moderate / hard by average heart rate as a share of max HR
(or by the athlete's own 1-10 rating when there was no heart rate). A target is the typical value of
the matching past sessions. With fewer than `min_pool` matches the targets fall back to plain defaults
and say so. Pure functions; no I/O.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from statistics import median

from training_agent.core.models import Activity, Intensity, Prescription, Sport

EASY_BELOW, MODERATE_BELOW = 0.75, 0.85  # share of max heart rate
HR_BANDS = {Intensity.EASY: (0.60, 0.75), Intensity.MODERATE: (0.75, 0.85), Intensity.HARD: (0.85, 0.92)}
MIN_MINUTES = 20
DURATION_CAP = {Intensity.MODERATE: 0.8, Intensity.HARD: 0.6}  # harder sessions are shorter than easy ones
MIN_HR_WIDTH = 6  # beats per minute

# Fallbacks until there is enough history: (duration in minutes, pace min/km for runs or speed km/h for rides).
DEFAULTS = {
    (Sport.RUN, Intensity.EASY): (40, 7.0), (Sport.RUN, Intensity.MODERATE): (50, 6.4), (Sport.RUN, Intensity.HARD): (50, 5.8),
    (Sport.BIKE, Intensity.EASY): (90, 20.0), (Sport.BIKE, Intensity.MODERATE): (75, 24.0), (Sport.BIKE, Intensity.HARD): (60, 27.0),
    (Sport.GYM, Intensity.EASY): (45, None), (Sport.GYM, Intensity.MODERATE): (50, None), (Sport.GYM, Intensity.HARD): (55, None),
}


SPORTS_WITH_TARGETS = {sport for sport, _ in DEFAULTS}  # adding a sport = adding its DEFAULTS rows
ENDURANCE_SPORTS = (Sport.RUN, Sport.BIKE)  # sports whose harder sessions are shorter than easy ones


def classify(a: Activity, max_hr: float) -> Intensity | None:
    """Easy / moderate / hard from heart rate, else from the athlete's own 1-10 rating, else unknown."""
    if a.avg_hr:
        share = a.avg_hr / max_hr
        return Intensity.EASY if share < EASY_BELOW else Intensity.MODERATE if share < MODERATE_BELOW else Intensity.HARD
    if a.perceived_exertion:
        pe = a.perceived_exertion
        return Intensity.EASY if pe <= 4 else Intensity.MODERATE if pe <= 6 else Intensity.HARD
    return None


def _quantile(values: list[float], q: float) -> float:
    s = sorted(values)
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _volume_quantile(kind: str) -> float:
    return {"long": 0.75, "short": 0.25}.get(kind, 0.5)


def _target_distance(kind: str) -> float | None:
    """A kind like "10k" or "21.1k" fixes the distance."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)k", kind)
    return float(m.group(1)) if m else None


def prescribe(sport: Sport, intensity: Intensity, history: list[Activity], *, kind: str = "general",
              max_hr: float = 195, volume_factor: float = 1.0, today: date | None = None,
              lookback_days: int = 180, min_pool: int = 3) -> Prescription | None:
    """Targets for one session, or None for rest and for sports without targets."""
    if intensity == Intensity.REST or sport not in SPORTS_WITH_TARGETS:
        return None

    pool = []
    for a in history:
        if a.sport != sport or a.duration_s < MIN_MINUTES * 60:
            continue
        if today and not (today - timedelta(days=lookback_days) <= a.start_time.date() < today):
            continue
        bucket = classify(a, max_hr)
        if sport == Sport.GYM or bucket == intensity:  # gym heart rate says little, so all gym sessions count
            pool.append(a)

    lo_share, hi_share = HR_BANDS[intensity]
    hr_low, hr_high = round(lo_share * max_hr), round(hi_share * max_hr)

    if len(pool) < min_pool:
        minutes, rate = DEFAULTS[(sport, intensity)]
        distance = _target_distance(kind)
        pace = rate if sport == Sport.RUN else None
        speed = rate if sport == Sport.BIKE else None
        if distance and pace:
            minutes = distance * pace
        distance = distance or (round(minutes / 60 * speed, 1) if speed else round(minutes / pace, 1) if pace else None)
        return Prescription(
            sport=sport, intensity=intensity, duration_min=round(minutes * volume_factor),
            distance_km=round(distance * volume_factor, 1) if distance else None, pace_min_per_km=pace,
            speed_kmh=speed, hr_low=hr_low, hr_high=hr_high, based_on=len(pool),
            note=f"Default targets: only {len(pool)} similar past session(s) found.")

    minutes_list = [a.duration_s / 60 for a in pool]
    with_distance = [a for a in pool if a.distance_m and a.distance_m > 0]
    paces = [a.duration_s / 60 / (a.distance_m / 1000) for a in with_distance]
    speeds = [(a.distance_m / 1000) / (a.duration_s / 3600) for a in with_distance]
    hrs = [a.avg_hr for a in pool if a.avg_hr]

    q = _volume_quantile(kind)
    minutes = _quantile(minutes_list, q)
    pace = median(paces) if sport == Sport.RUN and paces else None
    speed = median(speeds) if sport == Sport.BIKE and speeds else None
    distance = _target_distance(kind)
    if intensity in DURATION_CAP and not distance and sport in ENDURANCE_SPORTS:
        easy = prescribe(sport, Intensity.EASY, history, kind=kind, max_hr=max_hr, today=today,
                         lookback_days=lookback_days, min_pool=min_pool)
        minutes = min(minutes, easy.duration_min * DURATION_CAP[intensity])
    if distance and pace:
        minutes = distance * pace  # a fixed distance sets the time
    elif pace:
        distance = minutes / pace
    elif speed:
        distance = minutes / 60 * speed
    if hrs:
        hr_low, hr_high = round(_quantile(hrs, 0.25)), round(_quantile(hrs, 0.75))
        if hr_high - hr_low < MIN_HR_WIDTH:  # a few similar sessions give a needlessly narrow range
            mid = (hr_low + hr_high) / 2
            hr_low, hr_high = round(mid - MIN_HR_WIDTH / 2), round(mid + MIN_HR_WIDTH / 2)

    effort_note = "" if sport != Sport.GYM else " Effort comes from the weights, not heart rate."
    return Prescription(
        sport=sport, intensity=intensity, duration_min=round(minutes * volume_factor),
        distance_km=round(distance * volume_factor, 1) if distance else None,
        pace_min_per_km=round(pace, 2) if pace else None, speed_kmh=round(speed, 1) if speed else None,
        hr_low=hr_low, hr_high=hr_high, based_on=len(pool),
        note=f"Based on {len(pool)} of your {intensity.value} {sport.value} sessions.{effort_note}")
