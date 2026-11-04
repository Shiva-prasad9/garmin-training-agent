"""Personal baselines and data-quality flags (pure functions, no I/O except load_params).

Garmin's metrics are used as reported. This module only answers: "is this day's
value normal for this athlete, and can the value be trusted?"

Trend: plain average of the last `trend_days` valid days compared with the baseline,
scaled by spread / sqrt(days used). Those days partly overlap the baseline window,
which makes the trend conservative, never too eager.

Method: baseline = median of the previous `window_days` valid values;
spread = scaled median absolute deviation (robust to outliers). Today is never
part of its own baseline. Thresholds live in config/rules.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from datetime import date, timedelta
from pathlib import Path
from statistics import median

import yaml

from training_agent.core.models import DailyAssessment, DailyMetrics, SignalAssessment

SIGNALS = ["sleep_hours", "sleep_score", "hrv_last_night_ms", "resting_hr", "body_battery_morning"]
# Signals that come from the night's recording: unreliable if the night was too short.
SLEEP_DEPENDENT = {"sleep_hours", "sleep_score", "hrv_last_night_ms"}
ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class BaselineParams:
    window_days: int = 28
    min_points: int = 14
    min_sleep_hours: float = 3.0
    hrv_outlier_z: float = 4.0
    min_spread_pct: float = 0.03  # spread floor as a fraction of the baseline
    trend_days: int = 7  # window for the short-term average (includes today)
    min_trend_points: int = 4  # fewer valid days than this means "no trend"
    trend_z_threshold: float = 1.5  # |trend_z| below this counts as steady


def load_params(path: str | Path = ROOT / "config" / "rules.yaml") -> BaselineParams:
    """Read thresholds from rules.yaml; missing keys fall back to defaults."""
    cfg = {}
    p = Path(path)
    if p.exists():
        cfg = yaml.safe_load(p.read_text()) or {}
    merged = {**(cfg.get("baselines") or {}), **(cfg.get("data_quality") or {})}
    known = BaselineParams.__dataclass_fields__
    return BaselineParams(**{k: v for k, v in merged.items() if k in known})


def assess(metrics: list[DailyMetrics], params: BaselineParams | None = None) -> list[DailyAssessment]:
    """Return one DailyAssessment per input day, sorted by date."""
    params = params or BaselineParams()
    by_date = {m.date: m for m in metrics}
    short = {d for d, m in by_date.items() if m.sleep_hours is not None and m.sleep_hours < params.min_sleep_hours}

    def valid(d: date, sig: str) -> float | None:
        m = by_date.get(d)
        if m is None or d in short and sig in SLEEP_DEPENDENT:
            return None
        return getattr(m, sig)

    out: list[DailyAssessment] = []
    for d in sorted(by_date):
        m = by_date[d]
        flags: list[str] = []
        if m.sleep_hours is None:
            flags.append("missing_sleep")
        elif d in short:
            flags.append("short_sleep")
        if m.hrv_last_night_ms is None:
            flags.append("missing_hrv")

        signals: dict[str, SignalAssessment] = {}
        for sig in SIGNALS:
            history = [
                v for k in range(1, params.window_days + 1)
                if (v := valid(d - timedelta(days=k), sig)) is not None
            ]
            baseline = spread = z = None
            if len(history) >= params.min_points:
                baseline = median(history)
                mad = median(abs(x - baseline) for x in history)
                spread = max(1.4826 * mad, params.min_spread_pct * abs(baseline), 1e-6)
                current = valid(d, sig)
                if current is not None:
                    z = (current - baseline) / spread
            trend = trend_mean = trend_z = None
            used = 0
            if baseline is not None:
                recent = [
                    v for k in range(params.trend_days)
                    if (v := valid(d - timedelta(days=k), sig)) is not None
                ]
                used = len(recent)
                if used >= params.min_trend_points:
                    trend_mean = sum(recent) / used
                    trend_z = (trend_mean - baseline) / (spread / sqrt(used))
                    trend = ("steady" if abs(trend_z) < params.trend_z_threshold
                             else "up" if trend_z > 0 else "down")
            signals[sig] = SignalAssessment(
                value=getattr(m, sig), baseline=baseline, spread=spread, z=z,
                trend=trend, trend_mean=trend_mean, trend_z=trend_z, trend_n=used,
            )

        if signals["hrv_last_night_ms"].z is not None and abs(signals["hrv_last_night_ms"].z) > params.hrv_outlier_z:
            flags.append("hrv_outlier")
        if m.hrv_last_night_ms is not None and signals["hrv_last_night_ms"].baseline is None:
            flags.append("insufficient_baseline")
        out.append(DailyAssessment(date=d, flags=flags, signals=signals))
    return out
