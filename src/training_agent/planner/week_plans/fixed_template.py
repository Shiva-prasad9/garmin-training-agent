"""The default week plan: a fixed weekly template from config/athlete.yaml."""

from __future__ import annotations

from datetime import date

from training_agent.core.models import SessionSlot, Sport, WeekTargets
from training_agent.planner.base import WeekPlanSource
from training_agent.planner.params import load_athlete

# Used when athlete.yaml has no `weekly_template`: 1 run (10k), 2 bike (short + long), 3 gym, 1 rest.
DEFAULT_TEMPLATE = [
    {"sport": "run", "kind": "10k", "count": 1},
    {"sport": "bike", "kind": "short", "count": 1},
    {"sport": "bike", "kind": "long", "count": 1},
    {"sport": "gym", "kind": "strength", "count": 3},
    {"sport": "rest", "kind": "rest", "count": 1},
]


class FixedTemplate(WeekPlanSource):
    name = "fixed_template"

    def __init__(self, template: list[dict] | None = None):
        self._template = template or load_athlete().get("weekly_template") or DEFAULT_TEMPLATE

    def targets_for_week(self, week_start: date) -> WeekTargets:
        slots = [
            SessionSlot(sport=Sport(e["sport"]), kind=e.get("kind", "general"))
            for e in self._template for _ in range(int(e.get("count", 1)))
        ]
        return WeekTargets(week_start=week_start, source=self.name, phase="template", slots=slots,
                           notes=["Fixed weekly template from athlete.yaml."])
