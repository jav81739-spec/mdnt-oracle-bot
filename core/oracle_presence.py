"""Unified presence intelligence for Midnight Oracle.

This module decides whether Oracle has a worthwhile reason to appear. It deliberately
uses only public room activity already captured by the runtime: no hidden surveillance,
private-message mining, or member-memory scoring.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PresenceDecision:
    speak: bool
    score: float
    reason: str
    strategy: str


def _stable_noise(*parts: Any) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def decide_presence(
    *,
    group_id: int,
    now: float,
    active_count: int,
    context_items: list[dict[str, Any]],
    last_delivery: float | None,
    cooldown_seconds: float,
) -> PresenceDecision:
    """Return a contextual decision rather than a fixed probability timer.

    The score combines room life, conversational material, recency, and controlled
    novelty. It is intentionally conservative: silence wins when there is no reason
    to add value.
    """
    if active_count < 2:
        return PresenceDecision(False, 0.0, "room-too-quiet", "silence")
    if last_delivery is not None and now - float(last_delivery) < cooldown_seconds:
        return PresenceDecision(False, 0.0, "cooldown", "silence")

    recent = [x for x in context_items[-8:] if str(x.get("text", "")).strip()]
    context_score = min(0.34, 0.08 * min(len(recent), 4))
    people_score = min(0.20, 0.04 * min(active_count, 5))

    age_score = 0.0
    if recent:
        newest = max(float(x.get("ts", now)) for x in recent)
        age = max(0.0, now - newest)
        if age <= 20 * 60:
            age_score = 0.18
        elif age <= 90 * 60:
            age_score = 0.08

    diversity = len({str(x.get("text", "")).casefold()[:80] for x in recent})
    diversity_score = min(0.14, diversity * 0.025)
    novelty = _stable_noise(group_id, int(now // (15 * 60)), len(recent)) * 0.18

    score = min(1.0, 0.16 + context_score + people_score + age_score + diversity_score + novelty)
    threshold = 0.56 if recent else 0.76
    speak = score >= threshold

    if recent and age_score >= 0.18:
        reason = "fresh-room-context"
    elif diversity >= 3:
        reason = "varied-room-context"
    elif active_count >= 4:
        reason = "lively-room"
    else:
        reason = "oracle-opportunity"

    strategies = ("story", "curiosity", "playful_observation", "gossip")
    index = int(_stable_noise(group_id, int(now // (15 * 60)), reason) * len(strategies))
    strategy = strategies[min(index, len(strategies) - 1)] if speak else "silence"
    return PresenceDecision(speak, score, reason if speak else "not-worth-interrupting", strategy)
