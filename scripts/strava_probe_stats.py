"""Summary statistics of the Strava export (no individual workouts, no routes).

Prints, per activity type: how many workouts have each effort-related field, and
min/median/max of a few numeric columns. Also checks the unit of the duplicate
columns and how many Strava workouts match a Garmin workout already in the database.

Usage (from anywhere):
    python3 -I scripts/strava_probe_stats.py
"""
import csv
import sqlite3
import statistics as st
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "raw" / "strava_export"
DB = ROOT / "data" / "db" / "training.sqlite"
csv.field_size_limit(10_000_000)

# column index -> short name (indexes from strava_probe.py output)
COLS = {5: "elapsed_a", 15: "elapsed_b", 16: "moving", 6: "dist_a", 17: "dist_b", 19: "avg_speed",
        31: "avg_hr", 8: "rel_effort", 43: "perceived", 33: "avg_watts", 88: "train_load", 89: "intensity"}


def num(s):
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def summary(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "-"
    return f"n={len(vals)} min {min(vals):.1f} med {st.median(vals):.1f} max {max(vals):.1f}"


def parse_date(s):
    for fmt in ("%b %d, %Y, %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def main():
    root = next(p for p in BASE.iterdir() if (p / "activities.csv").exists())
    with open(root / "activities.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))[1:]

    by_type = defaultdict(list)
    for r in rows:
        by_type[r[3]].append(r)

    for t, rs in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        print(f"\n== {t}: {len(rs)} workouts")
        for i, name in COLS.items():
            print(f"  {name:11s} {summary([num(r[i]) for r in rs])}")

    print("\n== unit checks (ratios of duplicate columns, median)")
    for a, b, label in ((6, 17, "dist_b / dist_a"), (5, 15, "elapsed_b / elapsed_a")):
        ratios = [num(r[b]) / num(r[a]) for r in rows if num(r[a]) and num(r[b])]
        print(f"  {label}: {st.median(ratios):.3f}" if ratios else f"  {label}: n/a")

    print("\n== overlap with Garmin workouts already in the database (start within 3 min)")
    if not DB.exists():
        print("  database not found")
        return
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    garmin = [datetime.fromisoformat(s[0]) for s in con.execute("SELECT start_time FROM activities")]
    if garmin:
        lo, hi = min(garmin) - timedelta(minutes=3), max(garmin) + timedelta(minutes=3)
        in_range = [parse_date(r[1]) for r in rows]
        in_range = [d for d in in_range if d and lo <= d <= hi]
        matched = sum(1 for d in in_range if any(abs((d - g).total_seconds()) <= 180 for g in garmin))
        print(f"  Garmin workouts in database: {len(garmin)} ({min(garmin):%Y-%m-%d} to {max(garmin):%Y-%m-%d})")
        print(f"  Strava workouts in that period: {len(in_range)}, of which matched to a Garmin workout: {matched}")


if __name__ == "__main__":
    main()
