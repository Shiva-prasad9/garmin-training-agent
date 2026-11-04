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

## D014 (2026-11-04): Strava data is for the agent, not the dashboard
The Strava export is imported and stored so the agent can learn past efforts, baselines and session targets. The dashboard shows Garmin workouts only; it never lists Strava workouts or Strava relative effort.

## D015 (2026-11-04): Effort scale and no-HR rides
Garmin load is the planner's effort scale. Strava Relative Effort is converted with load = 1.42 x RE (median error ~20%). Rides without heart rate use duration x the athlete's typical ride load per minute, adjusted by perceived exertion when present, and are flagged as estimates. Strava's estimated watts are not used (they do not track HR-based effort).

## D016 (2026-11-04): Effort sources, in order (refines D015)
1. Garmin load when a heart-rate recording exists. 2. Strava Relative Effort x 1.42. 3. Strava Perceived Relative Effort (computed by Strava from the athlete's 1-10 rating, used when there is no HR) x 1.42, flagged rough (about a factor of 2; consistent across ratings 3-7, overshoots at 10). 4. Duration x the athlete's typical load per minute for the sport, flagged as an estimate (54 older rides have no rating). Strava's estimated watts are not used.

## D017 (2026-11-04): Weekly load compared with an 8-week average
The weekly load limit compares the last 7 days with the average week over the 8 weeks before (fewer while history is short). Four weeks was too jumpy for lumpy training (it kept the limit on for days). Chosen by the athlete after the first real-data run; all rule thresholds are expected to be tuned after the first trial period.

## D018 (2026-11-04): Keep sports and plans open to extension
The weekly template is configuration only (`config/athlete.yaml`). A week plan source (template today, event plan later) answers "what should this week contain", so an event overrides the template without editing core code. Adding a sport such as swimming is a documented checklist (`docs/extending.md`); not done yet by choice.

## D019 (2026-11-04): The athlete decides; writes stay local
Every option the planner offers can be chosen; labels and warnings inform but never block. A choice above the cap is stored as an override together with the recommendation, so later analysis can check how overrides turned out. The dashboard accepts changes only from the computer it runs on (no login). The web layer calls the planner through its plugin loader and `build_context`; this is the second documented exception to "no stage imports another's internals".
