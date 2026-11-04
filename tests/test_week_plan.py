"""Week plan sources: the template, and the rule that the first source with a plan wins."""
from datetime import date

import pytest

from training_agent.core.models import SessionSlot, Sport, WeekTargets
from training_agent.planner.base import WeekPlanSource
from training_agent.planner.week_plan import load_sources, monday_of, targets_for_week
from training_agent.planner.week_plans.fixed_template import FixedTemplate

MONDAY = date(2026, 11, 2)


def test_default_template_matches_the_athletes_week():
    t = FixedTemplate().targets_for_week(MONDAY)
    kinds = sorted((s.sport.value, s.kind) for s in t.slots)
    assert kinds == [("bike", "long"), ("bike", "short"), ("gym", "strength"), ("gym", "strength"),
                     ("gym", "strength"), ("rest", "rest"), ("run", "10k")]
    assert t.source == "fixed_template" and len(t.slots) == 7


def test_template_comes_from_the_given_definition():
    t = FixedTemplate([{"sport": "run", "kind": "long", "count": 2}]).targets_for_week(MONDAY)
    assert [s.kind for s in t.slots] == ["long", "long"]


class FakeEventPlan(WeekPlanSource):
    name = "event_plan"

    def __init__(self, active):
        self.active = active

    def targets_for_week(self, week_start):
        if not self.active:
            return None
        return WeekTargets(week_start=week_start, source=self.name, phase="build",
                           slots=[SessionSlot(sport=Sport.RUN, kind="long")], load_target=500.0)


def test_event_plan_overrides_the_template_when_it_has_a_plan():
    t = targets_for_week(MONDAY, [FakeEventPlan(True), FixedTemplate()])
    assert t.source == "event_plan" and t.phase == "build"


def test_template_is_used_when_the_event_plan_has_nothing():
    assert targets_for_week(MONDAY, [FakeEventPlan(False), FixedTemplate()]).source == "fixed_template"


def test_no_source_is_an_error():
    with pytest.raises(RuntimeError):
        targets_for_week(MONDAY, [FakeEventPlan(False)])


def test_sources_load_from_config_and_monday_helper():
    assert [s.name for s in load_sources()] == ["fixed_template"]  # event_plan exists only once enabled
    assert monday_of(date(2026, 11, 4)) == MONDAY
