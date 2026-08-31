"""Shared contract between Oracle Presence, Mind, Freshness, Social Engine and delivery."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OracleStrategy:
    """Immutable intent produced by Presence and consumed by the Oracle pipeline."""

    strategy: str
    reason: str
    language: str
    target_policy: str = "room"
    media_intent: str = "none"
    interaction: str = "creative"
    metadata: dict[str, Any] = field(default_factory=dict)


STRATEGY_MAP = {
    "story": ("story", "creative"),
    "gossip": ("gossip", "creative"),
    "curiosity": ("curiosity", "creative"),
    "playful_observation": ("playful_observation", "creative"),
}


def build_strategy(decision: Any, language: str) -> OracleStrategy:
    strategy = str(getattr(decision, "strategy", "curiosity") or "curiosity")
    interaction, _ = STRATEGY_MAP.get(strategy, ("creative", "creative"))
    return OracleStrategy(
        strategy=strategy,
        reason=str(getattr(decision, "reason", "fresh_room_moment") or "fresh_room_moment"),
        language=language,
        target_policy="room",
        media_intent="contextual" if strategy in {"story", "gossip"} else "none",
        interaction=interaction,
    )
