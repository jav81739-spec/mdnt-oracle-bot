"""Oracle Instinct: context-aware, anti-repeat member selection.

Selection is deliberately different from a single random sampler.  It uses only
member signals already legitimately observed by the bot, applies command-specific
lenses, remembers recent choices, and keeps activity volume from becoming a direct
selection control.
"""
from __future__ import annotations

import hashlib
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


def _stable_seed(*parts: Any) -> int:
    raw = "|".join(map(str, parts))
    return int(hashlib.sha256(raw.encode()).hexdigest(), 16)


def _id(member: dict[str, Any]) -> int:
    return int(member.get("id", 0))


def _activity(member: dict[str, Any]) -> float:
    # Message volume is bounded so flooding cannot dominate selection.
    return min(1.0, max(0.0, float(member.get("activity_score", 0.0))))


def _pair_score(a: dict[str, Any], b: dict[str, Any], lens: str) -> float:
    aa, bb = _activity(a), _activity(b)
    if lens == "activity":
        return (aa + bb) / 2
    if lens == "quiet":
        return 1.0 - min(1.0, (aa + bb) / 2)
    if lens == "contrast":
        return abs(aa - bb)
    if lens == "balance":
        return 1.0 - abs(aa - bb)
    if lens == "surprise":
        return 1.0 - min(1.0, abs(aa - bb) * 0.7 + (aa + bb) * 0.15)
    if lens == "playful":
        return min(1.0, 0.35 + (aa + bb) / 2)
    if lens == "familiarity":
        return min(1.0, 0.25 + (aa + bb) / 2)
    if lens == "chemistry":
        return 1.0 - abs(aa - bb) * 0.55
    if lens == "complement":
        return abs(aa - bb) * 0.7 + (1.0 - abs(aa - bb)) * 0.3
    return 0.5


def _history(application: Any, chat_id: int) -> list[tuple[int, int]]:
    root = application.bot_data.setdefault("oracle_instinct_history", {})
    return root.setdefault(str(chat_id), [])


def choose_pair(application: Any, chat_id: int, members: Iterable[dict[str, Any]], kind: str = "bond") -> tuple[dict[str, Any], dict[str, Any]] | None:
    pool = [m for m in members if _id(m) > 0 and not bool(m.get("is_bot", False))]
    if len(pool) < 2:
        return None
    history = _history(application, chat_id)
    recent = {tuple(sorted(pair)) for pair in history[-18:]}
    lenses = LENSES.get(kind, ("surprise", "balance", "contrast"))
    seed = _stable_seed(chat_id, kind, int(time.time() // 900), len(history))
    rng = random.Random(seed)
    lens = lenses[rng.randrange(len(lenses))]
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            pair = tuple(sorted((_id(a), _id(b))))
            repeat_penalty = 0.65 if pair in recent else 0.0
            score = _pair_score(a, b, lens) - repeat_penalty
            # Small deterministic jitter prevents identical score ties from producing
            # a visible ordering while remaining testable.
            score += (rng.random() - 0.5) * 0.12
            scored.append((score, a, b))
    scored.sort(key=lambda item: item[0], reverse=True)
    # Sample from a narrow elite set rather than always taking rank one.
    elite = scored[: min(5, len(scored))]
    _, a, b = elite[rng.randrange(len(elite))]
    history.append(tuple(sorted((_id(a), _id(b)))))
    del history[:-24]
    return a, b


def choose_one(application: Any, chat_id: int, members: Iterable[dict[str, Any]], kind: str = "surprise") -> dict[str, Any] | None:
    pool = [m for m in members if _id(m) > 0 and not bool(m.get("is_bot", False))]
    if not pool:
        return None
    history = application.bot_data.setdefault("oracle_instinct_single_history", {}).setdefault(str(chat_id), [])
    seed = _stable_seed(chat_id, kind, int(time.time() // 900), len(history))
    rng = random.Random(seed)
    recent = set(history[-12:])
    candidates = [m for m in pool if _id(m) not in recent] or pool
    selected = rng.choice(candidates)
    history.append(_id(selected))
    del history[:-18]
    return selected


def explain_lens(kind: str, application: Any, chat_id: int) -> str:
    # Internal diagnostics only; never expose the selection score or lens to members.
    history = _history(application, chat_id)
    return LENSES.get(kind, ("surprise",))[len(history) % len(LENSES.get(kind, ("surprise",)))]
