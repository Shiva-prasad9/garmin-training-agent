# Extending the agent

The agent is built so that new sports, plans and outputs are added as small, separate changes.
Everything below is a checklist; none of it is needed until you decide to do it.

## Changing the weekly template (no code)
Edit `weekly_template` in `config/athlete.yaml`, for example two runs and no bike:

    weekly_template:
      - {sport: run,  kind: "10k",  count: 2}
      - {sport: gym,  kind: strength, count: 3}
      - {sport: rest, kind: rest, count: 1}

`kind` can be `short`, `long`, a distance like `"10k"` or `"21.1k"`, or `strength`.

## Adding a sport (for example swimming)
1. `core/models.py`: add `SWIM = "swim"` to `Sport`.
2. Importers: map the source's swim type to `Sport.SWIM` in `collectors/strava_export.py` (`_sport`) and in
   `collectors/garmin_personal_api.py` (`_sport`). Both currently file swims under "other".
   Re-run `scripts/import_strava.py` afterwards so the 30 old swims are re-tagged.
3. `planner/prescriptions.py`: add `(Sport.SWIM, Intensity.EASY/MODERATE/HARD)` rows to `DEFAULTS`.
   Swim pace is per 100 m, so add a `pace_s_per_100m` field to `Prescription` and a branch for it in `prescribe`.
4. `planner/load.py`: optionally add a `DEFAULT_RATE` for swim (load per minute).
5. `config/athlete.yaml`: add a line such as `- {sport: swim, kind: general, count: 1}` to `weekly_template`.
6. Dashboard: add swim to `SPORTS` in `web/data.py` and in `static/js/panels/activities.js`, plus a colour
   `--s-swim` in `static/style.css` (check it with the dataviz palette validator).
7. Tests: a prescription test and a template test for swim.

## Adding an event plan (marathon, cycling, triathlon)
New file `planner/week_plans/event_plan.py` implementing `WeekPlanSource`, enabled in `config/features.yaml`
(it is already listed above the template, so it wins while an event exists). It will need an `Event` model
(type, date, goal), a way to store it, weekly load targets, and a way to tell the weekly load rule that a ramp
is intended. A triathlon also needs the swim sport above.

## Adding a rule, a collector or an output
One new plugin file implementing the stage's base class, plus one entry in `config/features.yaml`.
