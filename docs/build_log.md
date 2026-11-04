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
- Charts reviewed: data good; found a few very short nights and an HRV spike from partial recordings, and a slow HRV decline.
- New contract models `SignalAssessment`, `DailyAssessment` in `core/models.py`.
- `planner/baselines.py`: baseline = median of the previous 28 valid days, spread = scaled MAD (robust), z-score per signal. Flags: missing_sleep, short_sleep (<3 h), missing_hrv, hrv_outlier (|z|>4), insufficient_baseline. Short nights are excluded from sleep/HRV baselines. Thresholds in `config/rules.yaml`.
- Tests: `tests/test_baselines.py` (6 tests, synthetic series). Notebook sections 8-9 added.
- Idea: Strava archive for longer history (Phase 3).
- Note: Jupyter overwrote edits made to an open notebook (autosave of its older copy). Baseline charts moved to a separate `notebooks/02_baselines.ipynb`; rule: never edit a notebook file while it is open in Jupyter.

### Step 10: Dashboard (2026-11-01)
- Theme chosen: Solo Leveling "system window" (light background, indigo highlights, dark toggle). Panels: status window (latest day vs your normal), daily quest placeholder, trends (HRV, sleep, resting HR, Body Battery; 7/10/14 days, default 10; normal-range band; flagged days; table view), activities (workouts with HR zones, weekly load by sport).
- Backend: `web/data.py` (`build_overview`), `web/app.py` (`/api/overview`), `scripts/serve.py` (`--lan` for home network). Tests in `tests/test_web_data.py`.
- Colour check: sport colours validated with the dataviz palette validator (all adjacent-pair checks pass; aqua is below 3:1 on the light surface, so every sport also has a text label).
- Not yet visually checked: no browser available in the dev environment; first look is by the user.
- Dashboard review round 1 (screenshots): fixed default theme (light unless toggled), chart text too small (charts now drawn at real width and redrawn on resize), 2 charts per row, one-row status cards, duplicate activity names.

### Step 11: Dashboard committed, pause on step 1a (2026-11-01)
- Dashboard reviewed on screenshots (light theme, readable charts, 2x2 trends, activities). Theme polish deferred: user will research UI tuning ideas (rank badge, XP bar, background pattern, icons).
- Next: 7-day trend per signal, then the rules-based planner.

### Step 12: 7-day trend (2026-11-01)
- Goal: catch slow changes a single day's z-score misses (e.g. HRV drifting down while each night looks normal).
- `SignalAssessment` gains `trend` (up/down/steady/None), `trend_mean`, `trend_z`, `trend_n`. Method: plain average of the last 7 valid days vs the 28-day baseline, scaled by spread/sqrt(days used); steady if |z| < 1.5; needs 4+ valid days. Short nights excluded. Parameters in `config/rules.yaml`.
- Dashboard status cards show the trend as improving/declining/steady (direction judged per signal: higher HRV is good, lower resting HR is good).
- 5 new tests (21 total). On real data the trend showed resting HR up, Body Battery down and HRV borderline, with sleep steady.
- Commit message convention: no Co-Authored-By lines (owner preference).

### Step 13: Strava export import (2026-11-04)
- Probed the export (names and counts only): several years of workouts across rides, runs, swims, weight training, hikes and walks. Units: distance in metres (second `Distance` column), time in seconds. Nearly all Strava workouts in Garmin's period match a Garmin workout (start within 3 min).
- Heart rate on only 21 of 95 rides; Strava estimates power for rides without a meter. Relative Effort on 151 workouts, Perceived Exertion on 30.
- `Activity` gains optional `relative_effort`, `perceived_exertion`, `avg_power_w`, `elevation_gain_m`. `activities` table migrates automatically (columns added, data untouched).
- `collectors/strava_export.py` (plugin, read-only, uses Moving Time; hike with a 128-day elapsed time avoided). `scripts/import_strava.py` runs the one-time import.
- `core/activities.merge_duplicates`: both sources stay stored; reads return one record per workout (Garmin preferred, Strava effort fields carried over). `include_duplicates=True` returns everything.
- 5 new tests (26 total). Next: calibrate Strava Relative Effort against Garmin load on the matched workouts, then continue the planner.

### Step 14: Calibrating Strava effort to Garmin load (2026-11-04)
- 26 Garmin workouts match a Strava workout; 21 have both Garmin load and Strava Relative Effort (RE). Correlation 0.93.
- Ratio Garmin load / RE varies widely (RE grows faster than Garmin load for very hard efforts). A single multiplier, **load = 1.42 x RE**, has ~20% median error; a power-law fit was worse, so the simple multiplier is used.
- Rides without HR: Garmin load is ~0.1-0.5 (effectively nothing). All 4 are in Strava with a perceived exertion and estimated watts. Estimated watts do not track HR-based effort (correlation -0.37 on rides) so they are not used. Perceived exertion has only 2 rides that also have HR effort, so it cannot be calibrated yet.
- Decision: effort for no-HR rides = duration x typical load per minute of the athlete's HR rides (about 1.3-1.9/min for rides; runs about 2.5/min), with perceived exertion as a rough +/-30% adjustment when present; marked low confidence.
- To be implemented in planner step 2 (own load estimate). Going forward, logging a perceived effort per workout would let this be calibrated properly.

### Step 15: Perceived Relative Effort (2026-11-04)
- The user pointed out that for rides without HR they enter a 1-10 rating and Strava computes the effort. The export has this as `Perceived Relative Effort`; the importer was missing it. Added to `Activity`, storage (auto-migrated) and the importer; re-imported.
- Coverage: rides 20 HR-based + 22 rating-based of 95; runs 54 + 5 of 78; gym 26 of 26. Rating-based effort per hour rises with the rating (3: ~30, 5: ~65, 7: ~115) but is rough (about half the HR value on runs, 2.4x at rating 10). Garmin's four no-HR rides convert to about 4, 247, 1001 and 402 load, consistent with the duration-based estimate.
- Effort order recorded as D016.

### Step 16: Planner steps 1-5 (2026-11-04)
- Contracts in `core/models.py`: `RuleVerdict`, `PlanContext`, `Prescription`, `SessionOption`, `lowest()`; `PlannedSession` gains recommended_intensity / overridden / warnings; `planned_sessions` table migrated; `Repository.get_plan` added.
- `planner/load.py`: effort in the D016 order, per-sport load rate, hard threshold (top quarter of the athlete's 90 days) and `is_hard` (zones 4-5 share or top-quarter effort; gym never hard).
- Rule plugins (thresholds in `config/rules.yaml`, enabled in `features.yaml`): `readiness_gate`, `hard_easy_alternation`, `weekly_load_limit`. `PlannerRule` now has one method, `evaluate(ctx) -> RuleVerdict`.
- Tests: 55 passing (new `test_load.py`, `test_rules.py`).
- Real-data run on the owner's last days: the planner recommended easy days with plausible reasons (poor sleep score, resting HR trend, hard day before, high weekly load vs. average).
- Observation for tuning: the athlete's weeks are very lumpy, so the average week load is small and the weekly limit stays on for days.
- Weekly load limit changed to an 8-week average (D017): on real data the last days now read about 100-120% of the average week instead of 170-240%. 56 tests pass. All thresholds to be tuned after the first trial.

### Step 17: Week-plan seam and session targets (2026-11-04)
- Idea from the user: a target event (marathon, cycling, triathlon) must be able to override the weekly template. Built the seam: `SessionSlot` / `WeekTargets` models, `WeekPlanSource` plugin base, `planner/week_plan.py` (`targets_for_week`: first enabled source with a plan wins), `week_plans/fixed_template.py` (reads `weekly_template` from `config/athlete.yaml`), and a `week_plans` section in `features.yaml` (`event_plan` listed first, disabled, to be written later). An event plan will also need an `Event` model, a swim sport for triathlon, and a way to tell the weekly load rule that a ramp is intended.
- `planner/prescriptions.py` (step 6): easy/moderate/hard buckets by avg HR share of max HR (<75%, 75-85%, >85%; max HR 195 in athlete.yaml) or by the 1-10 rating when no HR; targets are medians/quantiles of matching sessions in the last 180 days (long = 75th percentile duration, short = 25th, "10k" fixes distance); defaults when fewer than 3 sessions; harder sessions capped at 80% / 60% of the easy duration; HR range at least 6 bpm wide; volume_factor for fatigue.
- Real-data targets looked sensible (easy run slower and lower heart rate than moderate; rides likewise); sports with few sessions use defaults.
- 75 tests pass.
- Sports and plans kept open (D018): weekly template is config only; adding swimming is the checklist in `docs/extending.md`; prescriptions no longer hard-code the sport list.

### Step 18: The rules planner (2026-11-04)
- `planner/rules_planner.py` (plugin `rules_planner`): combines the caps of all enabled rules, the active week plan source's open slots (`week_progress`: recorded workouts use up matching slots, days without a workout use up rest slots), and session targets into a `DayPlan` with a recommendation and one option per intensity (rest, easy, moderate, hard).
- Recommendation: never above the cap; REST if the cap is rest, or tired (cap easy or lower) with a free day left, or the week is complete; HARD only as a key session when there was no hard session in 5 days and the best open slot suits it; otherwise moderate (or the cap).
- Every option can be chosen. Risk: recommended / ok / caution (one level above the cap) / not_advised (two or more). `to_session` records `overridden` when the choice is above the cap, with the recommendation, flags and warnings.
- Each option previews tomorrow (alternation and weekly rules re-run with the planned session; rules that need tomorrow's own readings are skipped). Sessions are shortened (x0.85) the day after a hard one.
- Slot choice: kind-vs-intensity suitability (long ride = easy/moderate, short ride and 10k = hard key sessions, strength = easy/moderate), avoids the same endurance sport two days running, offers an "extra session" when the week's template is complete.
- 86 tests pass (new `test_rules_planner.py`). Real data, Wed 4 Nov: allowed easy (sleep score unusually low, resting HR trending up), recommended easy short ride; moderate is "caution", hard is "not advised" with tomorrow capped at easy.

### Step 19: Corrections after the first planner output (2026-11-04)
- The athlete's own ride definition replaces the heart-rate buckets for rides: under 2 h easy, 2-5 h moderate, over 5 h hard (`ride_bands_min: [120, 300]` in `config/athlete.yaml`). "Harder is shorter" now applies to runs only; a harder ride is a longer ride. Ride targets include typical climbing (elevation gain, from Strava and now Garmin too). Note: durations are moving time; the athlete thinks in elapsed time with breaks, so bands may need tuning after the first trial.
- Suitability of session kinds: a long ride suits moderate/hard days, a short ride easy/moderate days.
- When the week is behind (more sessions open than days left, keeping a rest day if one is still owed) the planner drops sessions: strength first, then the short ride, then the long ride; key sessions last. Shown as `dropped_slots` and in the summary.
- 90 tests pass.

### Step 20: Golden-day scenarios (2026-11-04)
- `tests/test_golden_days.py` runs 12 fixed scenarios from `tests/golden/*.yaml` through the real planner with the real thresholds (format in `tests/golden/README.md`). Scenarios: fresh and rested (key session), the real 1 Nov pattern, day after a hard run, short night (no false alarm), missing sleep/HRV, weekly load spike, illness pattern (rest), declining HRV trend with a fine day, override (hard chosen while easy recommended), week behind (drops a gym session), complete week (rest), planned hard session yesterday.
- Two expectations were corrected while writing them (wording of the weekly reason; a weekly spike also follows a 320-load day), not the planner. 98 tests pass.
- Rule: golden days run before every merge; changing a threshold changes outcomes here on purpose.

### Step 21: Daily quest, week panel and gym log on the dashboard (2026-11-04)
- API: `GET /api/plan` (recommendation + options + what was chosen), `POST /api/plan/choose` (any option, including above the cap; replaces an earlier choice; recorded with the recommendation, flags and warnings), `POST /api/plan/clear`, `GET/POST/DELETE /api/gym`.
- Safety: changes are only accepted from the computer the dashboard runs on (reading is open with `--lan`), since there is no login. Inputs are validated (gym minutes 5-300, effort 1-10, day within 14 days).
- Gym log: manual sessions are stored as activities with source `manual` (stable id `manual:gym:<date>:<n>`), count towards the week's strength slots and the load estimate (scaled by the 1-10 rating), and show on the dashboard. Strava stays hidden. `estimate_effort` now gives strength work a small load estimate.
- Frontend: Daily quest panel (recommendation, four option cards with targets, risk label with icon + words, tomorrow preview, Plan this / Undo, override banner), "This week" panel (done / open / dropped), Gym log panel. Panels redraw after any change. Storage gains `delete_plan` and `delete_activity`.
- 110 tests pass. Not yet seen in a browser.

### Step 22: Review of the new dashboard panels (2026-11-04)
- The athlete tried the dashboard: choosing, the week panel and the gym log all worked (a gym entry showed in This week and Activities).
- Fixes from the screenshots: swimming is now its own sport (`Sport.SWIM`; Garmin "lap swimming" and Strava "Swim" map to it; stored rows relabelled on startup; yellow `--s-swim`, validated light and dark); the 7-day trend badge on the status card sits on its own line without a stray space; the quest headline no longer repeats the recommendation. `docs/extending.md` updated. 113 tests pass.

### Step 23: The daily run (2026-11-04)
- `DailyBrief` (core contract) now carries the planner's `DayPlan`, the day's metrics, the newest data date and notes.
- `pipeline.run_daily` (collect -> store -> plan -> publish; all stages from `features.yaml`, plugins injectable for tests). A source that fails does not stop the run: the brief is made from stored data and says so. Stale data is reported ("newest recovery data is N days old"). A broken output does not stop the others. Empty database gives a clear error.
- `outputs/console_brief.py`: `format_brief` plain-text brief (allowed level and why, recommendation with targets and tomorrow preview, all options with risk, this week). Email and calendar outputs will reuse it.
- `main.py`: `--days N`, `--day YYYY-MM-DD`, `--no-collect`; logs to console and `logs/daily_run.log`.
- 122 tests pass (new `test_pipeline.py`). Offline run on real data produces the same recommendation as the dashboard. README and roadmap updated: phases 1-4 done.

### Step 24: Small fixes, and a leaked key found before going public (2026-11-04)
- The Strava archive no longer runs in the daily run (`daily_run: false` in `features.yaml`, honoured by `load_enabled_plugins(..., require="daily_run")`); the brief now starts with a "Recovery today" line (sleep, HRV, resting HR, Body Battery).
- Audit before making the repo public: the live Garmin API key was in the tracked `.env.example` (in every commit from the Strava/collector commit on, and pushed). Cause: the key was saved into the example file; earlier checks looked at file names only. Fixed in the working tree (names only). Added `tests/test_repo_hygiene.py` (scans tracked file contents for key patterns, requires `.env.example` to hold names only, forbids private or generated files) and rule 9 in `CLAUDE.md`. The key must be revoked and replaced; history still contains it until rewritten or the repository is recreated.

### Step 25: The LLM layer (2026-11-04)
- New planner plugin `planner/llm_agent.py` (+ `llm_client.py`, `config/llm.yaml`). It wraps the rules planner: the rules still set the cap and build every option; the model picks one intensity at or below the cap and writes a 2-3 sentence coach note. `DayPlan` gains `decided_by` and `coach_note`.
- Guardrails in code (D020): a choice above the cap, an unknown intensity, an API error or a missing `ANTHROPIC_API_KEY` all return the rules plan unchanged. Answers are cached per day and per facts in `data/cache/llm/` (git-ignored), so the dashboard does not call the model on every refresh.
- Privacy: the model sees only a compact summary (rule reasons, the options, workouts of the last 7 days: sport, minutes, load). No raw files, no key, no name.
- Plain `httpx` call with a forced tool (structured answer); no SDK needed. Model set in `config/llm.yaml`.
- 7 new tests with a fake client (133 total). Real run without a key: falls back to the rules plan as designed.

### Step 26: LLM providers are plug and play (2026-11-04)
- `config/llm.yaml` gets `provider: manual | anthropic | none` (default manual, no key). `make_client` picks the client; a new client is one small class.
- Manual mode: the run writes `data/llm/prompt_<date>.md`; a reply saved as `data/llm/reply_<date>.json` is used (checked against the cap like any answer). No reply means rules-only.
- `docs/llm.md` documents all providers and the Anthropic setup. 136 tests pass.

### Step 27: User guide and workout details (2026-11-04)
- User guide: `panels/guide.js` (collapsed panel at the bottom, "Guide" link in the header). Plain-language help for every panel plus a short glossary.
- Probed the Garmin per-activity endpoints (field names only). `/activity-service/activity/<id>` (summary) and `.../details` (per-sample series + GPS route) work; `.../splits` and `.../hrTimeInZones` return 404 (zones already come with the activity list). Checked that values arrive in metres, seconds and m/s, so the unit "factor" is not applied.
- New `ActivityDetail` model, optional `Collector.collect_activity_detail`, `activity_details` table, `pipeline.fetch_missing_details` (run/bike/other only; one failure never stops the rest), `backfill.py --details`. Raw responses are cached under `data/raw/garmin/activity_details/` (git-ignored). The dashboard reads stored data only, it never calls Garmin.
- Endpoint `/api/activities/<id>`; clicking a ride, run or hike opens a dialog: moving vs elapsed time, speed or pace, climbing, elevation range, heart rate and zones, calories, temperature, linked charts (heart rate, speed or pace, elevation, power, cadence along the distance) and the route drawn as a line with start/end markers and a scale bar. No map tiles, so the route never leaves the computer.
- 5 new tests (141 total). The JavaScript could not be run in the build environment, so the dialog needs a first visual check in the browser.

### Step 28: Side navigation and the Activities section (2026-11-04)
- Left menu with Overview, Activities (drop-down: all, cycling, running, hiking and walking, swimming, strength, other, each with a count) and User guide. Hash routes (`#/overview`, `#/activities/bike`, `#/guide`) so the browser back button works. The 7/10/14 day buttons show on the overview only.
- Activities view (`views/activities_view.js`, endpoint `/api/activity-log?kind=&days=`): choose 1, 3, 6 or 12 months; totals, hours per month (the existing stacked-bar chart, generalised for other periods and units) and the workouts grouped by month. Rows open the same detail window. A notice explains how to download older history when the stored history is shorter than the chosen period. Strava stays out.
- The guide moved from the bottom of the overview to its own page; `setup.py` now loads 6 months with details.
- History for the user: `scripts/backfill.py --days 180 --details`. 142 tests pass; the JavaScript still needs the first visual check in the browser.

### Step 29: Thunder theme and new layout (2026-11-04)
- The cream/red comic theme was rejected. Rebuilt from the user's references (dark card dashboards, and a Zenitsu image for colour): near-black rounded cards, gold and orange accents, his triangle (haori) pattern as a subtle motif, a pale mint light mode. Dark is the default; the toggle is in the side menu.
- New layout: side menu with icons and a brand block, page title bar, four key-number cards with a trend line each (Body Battery, HRV, sleep score, resting heart rate), "Today's plan" with the four options in a 2x2 grid, a Readiness card (four-step gauge of the allowed level, why, and the coach note), trends, a week progress ring, activities and the gym log. All styling is in `style.css` (the separate `pop.css` was removed).
- The workout window opens with a bounce and a lightning flash across a gold header with the triangle pattern, a black starburst badge with the distance, and tiles that pop in one by one.
- Contrast checked with a script on both modes (text 4.5:1 or better; marks about 3.4:1 or better; light-mode level and accent colours were darkened for this). Status colours always carry an icon and a word.
- The JavaScript could only be bracket-checked, not run, so the first browser look may need fixes.

### Step 30: Browser review, insights and next best step (2026-11-04)
- Reviewed the dashboard in a real browser (Playwright, installed in the venv as a dev tool; `scripts/screenshots.py` repeats it, dark, light and phone width, and reports console errors). The Node-based Playwright MCP could not be used (no Node.js here). Found and fixed: a long overview that repeated the same reasons in many places, an options area that dominated the page, jargon ("declining" for a rising resting heart rate), an "HP" leftover label, pace chart spikes from stops, a wrapping elevation tile, a stray white bar in the activity window with reduced motion, unreadable text in the light-mode hero box, and a very long month list.
- New insight plugins (`planner/insights/`, enabled in `features.yaml`, one file each): sleep_debt, recovery_trend, rest_days, load_balance, intensity_mix, consistency, progression. Each turns the athlete's own data into a plain sentence, why it matters, what to do, and a priority. They are advisory (never limit the plan) and return nothing when data is thin. The weekly load maths moved to `planner/load.weekly_load_ratio`, shared by the rule and the insight.
- Dashboard: a gold "Your next best step" card at the top (the highest-priority insight that needs attention), an Insights grid with Needs action / Keep an eye on it / On track and a "numbers behind it" drop-down, one plain-language meaning line under each Garmin metric, a compact Today's plan (recommended session in full, other choices in short rows), and months in the activity list that collapse (latest two open). The console brief also prints the next best step.
- 150 tests pass (8 new, one per insight plus planner ordering and failure isolation).

### Step 31: Calmer overview, Insights on its own page (2026-11-04)
- Feedback: the overview was overcrowded with words. The next best step and the insight cards moved to a new "Insights" page, last in the left menu (under User guide). The overview is back to key numbers, today's plan, readiness, trends, week, activities and gym log, with fewer words: no metric explanations, shorter trend labels, details of other choices behind one "Details" link, no coach box unless there is a coach note, shorter legends and helper texts.

### Step 32: Short overview, manual log under Activities (2026-11-04)
- Overview cut from about 3,900 px tall to about 1,450 px: key numbers, then today's plan (recommended session in full, the other three as compact choice buttons), a small readiness gauge, a week ring, trends in a 2x2 block, and a short "Recent activity" list (5 workouts, "See all activities" link). The weekly-load chart, the long activity list and the gym log left the overview.
- The gym log became a general manual log (`/api/manual`, replacing `/api/gym`): under Activities, "+ Log an activity by hand" with an Activity drop-down (strength, running, cycling, swimming, hiking, walking, other), date (up to 90 days back), minutes, optional distance and a 1-10 effort. Entries count toward the week and load, show up under the matching sport, and can be deleted from the same list.
- 151 tests pass. Checked in a real browser (dark, light, phone): no console errors.
