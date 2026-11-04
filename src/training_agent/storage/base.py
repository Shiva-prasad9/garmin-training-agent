"""Storage stage base class. STUB ONLY."""

from abc import abstractmethod
from datetime import date

from training_agent.core.models import Activity, DailyMetrics, PlannedSession
from training_agent.core.plugin import Plugin


class Repository(Plugin):
    """Persists and retrieves shared models (SQLite in data/db/).

    New features add tables; existing tables and data/raw/ are never rewritten.
    """

    @abstractmethod
    def save_metrics(self, metrics: list[DailyMetrics]) -> None:
        """Upsert daily metrics."""

    @abstractmethod
    def save_activities(self, activities: list[Activity]) -> None:
        """Upsert activities."""

    @abstractmethod
    def save_plan(self, sessions: list[PlannedSession]) -> None:
        """Store planned sessions."""

    @abstractmethod
    def get_plan(self, start: date, end: date) -> list[PlannedSession]:
        """Return stored planned sessions for the inclusive range."""

    @abstractmethod
    def get_metrics(self, start: date, end: date) -> list[DailyMetrics]:
        """Return stored metrics for the inclusive range."""

    @abstractmethod
    def get_activities(self, start: date, end: date) -> list[Activity]:
        """Return stored activities for the inclusive range."""
