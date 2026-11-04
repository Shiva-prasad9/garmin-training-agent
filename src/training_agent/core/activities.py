"""Pure helpers on lists of Activity (no I/O)."""

from __future__ import annotations

from training_agent.core.models import Activity

# Fields a lower-priority copy may contribute when the preferred copy lacks them.
_FILL = ("relative_effort", "perceived_exertion", "perceived_relative_effort", "avg_power_w", "elevation_gain_m",
         "avg_hr", "max_hr", "distance_m", "training_load", "hr_zone_seconds")


def _rank(a: Activity) -> int:
    return 0 if a.source == "garmin" else 1  # Garmin is the preferred record


def merge_duplicates(activities: list[Activity], tolerance_s: float = 180) -> list[Activity]:
    """Return each real-world workout once.

    Two activities from different sources that start within `tolerance_s` seconds
    are the same workout. The Garmin copy is kept; fields it lacks (for example
    Strava's relative effort and perceived exertion) are copied onto it.
    """
    kept: list[Activity] = []
    for a in sorted(activities, key=lambda x: x.start_time):
        twin_i = next((i for i in range(len(kept) - 1, -1, -1)
                       if abs((a.start_time - kept[i].start_time).total_seconds()) <= tolerance_s
                       and kept[i].source != a.source), None)
        if twin_i is None:
            kept.append(a)
            continue
        twin = kept[twin_i]
        keep, drop = (a, twin) if _rank(a) < _rank(twin) else (twin, a)
        extra = {f: getattr(drop, f) for f in _FILL
                 if getattr(keep, f) is None and getattr(drop, f) is not None}
        kept[twin_i] = keep.model_copy(update=extra)
    return kept
