"""First-run setup for a new person: key -> history -> today's plan.

    .venv/bin/python scripts/setup.py

Asks for your Garmin Personal API key (typing is hidden) and saves it to .env, which git ignores.
Then loads 90 days of your Garmin history and prints today's plan. Safe to re-run.
Your numbers (baselines, typical sessions) are learned from your own data; nothing is preset.
"""
import getpass
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
ATHLETE = ROOT / "config" / "athlete.yaml"
PY = sys.executable


def has_key() -> bool:
    if not ENV.exists():
        return False
    return any(line.startswith("GARMIN_API_KEY=") and line.strip() != "GARMIN_API_KEY=" for line in ENV.read_text().splitlines())


def save_key(key: str) -> None:
    lines = [l for l in (ENV.read_text().splitlines() if ENV.exists() else []) if not l.startswith("GARMIN_API_KEY=")]
    ENV.write_text("\n".join(lines + [f"GARMIN_API_KEY={key}"]) + "\n")
    ENV.chmod(0o600)


def set_max_hr(value: int) -> None:
    text = ATHLETE.read_text()
    ATHLETE.write_text(re.sub(r"^max_hr:\s*\d+", f"max_hr: {value}", text, count=1, flags=re.M))


def main() -> int:
    print("Garmin training agent: first-run setup\n")
    if has_key():
        print("A Garmin key is already saved in .env, keeping it.")
    else:
        key = getpass.getpass("Paste your Garmin Personal API key (hidden): ").strip()
        if not key:
            print("No key entered, stopping.")
            return 1
        save_key(key)
        print("Saved to .env (not tracked by git).")

    answer = input("Your max heart rate in bpm (Enter to keep the default in config/athlete.yaml): ").strip()
    if answer.isdigit() and 120 <= int(answer) <= 230:
        set_max_hr(int(answer))
        print(f"max_hr set to {answer}.")

    print("\nLoading 90 days of Garmin history (a minute or two)...")
    if subprocess.call([PY, str(ROOT / "scripts" / "backfill.py"), "--days", "90"]) != 0:
        print("History load failed. Check the key and try again.")
        return 1
    print("\nToday's plan:\n")
    return subprocess.call([PY, str(ROOT / "main.py"), "--no-collect"])


if __name__ == "__main__":
    sys.exit(main())
