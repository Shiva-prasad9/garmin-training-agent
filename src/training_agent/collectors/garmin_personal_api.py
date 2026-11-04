"""Garmin Personal API collector (pull-only).

Fetches one day at a time, saves every raw JSON response under
data/raw/garmin/<endpoint>/ (new files only, existing files are never
changed), and converts the responses into the shared models.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from training_agent.collectors.base import Collector
from training_agent.core.models import Activity, DailyMetrics, Sport

HOST = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw" / "garmin"
log = logging.getLogger(__name__)


# ---------- parsing (pure functions, easy to test) ----------

def _dig(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _sport(type_key: str | None) -> Sport:
    k = (type_key or "").lower()
    if "run" in k:
        return Sport.RUN
    if any(x in k for x in ("cycl", "bik", "ride")):
        return Sport.BIKE
    if any(x in k for x in ("strength", "gym", "fitness_equipment")):
        return Sport.GYM
    return Sport.OTHER


def parse_metrics(day: date, sleep, hrv, battery, summary) -> DailyMetrics | None:
    """Combine the four daily responses into one DailyMetrics (None if no data)."""
    rows = _dig(summary, "data")
    s = rows[0] if isinstance(rows, list) and rows else {}

    morning = None
    if isinstance(battery, list) and battery and isinstance(battery[0], dict):
        readings = [p for p in battery[0].get("bodyBatteryValuesArray") or [] if len(p) > 1 and p[1] is not None]
        if readings:
            # Readings are [timestamp_ms, level]. Body Battery peaks at wake-up, so take the
            # highest level up to 1 h after waking (fallback: first 12 h of the day).
            wake_ms = _dig(sleep, "sleepEndTimestampGMT")
            cutoff = wake_ms + 3_600_000 if wake_ms else readings[0][0] + 12 * 3_600_000
            window = [p[1] for p in readings if p[0] <= cutoff]
            morning = max(window) if window else None

    sleep_s = _dig(sleep, "sleepTimeSeconds")
    m = DailyMetrics(
        date=day,
        sleep_hours=round(sleep_s / 3600, 2) if sleep_s else None,
        sleep_score=_dig(sleep, "sleepScores", "overall", "value"),
        hrv_last_night_ms=_dig(hrv, "hrvSummary", "lastNightAvg"),
        hrv_weekly_avg_ms=_dig(hrv, "hrvSummary", "weeklyAvg"),
        hrv_status=_dig(hrv, "hrvSummary", "status"),
        resting_hr=_dig(s, "heartRate", "restingValue"),
        body_battery_morning=morning,
        body_battery_min=_dig(s, "bodyBattery", "minValue"),
        body_battery_max=_dig(s, "bodyBattery", "maxValue"),
        stress_avg=_dig(s, "stress", "avgLevel"),
    )
    if all(v is None for k, v in m.model_dump().items() if k not in ("date", "source")):
        return None
    return m


def parse_activity(a: dict) -> Activity:
    zones = [a.get(f"hrTimeInZone_{i}") for i in range(1, 6)]
    type_key = _dig(a, "activityType", "typeKey")
    return Activity(
        id=f"garmin:{a['activityId']}",
        source="garmin",
        sport=_sport(type_key),
        source_sport=type_key,
        start_time=datetime.fromisoformat(a["startTimeGMT"].replace(" ", "T")),
        duration_s=a.get("duration") or 0.0,
        distance_m=a.get("distance"),
        avg_hr=a.get("averageHR"),
        max_hr=a.get("maxHR"),
        training_load=a.get("activityTrainingLoad"),
        elevation_gain_m=a.get("elevationGain"),
        hr_zone_seconds=None if all(z is None for z in zones) else [z or 0.0 for z in zones],
        raw_ref=f"activities/{a['activityId']}",
    )


# ---------- collector plugin ----------

class GarminPersonalApi(Collector):
    name = "garmin_personal_api"

    def __init__(self, raw_dir: Path = RAW_DIR, pause_s: float = 0.25):
        load_dotenv(ROOT / ".env")
        self._key = os.environ.get("GARMIN_API_KEY", "")
        self._raw_dir = Path(raw_dir)
        self._pause_s = pause_s
        self._token: str | None = None
        self._token_expiry = 0.0

    # --- HTTP ---
    def _request(self, method: str, path: str, headers: dict) -> tuple[int, bytes]:
        req = urllib.request.Request(HOST + path, headers=headers, method=method,
                                     data=b"" if method == "POST" else None)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(2 ** attempt * 2)
                    continue
                return e.code, b""
            except urllib.error.URLError:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return 0, b""

    def _auth(self) -> dict:
        if not self._key:
            raise RuntimeError("GARMIN_API_KEY missing in .env")
        if self._token is None or time.time() > self._token_expiry:
            status, body = self._request("POST", TOKEN_PATH, {"Authorization": f"ApiKey {self._key}"})
            if status != 200:
                raise RuntimeError(f"Garmin token exchange failed (HTTP {status})")
            self._token = body.decode().strip().strip('"')
            self._token_expiry = time.time() + 23 * 3600
        return {"Authorization": f"Bearer {self._token}"}

    def _get_json(self, path: str):
        status, body = self._request("GET", path, self._auth())
        if status == 401:  # token expired early: refresh once
            self._token = None
            status, body = self._request("GET", path, self._auth())
        if status in (204, 404) or not body:
            return None
        if status != 200:
            log.warning("GET %s -> HTTP %s", path.split("?")[0], status)
            return None
        time.sleep(self._pause_s)
        return json.loads(body)

    def _cached(self, endpoint: str, name: str, path: str, settled: bool):
        """Return JSON for `path`, using/creating data/raw/garmin/<endpoint>/<name>.json.

        Only settled (older) days are cached, since recent days may still change.
        """
        file = self._raw_dir / endpoint / f"{name}.json"
        if file.exists():
            return json.loads(file.read_text())
        data = self._get_json(path)
        if data is not None and settled:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(data))
        return data

    # --- Collector interface ---
    def collect_metrics(self, start: date, end: date) -> list[DailyMetrics]:
        out: list[DailyMetrics] = []
        day = start
        while day <= end:
            d = day.isoformat()
            settled = day < date.today() - timedelta(days=2)
            sleep = self._cached("sleep", d, f"/sleep-service/sleep/dailySleep?date={d}", settled)
            hrv = self._cached("hrv", d, f"/hrv-service/hrv/{d}", settled)
            battery = self._cached(
                "body_battery", d,
                f"/wellness-service/wellness/bodyBattery/reports/daily?startDate={d}&endDate={d}", settled)
            summary = self._cached(
                "daily_summary", d,
                f"/usersummary-service/v2/dailysummaries?startDate={d}&endDate={d}", settled)
            m = parse_metrics(day, sleep, hrv, battery, summary)
            if m:
                out.append(m)
            day += timedelta(days=1)
        return out

    def collect_activities(self, start: date, end: date) -> list[Activity]:
        out: list[Activity] = []
        limit, offset = 100, 0
        settled = end < date.today() - timedelta(days=2)
        while True:
            path = (f"/activitylist-service/activities/search/activities?start={offset}&limit={limit}"
                    f"&startDate={start.isoformat()}&endDate={end.isoformat()}")
            page = self._cached("activities", f"{start}_{end}_{offset}", path, settled) or []
            out.extend(parse_activity(a) for a in page)
            if len(page) < limit:
                return out
            offset += limit
