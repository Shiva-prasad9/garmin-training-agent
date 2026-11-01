"""Output stage base class. STUB ONLY."""

from abc import abstractmethod

from training_agent.core.models import DailyBrief
from training_agent.core.plugin import Plugin


class Output(Plugin):
    """Delivers a DailyBrief somewhere (Google Calendar, email, file)."""

    @abstractmethod
    def publish(self, brief: DailyBrief) -> None:
        """Deliver the brief. Must be idempotent for the same date."""
