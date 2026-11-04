"""Collect Garmin data for the last N days and store it in SQLite.

Usage (from anywhere):
    .venv/bin/python scripts/backfill.py --days 14
    .venv/bin/python scripts/backfill.py --days 90
    .venv/bin/python scripts/backfill.py --days 90 --details   # also routes and per-sample detail

Plugins come from config/features.yaml, so this script never names them.
Safe to re-run: stored rows are updated, raw files are only added.
"""
import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from training_agent.core.plugin import load_enabled_plugins  # noqa: E402
from training_agent.pipeline import fetch_missing_details  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--details", action="store_true", help="also download route and per-sample detail of each workout")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    config = ROOT / "config" / "features.yaml"
    collectors = load_enabled_plugins(config, "collectors")
    repos = load_enabled_plugins(config, "storage")
    if not collectors or not repos:
        raise SystemExit("Enable a collector and a storage plugin in config/features.yaml")
    repo = repos[0]

    end = date.today()
    start = end - timedelta(days=args.days - 1)
    for c in collectors:
        print(f"[{c.name}] {start} -> {end}")
        metrics = c.collect_metrics(start, end)
        print(f"  daily metrics: {len(metrics)} days with data")
        repo.save_metrics(metrics)
        activities = c.collect_activities(start, end)
        print(f"  activities: {len(activities)}")
        repo.save_activities(activities)
    if args.details:
        added = fetch_missing_details(collectors, repo, repo.get_activities(start, end))
        print(f"activity details downloaded: {added}")
    print("done")


if __name__ == "__main__":
    main()
