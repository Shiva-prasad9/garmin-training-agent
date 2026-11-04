# Garmin Training Agent

A personal training agent that runs on a local network. It collects Garmin health data (plus Strava history), decides how hard to train each day based on recovery, and publishes the plan to Google Calendar and email.

It does **not** recompute Garmin's metrics. It adds a judgment layer on top. Example: Garmin says "recovery 30 h", but an easy Z1-Z2 spin is still fine; only intensity is restricted.

## Control-loop view

| Control concept | This project |
|---|---|
| Reference trajectory | Training plan / periodization |
| Sensors | Garmin metrics: sleep, HRV, Body Battery, resting HR, training load |
| Controller | Rules (hard guardrails) + LLM (reasoning within the guardrails) |
| Plant | The athlete; the loop closes when the watch syncs the next day |

## Architecture

Pipeline: **collect → store → plan → publish**.

1. `collectors/`: pull data (Garmin Personal API, Strava bulk export)
2. `storage/`: persist to SQLite in `data/db/`
3. `planner/`: deterministic rules (readiness-gated intensity, hard/easy alternation, weekly load limit) plus an LLM agent that explains its choice within those limits
4. `outputs/`: Google Calendar events and a daily email brief

Stages communicate only through the data contracts in `src/training_agent/core/models.py`. Every feature is a plugin file implementing a stage's base class; `config/features.yaml` enables or disables plugins. A new feature is one new file plus one config line.

Raw data in `data/raw/` is never modified.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
cp .env.example .env   # then fill in your keys
```

### Daily use

```bash
.venv/bin/python main.py                # refresh the last 3 days from Garmin, plan today, print the brief
.venv/bin/python main.py --no-collect   # plan from stored data only (no network)
.venv/bin/python scripts/serve.py       # the dashboard at http://127.0.0.1:8000 (choose a session, log gym)
```

Other scripts: `scripts/backfill.py --days 90` (longer Garmin history), `scripts/import_strava.py` (one-time Strava archive).
Tests: `PYTHONPATH=src .venv/bin/python -m pytest -q` (includes the golden days in `tests/golden/`).

## Workflow

Work on `feature/*` branches; `main` must always run. Golden-day tests in `tests/golden/` run before every merge.

## Docs

- Project rules: [CLAUDE.md](CLAUDE.md)
- Vision: [docs/vision.md](docs/vision.md)
- Decisions: [docs/decisions.md](docs/decisions.md)
- Roadmap: [docs/roadmap.md](docs/roadmap.md)
