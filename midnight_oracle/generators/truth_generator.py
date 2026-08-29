"""Original Truth question generator."""
from __future__ import annotations
import random

QUESTIONS = {
    "light": ("What's the last thing you pretended to understand?", "What's a tiny thing that instantly improves your mood?", "What's your most harmless bad habit?"),
    "personal": ("Are you actually happy these days?", "What have you been putting off admitting to yourself?", "What would you change about this month?"),
    "3am": ("What do you miss but refuse to admit?", "What are you pretending doesn't bother you?", "What thought keeps returning when everything gets quiet?"),
    "chaos": ("Who would you absolutely not survive a road trip with?", "What's the funniest hill you'd die on?", "What harmless opinion would start a civil war here?"),
}


def question(level: str = "light") -> str:
    """Return a random original Truth question for a supported level."""
    key = level.casefold().strip()
    if key == "3am": key = "3am"
    if key not in QUESTIONS: key = "light"
    return random.choice(QUESTIONS[key])
