# Golden days

Each `*.yaml` file is one fixed scenario and the outcome the planner must produce. They run with the real
thresholds from `config/rules.yaml`, so tuning a threshold changes outcomes here on purpose: update the
expectation only when the new outcome is what you want.

```yaml
description: what this day is about
weekday: wed                 # the day being planned (mon..sun); default wed
baseline: {sleep_score: 80}  # optional: steady-state values (sleep_hours, sleep_score, hrv, resting_hr, body_battery)
metrics:                     # overrides; days_ago 0 = the planned day, null = missing
  - {days_ago: 0, sleep_score: 61, resting_hr: 52}
history: {every: 2, loads: [70, 90, 130], sports: [bike, run]}   # steady background training (optional)
activities:                  # explicit workouts
  - {days_ago: 1, sport: bike, minutes: 240, load: 343, hr: 143}
chosen:                      # sessions the athlete accepted earlier
  - {days_ago: 1, sport: run, intensity: hard}
expect:
  cap: easy
  recommended: easy
  risk: {moderate: caution, hard: not_advised}
  reasons_contain: ["Sleep score unusually low"]
  tomorrow_contains: {hard: "capped at easy"}
  title_starts: {hard: "Hard"}
  dropped: [strength]
  remaining_has: ["10k"]
  summary_contains: "behind"
  choose: {intensity: hard, overridden: true, recommended_intensity: easy, flags_contain: [readiness_gate]}
```
