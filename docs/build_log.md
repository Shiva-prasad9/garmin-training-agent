# Build log

Step-by-step record of what we did and why. Source for the final PDF/Word document.

## Phase 1: Skeleton

### Step 1: Plan and folder structure (2026-11-01)
- Wrote the plan, then created the folders, docs, config files and stub code.
- Why: folders and contracts come first so every later feature has a place to plug in.

### Step 2: Premature commit undone (2026-11-01)
- A local commit was made before review, and a push to GitHub failed (no credentials).
- Undid the commit; files are kept and staged. Rule from now on: no commit or push until the user is satisfied.

### Step 3: Working agreement (2026-11-01)
- Claude decides technical details; the user interrupts if something needs attention.
- Explanations stay short and simple. Everything stays modular (new feature = new plugin file + one config line).
- Decision: keep `core/models.py` as docstring stubs during review, convert to typed pydantic fields after approval.

### Step 4: Goal clarified (2026-11-01)
- Ultimate goal: enter an event (e.g. marathon in 5 months) and the agent estimates and plans training toward it, tracking progress.
- First milestone: read Garmin data and store it; improve from there. Added as Phase 8 in the roadmap.

### Step 5: Garmin API access verified (2026-11-01)
- Created a personal API key (Garmin Connect settings). Stored only in `.env` (a first key was pasted into chat by mistake and revoked).
- Auth flow confirmed: POST key to `personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token` with `Authorization: ApiKey <key>` returns a plain-text token; data calls use `Authorization: Bearer <token>`. Token lifetime 24 h.
- Verified: token exchange 200, profile settings 200.
- Lesson: `.env.` (typo with trailing dot) is not ignored by git; always check the filename.

### Step 6: Probed Garmin data and finalized models (2026-11-01)
- `scripts/garmin_probe.py` prints field names/types only (no values). Sleep, HRV, Body Battery, daily summary and activities all reachable with the personal key.
- Mapping: sleep_hours from `sleepTimeSeconds`; sleep_score from `sleepScores.overall`; HRV from `hrvSummary`; resting_hr from `heartRate.restingValue`; Body Battery from `bodyBatteryValuesArray`; activity load from `activityTrainingLoad`; zones from `hrTimeInZone_1..5`.
- Not exposed: Garmin recovery hours and 7-day load. Decision: `recovery_hours` stays optional/empty; 7-day load = sum of per-activity `activityTrainingLoad` (aggregation, not recomputation).
- `core/models.py` converted from docstring stubs to typed pydantic models. All uncertain signals are Optional so gaps never break the pipeline.

### Step 7: Collector, storage, backfill, notebook (2026-11-01)
- Plugin loader implemented in `core/plugin.py` (reads `config/features.yaml`, imports enabled plugins).
- `collectors/garmin_personal_api.py`: day-by-day fetch, caches each raw JSON response as a new file under `data/raw/garmin/<endpoint>/` (never overwritten), parses into `DailyMetrics` / `Activity`. Retries on 429/5xx, refreshes token.
- `storage/sqlite.py`: tables `daily_metrics`, `activities`, `planned_sessions`; upserts so re-runs are safe.
- `scripts/backfill.py --days N`: wires enabled collector + storage from config.
- `notebooks/01_explore_garmin.ipynb`: coverage, sleep, HRV, resting HR, Body Battery, weekly load, HR availability.
- `tests/test_garmin_storage.py`: 4 tests with fake payloads, passing.
- Plugins `garmin_personal_api` and `sqlite` enabled in `features.yaml`.
- Idea logged: web UI as roadmap Phase 9.

### Step 8: Body Battery fix (2026-11-01)
- Checked stored data against Garmin Connect screenshot: sleep, run and ride values matched; weekly activity total matched (5:41).
- Bug: `body_battery_morning` used the first reading of the day (a midnight value). Raw readings are sparse `[timestamp_ms, level]` pairs; the wake-up value is the peak up to 1 h after sleep end. Fixed in `parse_metrics`, test added. Re-run backfill (cached raw files, no extra API load) to correct stored rows.

### Step 9: Personal baselines and data-quality flags (2026-11-01)
- Charts reviewed: data good; found short nights (~0.6 h, ~1.8 h) and an HRV spike (~106 ms) from partial recordings, and a slow HRV decline since early October.
- New contract models `SignalAssessment`, `DailyAssessment` in `core/models.py`.
- `planner/baselines.py`: baseline = median of the previous 28 valid days, spread = scaled MAD (robust), z-score per signal. Flags: missing_sleep, short_sleep (<3 h), missing_hrv, hrv_outlier (|z|>4), insufficient_baseline. Short nights are excluded from sleep/HRV baselines. Thresholds in `config/rules.yaml`.
- Tests: `tests/test_baselines.py` (6 tests, synthetic series). Notebook sections 8-9 added.
- Idea: Strava archive for longer history (Phase 3).
- Note: Jupyter overwrote edits made to an open notebook (autosave of its older copy). Baseline charts moved to a separate `notebooks/02_baselines.ipynb`; rule: never edit a notebook file while it is open in Jupyter.
