"""SQLite storage plugin. Database lives in data/db/ (gitignored).

Upserts keep re-runs safe. New features add new tables; existing tables and
data/raw/ are never rewritten.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from training_agent.core.activities import merge_duplicates
from training_agent.core.models import Activity, DailyMetrics, PlannedSession
from training_agent.storage.base import Repository

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "data" / "db" / "training.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_metrics (
    date TEXT PRIMARY KEY, source TEXT, sleep_hours REAL, sleep_score INTEGER,
    hrv_last_night_ms INTEGER, hrv_weekly_avg_ms INTEGER, hrv_status TEXT,
    resting_hr INTEGER, body_battery_morning INTEGER, body_battery_min INTEGER,
    body_battery_max INTEGER, stress_avg INTEGER, recovery_hours REAL
);
CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY, source TEXT, sport TEXT, source_sport TEXT,
    start_time TEXT, duration_s REAL, distance_m REAL, avg_hr REAL, max_hr REAL,
    training_load REAL, hr_zone_seconds TEXT, raw_ref TEXT,
    relative_effort REAL, perceived_exertion REAL, perceived_relative_effort REAL,
    avg_power_w REAL, elevation_gain_m REAL
);
CREATE TABLE IF NOT EXISTS planned_sessions (
    date TEXT, sport TEXT, intensity TEXT, title TEXT, rationale TEXT,
    duration_min INTEGER, rule_flags TEXT, PRIMARY KEY (date, sport, title)
);
"""

MIGRATIONS = {
    "activities": {"relative_effort": "REAL", "perceived_exertion": "REAL", "avg_power_w": "REAL",
                   "elevation_gain_m": "REAL", "perceived_relative_effort": "REAL"},
}


def _row(model) -> dict:
    row = {}
    for k, v in model.model_dump().items():
        if isinstance(v, Enum):
            v = v.value
        elif isinstance(v, (date, datetime)):
            v = v.isoformat()
        elif isinstance(v, list):
            v = json.dumps(v)
        row[k] = v
    return row


def _upsert(con: sqlite3.Connection, table: str, models: list) -> None:
    for m in models:
        row = _row(m)
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        con.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


class SqliteRepository(Repository):
    name = "sqlite"

    def __init__(self, path: Path = DB_PATH):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(SCHEMA)
            # Add columns introduced after a table was first created (data is never rewritten).
            for table, columns in MIGRATIONS.items():
                have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
                for name, kind in columns.items():
                    if name not in have:
                        con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._path)
        con.row_factory = sqlite3.Row
        return con

    def save_metrics(self, metrics: list[DailyMetrics]) -> None:
        with self._connect() as con:
            _upsert(con, "daily_metrics", metrics)

    def save_activities(self, activities: list[Activity]) -> None:
        with self._connect() as con:
            _upsert(con, "activities", activities)

    def save_plan(self, sessions: list[PlannedSession]) -> None:
        with self._connect() as con:
            _upsert(con, "planned_sessions", sessions)

    def get_metrics(self, start: date, end: date) -> list[DailyMetrics]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
                               (start.isoformat(), end.isoformat())).fetchall()
        return [DailyMetrics(**dict(r)) for r in rows]

    def get_activities(self, start: date, end: date, include_duplicates: bool = False) -> list[Activity]:
        """Stored workouts in the range. By default a workout present in several sources is returned once."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM activities WHERE date(start_time) BETWEEN ? AND ? ORDER BY start_time",
                (start.isoformat(), end.isoformat())).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["hr_zone_seconds"] = json.loads(d["hr_zone_seconds"]) if d["hr_zone_seconds"] else None
            out.append(Activity(**d))
        return out if include_duplicates else merge_duplicates(out)
