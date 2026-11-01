# Roadmap

- [ ] **1. Skeleton** (in progress): structure, docs, contracts (stubs), config files, git
- [ ] **2. Garmin collector + SQLite storage**: observability only, read-mostly
- [ ] **3. Strava bulk-export import**: historical backfill
- [ ] **4. Rules-based planner + golden-day tests**
- [ ] **5. LLM planner layer with explanations**
- [ ] **6. Google Calendar + email outputs**
- [ ] **7. Scheduling on home host, simple dashboard**

## Ultimate goal (added 2026-11-01)
- [ ] **8. Goal-driven periodization**: user enters a target event (e.g. marathon in 5 months); the agent estimates fitness, builds a periodized plan (base, build, peak, taper), and adapts it as progress is measured. Needs a new `Goal`/`Event` model and a planner plugin; no core edits.

First milestone: read Garmin data and store it (Phase 2), then improve step by step.
- [ ] **9. Web UI**: polished local website (dashboard of recovery, plan and progress; goal entry) served from the home host. Reads the same SQLite database and models; added as new files, no core changes.
