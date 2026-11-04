"""Planner stage base classes. STUBS ONLY."""

from abc import abstractmethod
from datetime import date

from training_agent.core.models import Activity, DailyMetrics, PlanContext, PlannedSession, RuleVerdict, WeekTargets
from training_agent.core.plugin import Plugin


class PlannerRule(Plugin):
    """A deterministic guardrail (plugin files live in planner/rules/).

    Rules only restrict: a verdict is the highest intensity the rule allows, with reasons.
    """

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
    """Produces the PlannedSession for a day.

    Combines the minimum over all enabled PlannerRule limits with an LLM
    agent that chooses and explains the session within those limits.
    """

    @abstractmethod
    def plan_day(
        self,
        day: date,
        metrics: list[DailyMetrics],
        history: list[Activity],
    ) -> PlannedSession:
        """Return the session for `day`, never exceeding rule limits."""
