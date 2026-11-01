# Vision

A personal training agent that runs on my local network. It collects my Garmin health data (plus Strava history), decides how hard I should train each day based on my recovery, and publishes the plan to Google Calendar and email. It does NOT recompute Garmin's metrics; it adds a judgment layer on top. Example: Garmin says "recovery 30 h", but light activity (easy Z1-Z2 spin) is still fine; only intensity is restricted.

I'm a controls engineer, trying to understand how an agent works by building my own AI agent for training:

- Reference trajectory = training plan / periodization
- Sensors = Garmin metrics (sleep, HRV, Body Battery, resting HR, training load)
- Controller = rules (hard guardrails) + LLM (reasoning within those guardrails)
- Plant = me; the loop closes when the watch syncs the next day

## Data sources

- Garmin Connect **Personal API** (official, API key + token, pull-only, JSON + .FIT). No password scraping, no unofficial libraries.
- Strava: **bulk export archive** only, for historical backfill (not the Strava API).
- Current weekly template (to be refined later): 1 run (10k), 2 bike (short + long), 3 gym, 1 rest day. Some bike rides are recorded on a Sigma ROX 4.0 without HR.

## Outputs

- Google Calendar events for planned sessions (OAuth desktop client)
- Daily email brief: today's session, intensity, and the reason for it

## Architecture (modular: the most important requirement)

Pipeline: collect → store → plan → publish. Stages communicate ONLY via data contracts in `src/training_agent/core/models.py` (e.g. DailyMetrics, Activity, PlannedSession).

- Each stage has a base class; every feature is a plugin file implementing it (collectors/, planner/rules/, outputs/).
- `config/features.yaml` enables/disables plugins. A new feature = one new file + one config line, without editing existing plugins.
- Planner = deterministic rules (readiness-gated intensity, hard/easy alternation, weekly load limit) + LLM agent that reasons within those limits and explains its choice.
- Storage: SQLite in data/db/. Raw data in data/raw/ is never modified; new features add tables, never rewrite raw data.
- "Golden day" tests in tests/: fixed metric scenarios with expected outcomes, run before every merge.
- Single entry point `main.py` for one daily run; scheduling comes later.

## Environment

- WSL Ubuntu 24.04, Python 3.12, venv in .venv/
- Later: move to an always-on home host (e.g. Raspberry Pi). Keep everything Linux-compatible and path-independent.
- GitHub: private repo https://github.com/Shiva-prasad9/garmin-training-agent.git. Work on feature/* branches; main must always run.

## Security rules

- Secrets only in .env and secrets/. Never read, print, or commit them. `.env.example` has variable names only (GARMIN_API_KEY, ANTHROPIC_API_KEY, GOOGLE_CALENDAR_ID, EMAIL_TO).
- .gitignore: .venv/, .env, secrets/, data/, logs/, __pycache__/, *.sqlite
- `.claude/settings.json` denies Read on .env, secrets/** and data/raw/**.

See [roadmap.md](roadmap.md) for the build phases.
