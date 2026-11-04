"""Single entry point for one daily run: collect -> store -> plan -> publish.

    .venv/bin/python main.py                 # refresh the last 3 days from Garmin, plan today, print the brief
    .venv/bin/python main.py --no-collect    # plan from stored data only (no network)
    .venv/bin/python main.py --days 7        # refresh a longer window
    .venv/bin/python main.py --day 2026-11-01   # plan a past day

Each stage comes from config/features.yaml. A run is safe to repeat. Log: logs/daily_run.log.
"""
import argparse
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from training_agent.pipeline import run_daily  # noqa: E402


def setup_logging() -> None:
    (ROOT / "logs").mkdir(exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(message)s"))
    logfile = logging.FileHandler(ROOT / "logs" / "daily_run.log")
    logfile.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.handlers[:] = [console, logfile]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the daily training agent cycle.")
    parser.add_argument("--days", type=int, default=3, help="how many days to refresh from the sources (default 3)")
    parser.add_argument("--day", type=date.fromisoformat, default=None, help="plan this day instead of today (YYYY-MM-DD)")
    parser.add_argument("--no-collect", action="store_true", help="skip fetching and plan from stored data")
    args = parser.parse_args(argv)
    setup_logging()
    try:
        run_daily(day=args.day, days=args.days, collect=not args.no_collect)
    except RuntimeError as e:
        print(f"Cannot run: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
