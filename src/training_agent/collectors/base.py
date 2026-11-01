"""Collector stage base class. STUB ONLY."""

from abc import abstractmethod
from datetime import date

from training_agent.core.models import Activity, DailyMetrics
from training_agent.core.plugin import Plugin


class Collector(Plugin):
    """Pulls data from one source and returns it as shared models.

    Collectors never write to data/raw/ destructively and never touch storage.
    """

    @abstractmethod
    def collect_metrics(self, start: date, end: date) -> list[DailyMetrics]:
        """Return DailyMetrics for the inclusive date range."""

    @abstractmethod
    def collect_activities(self, start: date, end: date) -> list[Activity]:
        """Return Activities for the inclusive date range."""
