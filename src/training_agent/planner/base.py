"""Planner stage base classes. STUBS ONLY."""

from abc import abstractmethod
from datetime import date

from training_agent.core.models import Activity, DailyMetrics, Intensity, PlannedSession
from training_agent.core.plugin import Plugin


class PlannerRule(Plugin):
    """A deterministic guardrail (plugin files live in planner/rules/).

    Rules only restrict; they never raise the allowed intensity.
    """

    @abstractmethod
    def max_intensity(
        self,
        day: date,
        metrics: list[DailyMetrics],
        history: list[Activity],
    ) -> tuple[Intensity, str]:
        """Return the highest allowed intensity for `day` and the reason."""


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
