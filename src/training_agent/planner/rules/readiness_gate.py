"""Readiness gate: caps today's intensity from how you compare with your own normal."""

from __future__ import annotations

from training_agent.core.models import Intensity, PlanContext, RuleVerdict, lowest
from training_agent.planner.base import PlannerRule
from training_agent.planner.params import load_section

# signal -> (label, +1 if higher is better / -1 if lower is better)
SIGNALS = {
    "sleep_score": ("Sleep score", 1),
    "hrv_last_night_ms": ("HRV", 1),
    "body_battery_morning": ("Morning Body Battery", 1),
    "resting_hr": ("Resting heart rate", -1),
}
DEFAULTS = {"notable_z": 1.5, "unusual_z": 2.5, "illness_z": 2.0}


def _fmt(v: float | None) -> str:
    if v is None:
        return "-"
    return f"{v:.0f}" if abs(v) >= 100 else f"{v:.1f}".rstrip("0").rstrip(".")


class ReadinessGate(PlannerRule):
    name = "readiness_gate"
    uses_daily_readings = True

    def __init__(self, params: dict | None = None):
        self.p = {**load_section(self.name, DEFAULTS), **(params or {})}

    def evaluate(self, ctx: PlanContext) -> RuleVerdict:
        today = ctx.assessment_for(ctx.day)
        if today is None:
            return RuleVerdict(rule=self.name, max_intensity=Intensity.EASY,
                               reasons=["No data for today yet, staying careful."])
        p = self.p
        reasons: list[str] = []
        notable = unusual = evaluable = 0
        adverse: dict[str, float] = {}  # positive = worse than your normal

        for sig, (label, good) in SIGNALS.items():
            s = today.signals.get(sig)
            if s is None or s.z is None:
                continue
            evaluable += 1
            adverse[sig] = -s.z * good
            word = "low" if good == 1 else "high"
            detail = f"{_fmt(s.value)} vs usual {_fmt(s.baseline)}"
            worse_trend = s.trend in ("up", "down") and ((s.trend == "up") != (good == 1))
            if adverse[sig] >= p["unusual_z"]:
                unusual += 1
                reasons.append(f"{label} unusually {word} ({detail})")
            elif adverse[sig] >= p["notable_z"]:
                notable += 1
                reasons.append(f"{label} {word} ({detail})")
            elif worse_trend:
                notable += 1
                reasons.append(f"{label} trending worse over 7 days (average {_fmt(s.trend_mean)} vs usual {_fmt(s.baseline)})")

        cap = Intensity.HARD
        if (adverse.get("resting_hr", 0) >= p["illness_z"] and adverse.get("hrv_last_night_ms", 0) >= p["illness_z"]):
            cap = Intensity.REST
            reasons.insert(0, "Resting heart rate up and HRV down together: possible illness or heavy stress.")
        elif unusual >= 1 or notable >= 2:
            cap = Intensity.EASY
        elif notable == 1:
            cap = Intensity.MODERATE

        if "short_sleep" in today.flags:
            cap = lowest(cap, Intensity.MODERATE)
            reasons.append("Very short night: sleep readings ignored, so staying careful.")
        elif "missing_sleep" in today.flags and "missing_hrv" in today.flags:
            cap = lowest(cap, Intensity.MODERATE)
            reasons.append("No sleep or HRV data today, staying careful.")
        if evaluable < 2:
            cap = lowest(cap, Intensity.MODERATE)
            reasons.append("Too little recent history to compare today with your normal.")
        if not reasons:
            reasons.append("Recovery signals look normal for you.")
        return RuleVerdict(rule=self.name, max_intensity=cap, reasons=reasons)
