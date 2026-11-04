"""LLM layer: picks among the options the rules allow and explains the pick in plain words.

It wraps the rules planner. The rules still set the cap and build every option; the model may only
choose an intensity at or below the cap, and code checks that. If there is no key, the call fails, or
the answer is not allowed, the rules plan is returned unchanged. Only a compact summary goes to the
model (rule reasons, the options, last 7 days of workouts), never raw files or the key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import timedelta
from pathlib import Path

import yaml

from training_agent.core.models import DayPlan, Intensity, PlanContext, PlannedSession
from training_agent.planner.base import Planner
from training_agent.planner.llm_client import ROOT, NoReply, make_client
from training_agent.planner.rules_planner import RulesPlanner, rank

log = logging.getLogger("training_agent.llm_agent")
CONFIG = ROOT / "config" / "llm.yaml"
CACHE_DIR = ROOT / "data" / "cache" / "llm"
MAX_NOTE = 700

SYSTEM = (
    "You are a careful endurance-training coach for one athlete who is not a sports scientist. A rules engine has already set "
    "the highest intensity allowed today (the cap) and built the options. Choose the intensity for today from the options at or "
    "below the cap. Then write a coach note of at most 3 short plain-English sentences: why this choice fits today's numbers, and "
    "the athlete's next best step (use the top insight that needs attention, in your own words). Refer to the athlete's own numbers "
    "only as given in the facts. Never choose above the cap. Do not invent data. Do not give medical advice."
)
TOOL = {
    "name": "submit_decision",
    "description": "Submit today's intensity and the explanation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intensity": {"type": "string", "enum": [i.value for i in Intensity]},
            "coach_note": {"type": "string", "description": "2-3 plain sentences for the athlete."},
        },
        "required": ["intensity", "coach_note"],
    },
}


def _load_config(path: Path = CONFIG) -> dict:
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def build_prompt(plan: DayPlan, ctx: PlanContext) -> str:
    """The facts the model sees. Compact on purpose."""
    since = ctx.day - timedelta(days=7)
    recent = [{"date": str(a.start_time.date()), "sport": a.sport.value, "minutes": round((a.duration_s or 0) / 60),
               "load": round(a.training_load) if a.training_load else None}
              for a in ctx.activities if since <= a.start_time.date() < ctx.day]
    options = []
    for o in plan.options:
        p = o.prescription
        options.append({"intensity": o.intensity.value, "session": o.title, "risk": o.risk,
                        "minutes": round(p.duration_min) if p and p.duration_min else None,
                        "km": round(p.distance_km, 1) if p and p.distance_km else None})
    facts = {
        "date": str(plan.day), "cap": plan.cap.value, "rules_recommend": plan.recommended.value,
        "rule_verdicts": [{"rule": v.rule, "allows_up_to": v.max_intensity.value, "reasons": v.reasons} for v in plan.verdicts],
        "options": options, "done_this_week": plan.done_this_week,
        "still_to_do_this_week": [f"{s.sport.value} ({s.kind})" for s in plan.remaining_slots],
        "dropped_this_week": [f"{s.sport.value} ({s.kind})" for s in plan.dropped_slots],
        "workouts_last_7_days": recent,
        # the planner's guidance, most important first; "act" and "watch" items are what the note should build on
        "insights": [{"status": i.status, "area": i.area, "finding": i.headline, "do_next": i.action} for i in plan.insights],
    }
    return json.dumps(facts, indent=1)


class LlmAgent(Planner):
    name = "llm_agent"

    def __init__(self, client=None, rules: Planner | None = None, cache_dir: Path | None | str = "default", config: dict | None = None):
        cfg = {**_load_config(), **(config or {})}
        self.rules = rules or RulesPlanner()
        self.client = client or make_client(cfg)
        self.model = getattr(self.client, "model", "custom")
        cache_dir = CACHE_DIR if cache_dir == "default" else cache_dir
        self.cache_dir = cache_dir if getattr(self.client, "cacheable", True) else None

    # ---------- main entry ----------
    def plan_day(self, ctx: PlanContext) -> DayPlan:
        plan = self.rules.plan_day(ctx)
        if not getattr(self.client, "available", True):
            return plan
        prompt = build_prompt(plan, ctx)
        try:
            decision = self._cached(plan, prompt) or self._ask(plan, prompt)
        except NoReply as e:
            log.info("LLM layer waiting: %s", e)
            return plan
        except Exception as e:  # never let the model break the daily plan
            log.warning("LLM layer skipped: %s", e)
            return plan
        return self._apply(plan, decision)

    def to_session(self, plan: DayPlan, intensity: Intensity) -> PlannedSession:
        return self.rules.to_session(plan, intensity)

    # ---------- model call, cache, checks ----------
    def _key(self, prompt: str) -> str:
        return hashlib.sha256(f"{self.model}\n{SYSTEM}\n{prompt}".encode()).hexdigest()[:16]

    def _cached(self, plan: DayPlan, prompt: str) -> dict | None:
        if not self.cache_dir:
            return None
        f = self.cache_dir / f"{plan.day}-{self._key(prompt)}.json"
        return json.loads(f.read_text()) if f.exists() else None

    def _ask(self, plan: DayPlan, prompt: str) -> dict:
        decision = self.client.choose(SYSTEM, prompt, TOOL)
        decision = {"intensity": str(decision["intensity"]), "coach_note": str(decision["coach_note"])}
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{plan.day}-{self._key(prompt)}.json").write_text(json.dumps(decision))
        return decision

    def _apply(self, plan: DayPlan, decision: dict) -> DayPlan:
        try:
            chosen = Intensity(decision["intensity"])
        except ValueError:
            log.warning("LLM layer ignored: unknown intensity %r", decision.get("intensity"))
            return plan
        if rank(chosen) > rank(plan.cap):
            log.warning("LLM layer ignored: %s is above the cap (%s)", chosen.value, plan.cap.value)
            return plan
        options = [o.model_copy(update={"risk": "recommended" if o.intensity == chosen else
                                        ("ok" if o.risk == "recommended" else o.risk)}) for o in plan.options]
        title = next(o.title for o in options if o.intensity == chosen)
        summary = re.sub(r"^Recommended: [^.]*\.", f"Recommended: {title.lower()}.", plan.summary)
        return plan.model_copy(update={"recommended": chosen, "options": options, "summary": summary,
                                       "decided_by": "llm", "coach_note": decision["coach_note"].strip()[:MAX_NOTE]})
