"""Lightweight, non-clinical mood estimation for conversational tone."""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque


@dataclass(frozen=True)
class MoodSignal:
    """Describe conversational energy without making a mental-health diagnosis."""
    energy: float
    humour: float
    social: float
    stress: float
    playful: float

    def summary(self) -> str:
        """Return a compact tone summary for a reply generator."""
        if self.stress >= .65:
            return "stressed; warm and serious"
        if self.playful >= .65 or self.humour >= .65:
            return "playful; light banter fits"
        if self.energy < .35:
            return "low-energy; gentle tone fits"
        return "balanced; natural conversational tone"


class MoodEngine:
    """Estimate member and group conversational tone from recent text."""

    def __init__(self, window: int = 10) -> None:
        """Create an estimator with a bounded rolling window."""
        self._window = max(1, window)
        self._members: dict[tuple[int, int], deque[MoodSignal]] = {}
        self._groups: dict[int, deque[MoodSignal]] = {}

    def estimate(self, text: str) -> MoodSignal:
        """Estimate tone from lexical and punctuation cues."""
        low = (text or "").casefold()
        humour = min(1.0, sum(low.count(x) for x in ("haha", "lol", "😂", "🤣", "💀")) * .22)
        stress = min(1.0, sum(low.count(x) for x in ("tired", "thak", "stress", "worried", "darr", "scared", "fed up", "nahi ho")) * .28)
        social = min(1.0, .2 + sum(low.count(x) for x in ("bhai", "bro", "yaar", "guys", "anyone", "someone")) * .2 + (.2 if "?" in text else 0))
        playful = min(1.0, humour * .8 + (.2 if "!" in text else 0))
        energy = max(0.0, min(1.0, .55 + playful * .3 - stress * .35))
        return MoodSignal(energy, humour, social, stress, playful)

    def observe(self, user_id: int, group_id: int, text: str) -> MoodSignal:
        """Record a member signal and return it."""
        signal = self.estimate(text)
        self._members.setdefault((user_id, group_id), deque(maxlen=self._window)).append(signal)
        self._groups.setdefault(group_id, deque(maxlen=self._window)).append(signal)
        return signal

    def member_mood(self, user_id: int, group_id: int) -> MoodSignal:
        """Return the rolling member mood or a neutral signal."""
        return self._average(self._members.get((user_id, group_id)))

    def group_mood(self, group_id: int) -> MoodSignal:
        """Return the rolling group mood or a neutral signal."""
        return self._average(self._groups.get(group_id))

    @staticmethod
    def _average(items: deque[MoodSignal] | None) -> MoodSignal:
        """Average a bounded sequence of mood signals."""
        if not items:
            return MoodSignal(.5, .2, .3, .2, .2)
        n = len(items)
        return MoodSignal(*(sum(getattr(x, f) for x in items) / n for f in ("energy", "humour", "social", "stress", "playful")))
