"""Console output: prints the daily brief as plain text. Email and calendar outputs will reuse `format_brief`."""

from __future__ import annotations

from training_agent.core.models import DailyBrief, Prescription
from training_agent.outputs.base import Output

RISK_WORDS = {"recommended": "RECOMMENDED", "ok": "fine to choose", "caution": "caution: above what your signals allow",
              "not_advised": "not advised"}


def _duration(minutes: float) -> str:
    h, m = divmod(round(minutes), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _targets(p: Prescription | None) -> str:
    if p is None:
        return ""
    parts = []
    if p.duration_min:
        parts.append(_duration(p.duration_min))
    if p.distance_km:
        parts.append(f"{p.distance_km:.1f} km")
    if p.pace_min_per_km:
        parts.append(f"{int(p.pace_min_per_km)}:{round((p.pace_min_per_km % 1) * 60):02d} /km")
    if p.speed_kmh:
        parts.append(f"{p.speed_kmh:.1f} km/h")
    if p.elevation_gain_m:
        parts.append(f"about {p.elevation_gain_m:.0f} m climbing")
    if p.hr_low:
        parts.append(f"HR {p.hr_low}-{p.hr_high}")
    return ", ".join(parts)


def _recovery_line(brief: DailyBrief) -> str:
    m = brief.metrics
    if m is None:
        return "Recovery today: no readings yet."
    parts = []
    if m.sleep_hours is not None:
        parts.append(f"sleep {m.sleep_hours:.1f} h" + (f" (score {m.sleep_score})" if m.sleep_score is not None else ""))
    if m.hrv_last_night_ms is not None:
        parts.append(f"HRV {m.hrv_last_night_ms} ms" + (f" ({m.hrv_status.lower()})" if m.hrv_status else ""))
    if m.resting_hr is not None:
        parts.append(f"resting HR {m.resting_hr}")
    if m.body_battery_morning is not None:
        parts.append(f"Body Battery {m.body_battery_morning} at wake-up")
    return "Recovery today: " + (", ".join(parts) or "no readings yet.")


def format_brief(brief: DailyBrief) -> str:
    plan = brief.plan
    rec = next(o for o in plan.options if o.intensity == plan.recommended)
    lines = [f"TRAINING BRIEF  {brief.date:%A %d %B %Y}", ""]
    lines += [f"! {note}" for note in brief.notes]
    if brief.notes:
        lines.append("")
    lines.append(_recovery_line(brief))
    lines.append(f"Allowed today: up to {plan.cap.value.upper()}")
    lines += [f"  - {r}" for v in plan.verdicts if v.max_intensity.value != "hard" for r in v.reasons] or ["  - Recovery signals look normal for you."]
    lines += ["", f"RECOMMENDED: {rec.title}"]
    if rec.prescription:
        lines.append(f"  {_targets(rec.prescription)}")
        if rec.prescription.note:
            lines.append(f"  ({rec.prescription.note})")
    if rec.tomorrow:
        lines.append(f"  {rec.tomorrow}")
    if plan.coach_note:
        lines += ["", f"Coach note ({plan.decided_by}): {plan.coach_note}"]
    lines += ["", "Your options (any of them can be chosen on the dashboard):"]
    for o in plan.options:
        lines.append(f"  [{o.intensity.value:8s}] {o.title}  - {RISK_WORDS.get(o.risk, o.risk)}")
        if o.prescription and o.intensity != plan.recommended:
            lines.append(f"             {_targets(o.prescription)}")
    lines += ["", f"This week ({plan.week_source.replace('_', ' ')}):"]
    lines.append("  done: " + ("; ".join(plan.done_this_week) or "nothing yet"))
    lines.append("  open: " + (", ".join(f"{s.sport.value} ({s.kind})" for s in plan.remaining_slots) or "nothing"))
    if plan.dropped_slots:
        lines.append("  dropped (week is behind): " + ", ".join(f"{s.sport.value} ({s.kind})" for s in plan.dropped_slots))
    return "\n".join(lines)


class ConsoleBrief(Output):
    name = "console_brief"

    def publish(self, brief: DailyBrief) -> None:
        print(format_brief(brief))
