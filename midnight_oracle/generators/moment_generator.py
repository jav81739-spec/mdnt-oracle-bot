"""Rare, non-spammy Oracle Moment generation."""
from __future__ import annotations
import random

MOMENTS = (
    "☾ Oracle Moment\nThree people here survived a rough day today.\nNo advice. Just: glad you're here.",
    "☾ Tonight's question\nIf your life had a 'previously on…' segment, what would it show?",
    "☾ Small observation\nSome days don't need fixing. They just need to end.",
)


def moment() -> str:
    """Return one original Oracle Moment."""
    return random.choice(MOMENTS)
