"""Describe the Strava export: file names, activities.csv columns, counts. No values are printed.

Usage (from anywhere):
    python3 -I scripts/strava_probe.py
Finds the export folder inside data/raw/strava_export/ by itself.
"""
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "raw" / "strava_export"
csv.field_size_limit(10_000_000)


def find_export() -> Path:
    candidates = [p for p in BASE.iterdir() if p.is_dir()] or [BASE]
    for c in candidates:
        if (c / "activities.csv").exists():
            return c
    raise SystemExit(f"activities.csv not found under {BASE}")


def parse_date(s: str):
    for fmt in ("%b %d, %Y, %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def main() -> None:
    root = find_export()
    print("export folder:", root.name)
    print("\n== top-level contents")
    for p in sorted(root.iterdir()):
        if p.is_dir():
            kinds = Counter("".join(f.suffixes) or "(none)" for f in p.iterdir() if f.is_file())
            print(f"  {p.name}/  {sum(kinds.values())} files  {dict(kinds)}")
        else:
            print(f"  {p.name}  {p.stat().st_size:,} bytes")

    with open(root / "activities.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    print(f"\n== activities.csv: {len(data)} rows, {len(header)} columns")
    print("(column index, name, how many rows have a value)")
    for i, name in enumerate(header):
        filled = sum(1 for r in data if i < len(r) and r[i].strip() != "")
        print(f"  [{i:2d}] {name}: {filled}/{len(data)}")

    for name in ("Activity Type", "Activity Gear"):
        if name in header:
            i = header.index(name)
            print(f"\n== {name} (counts)")
            for k, v in Counter(r[i] for r in data if i < len(r)).most_common(12):
                print(f"  {k or '(empty)'}: {v}")

    if "Activity Date" in header:
        i = header.index("Activity Date")
        dates = [d for d in (parse_date(r[i]) for r in data if i < len(r)) if d]
        if dates:
            print(f"\n== date range: {min(dates):%Y-%m-%d} to {max(dates):%Y-%m-%d} ({len(dates)} parsed)")
            years = Counter(d.year for d in dates)
            print("  per year:", dict(sorted(years.items())))


if __name__ == "__main__":
    main()
