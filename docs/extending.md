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

## Swimming: what is done and what is left
Done (2026-11-04, on request): `Sport.SWIM`, both importers map swim types to it, stored workouts filed as "other"
are relabelled on startup, and the dashboard shows swims as "Swimming" with their own colour.
Not done on purpose: session targets and a template slot for swimming.
To plan swims later:
1. `planner/prescriptions.py`: add `(Sport.SWIM, Intensity.EASY/MODERATE/HARD)` rows to `DEFAULTS`. Swim pace is per
   100 m, so add a `pace_s_per_100m` field to `Prescription` and a branch for it in `prescribe`.
2. `planner/load.py`: optionally add a `DEFAULT_RATE` for swim (load per minute).
3. `config/athlete.yaml`: add `- {sport: swim, kind: general, count: 1}` to `weekly_template`.
4. Tests: a prescription test and a template test for swim.

## Adding any other sport
Same steps: add the member to `Sport`, map it in both importers, add `DEFAULTS` rows for targets, a template line,
and the dashboard entries (`SPORTS` in `web/data.py` and `activities.js`, a `--s-<sport>` colour in `style.css`,
checked with the dataviz palette validator).

## Adding an event plan (marathon, cycling, triathlon)
New file `planner/week_plans/event_plan.py` implementing `WeekPlanSource`, enabled in `config/features.yaml`
(it is already listed above the template, so it wins while an event exists). It will need an `Event` model
(type, date, goal), a way to store it, weekly load targets, and a way to tell the weekly load rule that a ramp
is intended. A triathlon also needs the swim sport above.

## Adding a rule, a collector or an output
One new plugin file implementing the stage's base class, plus one entry in `config/features.yaml`.
