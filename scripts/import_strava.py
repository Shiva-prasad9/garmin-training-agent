"""Import the Strava bulk export into the database (one-time backfill, safe to re-run).

Usage:
    .venv/bin/python scripts/import_strava.py

Reads data/raw/strava_export/<export folder>/activities.csv (read-only).
Both Strava and Garmin rows are stored; duplicates are merged when workouts are read back.
"""
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from training_agent.core.plugin import load_enabled_plugins  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = ROOT / "config" / "features.yaml"
    collectors = [c for c in load_enabled_plugins(config, "collectors") if c.name == "strava_export"]
    repos = load_enabled_plugins(config, "storage")
    if not collectors or not repos:
        raise SystemExit("Enable strava_export (collectors) and a storage plugin in config/features.yaml")

    activities = collectors[0].collect_activities(date(2000, 1, 1), date(2100, 1, 1))
    repos[0].save_activities(activities)
    print(f"imported {len(activities)} Strava workouts")
    for sport, n in Counter(a.sport.value for a in activities).most_common():
        print(f"  {sport}: {n}")
    print("done")


if __name__ == "__main__":
    main()
