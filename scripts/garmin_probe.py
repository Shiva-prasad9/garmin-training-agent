"""Probe the Garmin Personal API and print the SHAPE of each response.

Prints field names and types only, never values, the key or the token.
Used to decide which fields the collector and DailyMetrics can rely on.

Usage (from the project folder):
    python3 -I scripts/garmin_probe.py [YYYY-MM-DD]
Default date: yesterday.
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HOST = "https://personal.connectapi.garmin.com"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_key() -> str:
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("GARMIN_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("GARMIN_API_KEY not found in .env")


def request(path, headers, method="GET"):
    req = urllib.request.Request(HOST + path, headers=headers, method=method,
                                 data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return type(e).__name__, b""


def shape(obj, depth=0, max_depth=2):
    """Describe structure without values."""
    if isinstance(obj, dict):
        if depth >= max_depth:
            return f"dict({len(obj)} keys)"
        return {k: shape(v, depth + 1, max_depth) for k, v in obj.items()}
    if isinstance(obj, list):
        if not obj:
            return "list(empty)"
        return [f"list({len(obj)})", shape(obj[0], depth + 1, max_depth)]
    return type(obj).__name__ if obj is not None else "null"


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=1)).isoformat()
    status, body = request("/personalapitoken-service/personal-api/personal-api-key/token",
                           {"Authorization": f"ApiKey {load_key()}"}, "POST")
    if status != 200:
        raise SystemExit(f"token exchange failed: {status}")
    auth = {"Authorization": f"Bearer {body.decode().strip().strip(chr(34))}"}

    endpoints = {
        "daily summary": f"/usersummary-service/v2/dailysummaries?startDate={day}&endDate={day}",
        "sleep": f"/sleep-service/sleep/dailySleep?date={day}",
        "hrv": f"/hrv-service/hrv/{day}",
        "body battery": f"/wellness-service/wellness/bodyBattery/reports/daily?startDate={day}&endDate={day}",
        "activities": "/activitylist-service/activities/search/activities?start=0&limit=3",
    }
    print(f"date: {day}")
    for name, path in endpoints.items():
        status, body = request(path, auth)
        print(f"\n== {name}: status {status}")
        if status == 200:
            try:
                depth = 4 if name == "daily summary" else 2
                print(json.dumps(shape(json.loads(body), max_depth=depth), indent=2))
            except Exception:
                print(f"(not JSON, {len(body)} bytes)")


if __name__ == "__main__":
    main()
