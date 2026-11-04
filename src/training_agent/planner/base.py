"""Planner stage base classes. STUBS ONLY."""

from abc import abstractmethod
from datetime import date

from training_agent.core.models import PlanContext, DayPlan, Intensity, PlannedSession, RuleVerdict, WeekTargets
from training_agent.core.plugin import Plugin


class PlannerRule(Plugin):
    """A deterministic guardrail (plugin files live in planner/rules/).

    Rules only restrict: a verdict is the highest intensity the rule allows, with reasons.
    A rule that needs the day's own morning readings (sleep, HRV, ...) sets `uses_daily_readings`
    so it is skipped when previewing a day whose readings do not exist yet.
    """

    uses_daily_readings: bool = False

    @abstractmethod
    def evaluate(self, ctx: PlanContext) -> RuleVerdict:
        """Return the cap this rule sets for ctx.day and the reasons for it."""


class WeekPlanSource(Plugin):
    """Says what a week should contain. The daily planner asks; it never hard-codes a template.

    The fixed weekly template is one source; an event plan (marathon, cycling, triathlon) is another.
    Sources are tried in the order listed under `week_plans` in features.yaml; the first one that
    returns targets wins, so an event plan listed first overrides the template while an event exists.
    """

    @abstractmethod
    def targets_for_week(self, week_start: date) -> WeekTargets | None:
        """Return the week's targets, or None if this source has no plan for that week."""


class Planner(Plugin):
    """Turns a PlanContext into a DayPlan: caps from the rules, the week's template, and options to choose from."""

    @abstractmethod
    def plan_day(self, ctx: PlanContext) -> DayPlan:
        """Return the recommendation and all options for ctx.day."""

    @abstractmethod
    def to_session(self, plan: DayPlan, intensity: Intensity) -> PlannedSession:
        """Turn the chosen option into a PlannedSession (records whether it overrides the recommendation)."""
