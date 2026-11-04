"""Strava bulk-export collector (one-time historical import, read-only).

Reads activities.csv from the export folder inside data/raw/strava_export/.
Nothing under data/raw/ is modified. Track files (.fit.gz, .gpx) are not used yet.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from training_agent.collectors.base import Collector
from training_agent.core.models import Activity, DailyMetrics, Sport

ROOT = Path(__file__).resolve().parents[3]
EXPORT_BASE = ROOT / "data" / "raw" / "strava_export"
DATE_FORMAT = "%b %d, %Y, %I:%M:%S %p"  # Strava writes UTC
log = logging.getLogger(__name__)
csv.field_size_limit(10_000_000)


def _sport(strava_type: str) -> Sport:
    t = strava_type.lower()
    if "ride" in t:
        return Sport.BIKE
    if "run" in t:
        return Sport.RUN
    if any(x in t for x in ("weight", "workout", "strength", "crossfit")):
        return Sport.GYM
    return Sport.OTHER


def _num(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def parse_rows(rows: list[list[str]]) -> tuple[list[Activity], int]:
    """Convert activities.csv rows (header first) into Activities. Returns (activities, skipped)."""
    header = rows[0]
    positions: dict[str, list[int]] = defaultdict(list)  # the export repeats some column names
    for i, name in enumerate(header):
        positions[name].append(i)

    def get(row: list[str], name: str, last: bool = False) -> str | None:
        idx = positions.get(name, [])
        for i in ([idx[-1]] if last and idx else idx):
            if i < len(row) and row[i].strip():
                return row[i].strip()
        return None

    out: list[Activity] = []
    skipped = 0
    for row in rows[1:]:
        try:
            activity_id = get(row, "Activity ID")
            start = datetime.strptime(get(row, "Activity Date") or "", DATE_FORMAT)
            duration = _num(get(row, "Moving Time")) or _num(get(row, "Elapsed Time")) or 0.0
            distance = _num(get(row, "Distance", last=True))  # second copy is metres
            filename = get(row, "Filename")
            out.append(Activity(
                id=f"strava:{activity_id}",
                source="strava_export",
                sport=_sport(get(row, "Activity Type") or ""),
                source_sport=get(row, "Activity Type"),
                start_time=start,
                duration_s=duration,
                distance_m=distance or None,
                avg_hr=_num(get(row, "Average Heart Rate")),
                max_hr=_num(get(row, "Max Heart Rate")),
                relative_effort=_num(get(row, "Relative Effort")),
                perceived_exertion=_num(get(row, "Perceived Exertion")),
                perceived_relative_effort=_num(get(row, "Perceived Relative Effort")),
                avg_power_w=_num(get(row, "Average Watts")),
                elevation_gain_m=_num(get(row, "Elevation Gain")),
                raw_ref=filename,
            ))
        except (ValueError, TypeError):
            skipped += 1
    return out, skipped


class StravaExport(Collector):
    name = "strava_export"

    def __init__(self, export_base: Path = EXPORT_BASE):
        self._base = Path(export_base)

    def _activities_csv(self) -> Path | None:
        if not self._base.exists():
            return None
        folders = [self._base] + [p for p in sorted(self._base.iterdir()) if p.is_dir()]
        return next((f / "activities.csv" for f in folders if (f / "activities.csv").exists()), None)

    def collect_metrics(self, start: date, end: date) -> list[DailyMetrics]:
        return []  # the export has no daily health metrics

    def collect_activities(self, start: date, end: date) -> list[Activity]:
        path = self._activities_csv()
        if path is None:
            log.warning("No Strava export found under %s", self._base)
            return []
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        activities, skipped = parse_rows(rows)
        if skipped:
            log.warning("Skipped %d Strava rows that could not be read", skipped)
        return [a for a in activities if start <= a.start_time.date() <= end]
