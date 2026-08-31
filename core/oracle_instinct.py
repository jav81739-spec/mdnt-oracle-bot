"""Oracle Instinct: varied, context-aware and anti-manipulation member selection."""
from __future__ import annotations

import random
import time
from collections import Counter
from typing import Any, Iterable

LENSES = {
    "bond": ("balance", "chemistry", "contrast", "surprise"),
    "ship": ("chemistry", "contrast", "surprise", "balance"),
    "bestie": ("familiarity", "chemistry", "balance", "surprise"),
    "duo": ("complement", "contrast", "balance", "surprise"),
    "matchmaker": ("surprise", "chemistry", "contrast", "complement"),
    "randomship": ("surprise", "contrast", "balance"),
    "oraclepair": ("surprise", "contrast", "chemistry"),
    "friendship": ("familiarity", "chemistry", "balance"),
    "roast": ("playful", "surprise", "activity"),
    "comfort": ("quiet", "familiarity", "balance"),
}

# Message volume is deliberately a weak signal. It must never become a control
# surface where flooding a room guarantees selection.

def _id(member: dict[str, Any]) -> int:
    try:
        return int(member.get("id", 0))
    except (TypeError, ValueError):
        return 0


def _activity(member: dict[str, Any]) -> float:
    return min(1.0, max(0.0, float(member.get("activity_score", 0.0))))


def _fresh_entropy() -> float:
    # SystemRandom is intentionally not seeded from public chat/user identifiers.
    return random.SystemRandom().random()


def _pair_score(a: dict[str, Any], b: dict[str, Any], lens: str) -> float:
    aa, bb = _activity(a), _activity(b)
    contrast = abs(aa - bb)
    balance = 1.0 - contrast
    if lens == "activity": return (aa + bb) / 2
    if lens == "quiet": return 1.0 - (aa + bb) / 2
    if lens == "contrast": return contrast
    if lens == "balance": return balance
    if lens == "surprise": return 0.55 + _fresh_entropy() * 0.45
    if lens == "playful": return min(1.0, 0.35 + (aa + bb) / 3)
    if lens == "familiarity": return min(1.0, 0.25 + (aa + bb) / 3)
    if lens == "chemistry": return 0.55 * balance + 0.45 * (0.5 + _fresh_entropy() / 2)
    if lens == "complement": return 0.7 * contrast + 0.3 * balance
    return 0.5 + _fresh_entropy() * 0.5


def _history(application: Any, chat_id: int) -> list[tuple[int, int]]:
    return application.bot_data.setdefault("oracle_instinct_history", {}).setdefault(str(chat_id), [])


def _strategy_history(application: Any, chat_id: int) -> list[str]:
    return application.bot_data.setdefault("oracle_instinct_strategy_history", {}).setdefault(str(chat_id), [])


def _choose_strategy(application: Any, chat_id: int, kind: str) -> str:
    choices = LENSES.get(kind, ("surprise", "balance", "contrast"))
    history = _strategy_history(application, chat_id)
    recent = Counter(history[-5:])
    weighted = [(lens, 1.0 / (1 + recent[lens])) for lens in choices]
    total = sum(weight for _, weight in weighted)
    pick = random.SystemRandom().random() * total
    for lens, weight in weighted:
        pick -= weight
        if pick <= 0:
            history.append(lens)
            del history[:-12]
            return lens
    return choices[0]


def choose_pair(application: Any, chat_id: int, members: Iterable[dict[str, Any]], kind: str = "bond") -> tuple[dict[str, Any], dict[str, Any]] | None:
    pool = [m for m in members if _id(m) > 0 and not bool(m.get("is_bot", False))]
    if len(pool) < 2:
        return None
    history = _history(application, chat_id)
    recent_pairs = Counter(tuple(sorted(pair)) for pair in history[-24:])
    lens = _choose_strategy(application, chat_id, kind)
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            pair = tuple(sorted((_id(a), _id(b))))
            # Repetition is a strong negative signal, activity is intentionally weak.
            repeat_penalty = min(0.95, 0.28 * recent_pairs.get(pair, 0))
            score = _pair_score(a, b, lens) - repeat_penalty
            scored.append((score, a, b))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    elite = scored[: min(7, len(scored))]
    # Pick among good candidates rather than always exposing the top-ranked pair.
    chosen = random.SystemRandom().choice(elite)
    _, a, b = chosen
    history.append(tuple(sorted((_id(a), _id(b)))))
    del history[:-36]
    return a, b


def choose_one(application: Any, chat_id: int, members: Iterable[dict[str, Any]], kind: str = "surprise") -> dict[str, Any] | None:
    pool = [m for m in members if _id(m) > 0 and not bool(m.get("is_bot", False))]
    if not pool:
        return None
    history = application.bot_data.setdefault("oracle_instinct_single_history", {}).setdefault(str(chat_id), [])
    recent = Counter(history[-18:])
    # First remove recent targets when the room has enough alternatives. This makes
    # repeated commands naturally travel through the room instead of orbiting one user.
    candidates = [m for m in pool if recent.get(_id(m), 0) == 0] or pool
    weights = []
    for member in candidates:
        uid = _id(member)
        freshness = 1.0 / (1.0 + recent.get(uid, 0))
        quiet_bonus = 0.15 if kind in {"comfort", "quiet"} else 0.0
        # Activity contributes only a capped, weak amount.
        weight = max(0.05, freshness + min(0.15, _activity(member) * 0.15) + quiet_bonus)
        weights.append(weight)
    selected = random.SystemRandom().choices(candidates, weights=weights, k=1)[0]
    history.append(_id(selected))
    del history[:-24]
    return selected


def explain_lens(kind: str, application: Any, chat_id: int) -> str:
    """Internal diagnostics only; selection reasoning is never public output."""
    return _strategy_history(application, chat_id)[-1] if _strategy_history(application, chat_id) else LENSES.get(kind, ("surprise",))[0]
