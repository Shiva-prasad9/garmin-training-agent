# Project rules

1. Stages communicate only through the shared data models in `src/training_agent/core/models.py`. No stage imports another stage's internals.
2. New features are new plugin files, enabled in `config/features.yaml`. Do not edit core code to add a feature.
3. Never modify anything under `data/raw/`. Treat it as read-only source data.
4. Never read `.env` or `secrets/`. Use `.env.example` for the variable names.
5. Garmin data comes only from the official Personal API. No password scraping or unofficial libraries. Strava is bulk export only.
6. Golden-day tests (`tests/golden/`) must pass before every merge. Work on `feature/*` branches; `main` must always run.
7. Do not recompute Garmin metrics. The planner adds a judgment layer on top of them.

## Layout

- `config/`: configuration, including `features.yaml`
- `secrets/`: credentials (never read, never committed)
- `data/raw/garmin`, `data/raw/strava_export`: read-only raw data
- `data/db/`: local database
- `logs/`: runtime logs
- `src/training_agent/core/`: shared models and plugin loading
- `src/training_agent/collectors/`: data collection plugins
- `src/training_agent/storage/`: persistence
- `src/training_agent/planner/`: training plan generation (`rules/` holds rule plugins)
- `src/training_agent/outputs/`: delivery (email, calendar, files)
- `src/training_agent/web/`: local dashboard (FastAPI + static frontend); reads data via storage, adds panels as new files
- `scripts/`, `notebooks/`, `tests/`, `docs/`
