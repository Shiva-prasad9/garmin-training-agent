# Decision log

Format: ID, date, decision, reason. Append new entries; do not rewrite old ones (supersede instead).

## D001 (2026-11-01): Judgment layer, not metric recomputation
The agent consumes Garmin's metrics as-is and decides what to do with them. Reason: Garmin's physiology models are better than anything built here; the value is in the decision.

## D002 (2026-11-01): Garmin via official Personal API only
Pull-only, API key + token, JSON and .FIT. No password scraping, no unofficial libraries. Reason: stability, account safety, terms of service.

## D003 (2026-11-01): Strava via bulk export only
Historical backfill from the export archive, not the Strava API. Reason: avoids API limits and OAuth for a one-time import.

## D004 (2026-11-01): Pipeline of stages communicating via data contracts
collect → store → plan → publish; stages exchange only the models in `core/models.py`. Reason: modularity is the top requirement; stages stay swappable and testable.

## D005 (2026-11-01): Plugin architecture driven by `config/features.yaml`
Each feature is one plugin file implementing a stage base class, enabled by one config line. Reason: add features without editing existing code.

## D006 (2026-11-01): Planner = deterministic rules + LLM within limits
Rules are hard guardrails (readiness-gated intensity, hard/easy alternation, weekly load limit). The LLM reasons inside them and explains the choice; it cannot override a guardrail. Reason: safety and explainability; mirrors a controller with limits.

## D007 (2026-11-01): SQLite storage, raw data immutable
SQLite in `data/db/`. `data/raw/` is never modified; features add tables and never rewrite raw data. Reason: reproducibility and simple local deployment.

## D008 (2026-11-01): Golden-day tests
Fixed metric scenarios with expected outcomes in `tests/golden/`, run before every merge. Reason: regression protection for planner behaviour.

## D009 (2026-11-01): Git workflow
Private GitHub repo; work on `feature/*` branches; `main` always runs.

## D010 (2026-11-01): Secrets handling
Secrets live only in `.env` and `secrets/`, are gitignored, and are denied for Read in `.claude/settings.json`. `.env.example` lists names only.

## D011 (2026-11-01): Linux-portable, path-independent
Target WSL now, an always-on host (e.g. Raspberry Pi) later. No hard-coded absolute paths.

## D012 (2026-11-01): Single entry point
`main.py` runs one daily cycle; scheduling is added later (Phase 7).

## D013 (2026-11-01): Local dashboard, Solo Leveling-inspired theme
FastAPI serves one JSON endpoint plus a static page (plain HTML/CSS/JS, hand-written SVG charts, no build step). Each panel is one JS file listed in `static/js/panels/index.js`. Default range 10 days, options 7/14. Light lavender background with deep indigo highlights, dark toggle. Original CSS/SVG styling only, no copied artwork. Binds to 127.0.0.1 unless `--lan` is given (no login).
Exception noted: the web layer calls `planner.baselines.assess` (a pure, public function) to get assessments; if more consumers need it, move it to a shared analysis module.
