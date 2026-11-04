# Roadmap

- [x] **1. Skeleton**: structure, docs, contracts, config files, git
- [x] **2. Garmin collector + SQLite storage**
- [x] **3. Strava bulk-export import** (history for baselines and session targets; agent only, not shown on the dashboard)
- [x] **4. Rules-based planner + golden-day tests**: readiness gate, hard/easy alternation, weekly load limit, session targets from your own history, options for every intensity with your override, week plan seam (template now, event plan later)
- [ ] **5. LLM planner layer with explanations**: chooses and explains within the rules' options
- [ ] **6. Google Calendar + email outputs**: console brief done (`outputs/console_brief.py`); calendar and email to do
- [ ] **7. Scheduling on a home host**: the daily run (`main.py`) is ready to be scheduled; dashboard exists (local only)
- [ ] **8. Goal-driven periodization**: enter a target event (marathon, cycling, triathlon); an `event_plan` week plan source builds the plan and adapts it. Needs an `Event` model, swim targets for triathlon, and a way to tell the weekly load rule about intended ramps
- [ ] **9. Web UI polish**: more theme (rank badge, XP bar, background pattern, icons), event entry, history views

First-trial tuning (all thresholds are in `config/rules.yaml` and `config/athlete.yaml`): rule thresholds, ride bands, session targets.
