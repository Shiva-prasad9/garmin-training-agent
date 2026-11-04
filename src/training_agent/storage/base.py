"""Storage stage base class. STUB ONLY."""

from abc import abstractmethod
from datetime import date

from training_agent.core.models import Activity, ActivityDetail, DailyMetrics, PlannedSession
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
    def delete_plan(self, day: date) -> None:
        """Remove the planned sessions stored for one day (used when the athlete changes a choice)."""

    @abstractmethod
    def delete_activity(self, activity_id: str) -> None:
        """Remove one stored activity (used to undo a manual log entry)."""

    @abstractmethod
    def get_plan(self, start: date, end: date) -> list[PlannedSession]:
        """Return stored planned sessions for the inclusive range."""

    @abstractmethod
    def get_metrics(self, start: date, end: date) -> list[DailyMetrics]:
        """Return stored metrics for the inclusive range."""

    @abstractmethod
    def get_activities(self, start: date, end: date, include_duplicates: bool = False) -> list[Activity]:
        """Return stored activities for the inclusive range; a workout present in several sources is returned once
        unless include_duplicates is True."""

    @abstractmethod
    def save_activity_detail(self, detail: ActivityDetail) -> None:
        """Upsert the detail (route, samples) of one workout."""

    @abstractmethod
    def get_activity_detail(self, activity_id: str) -> ActivityDetail | None:
        """Return the stored detail of one workout, or None if it was not downloaded."""
