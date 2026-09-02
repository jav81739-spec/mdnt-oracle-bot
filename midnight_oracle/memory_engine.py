"""Bounded, consent-oriented member memory."""
from __future__ import annotations
import re
from dataclasses import dataclass
from .config import MEMORY_INTEREST_LIMIT, MEMORY_THEME_LIMIT, MEMORY_WORRY_LIMIT, MEMORY_WIN_LIMIT, MEMORY_JOKE_LIMIT
from .database import Database


@dataclass(frozen=True)
class MemberMemory:
    """A compact view of memories safe to surface conversationally."""
    preferred_name: str
    relationship_tier: str
    interests: tuple[str, ...]
    themes: tuple[str, ...]
    worries: tuple[str, ...]
    wins: tuple[str, ...]
    jokes: tuple[str, ...]


class MemoryEngine:
    """Manage bounded member memories without storing full chat transcripts."""

    _SENSITIVE = re.compile(r"\b(password|otp|one[- ]time password|token|api key|secret|seed phrase|private key|upi|account number|card number|cvv|pin)\b", re.I)
    _NOISY = re.compile(r"^(lol+|haha+|hahaha+|ok+|okay+|hmm+|yes+|no+|bro+|bhai+|guys+|wtf+|lmao+)[!? .]*$", re.I)

    def __init__(self, db: Database) -> None:
        self.db = db

    async def observe(self, user_id: int, group_id: int, name: str, text: str, meaningful: bool) -> None:
        """Record bounded relationship state and only durable, non-sensitive memory signals."""
        await self.db.upsert_member(user_id, group_id, "", name)
        await self.db.increment_interaction(user_id, group_id)
        row = await self.db.fetchone("SELECT interaction_count FROM members WHERE user_id=? AND group_id=?", (user_id, group_id))
        count = int(row[0]) if row else 1
        await self.db.execute("UPDATE members SET relationship_tier=? WHERE user_id=? AND group_id=?", (self.relationship_tier(count), user_id, group_id))
        if not meaningful:
            return
        value = " ".join((text or "").split()).strip()
        if len(value) < 12 or len(value) > 240 or self._SENSITIVE.search(value) or self._NOISY.fullmatch(value):
            return
        low = value.casefold()
        if any(x in low for x in ("i like ", "i love ", "mera favourite", "my favorite", "my favourite", "i enjoy ")):
            await self.db.add_memory(user_id, group_id, "interest", value)
        if any(x in low for x in ("worried", "tension", "stress", "darr", "scared", "nervous", "anxious")):
            await self.db.add_memory(user_id, group_id, "worry", value)
        if any(x in low for x in ("ho gaya", "finally", "cleared", "done", "got it", "mil gaya", "passed")):
            await self.db.add_memory(user_id, group_id, "win", value)
        if any(x in low for x in ("haha", "lol", "😂", "🤣", "💀")) and len(value) <= 120:
            await self.db.add_memory(user_id, group_id, "joke", value)
        # Themes are durable topics, not a transcript. Only keep messages that look like
        # an actual topic or preference and never store arbitrary conversational chatter.
        if any(marker in low for marker in ("i'm into ", "i am into ", "these days", "lately", "working on ", "learning ", "watching ", "playing ", "trying to ")):
            await self.db.add_memory(user_id, group_id, "theme", value)

    async def get(self, user_id: int, group_id: int) -> MemberMemory:
        """Load a bounded memory profile for a member."""
        member = await self.db.fetchone("SELECT preferred_name,relationship_tier FROM members WHERE user_id=? AND group_id=?", (user_id, group_id))
        name = str(member[0] if member else "")
        tier = str(member[1] if member else "new")
        return MemberMemory(name, tier, tuple(await self.db.memories(user_id, group_id, "interest", MEMORY_INTEREST_LIMIT)), tuple(await self.db.memories(user_id, group_id, "theme", MEMORY_THEME_LIMIT)), tuple(await self.db.memories(user_id, group_id, "worry", MEMORY_WORRY_LIMIT)), tuple(await self.db.memories(user_id, group_id, "win", MEMORY_WIN_LIMIT)), tuple(await self.db.memories(user_id, group_id, "joke", MEMORY_JOKE_LIMIT)))

    async def forget(self, user_id: int, group_id: int, term: str) -> int:
        """Deactivate memories matching the requested term."""
        return await self.db.delete_memories_matching(user_id, group_id, term.strip()[:100])

    @staticmethod
    def relationship_tier(interactions: int) -> str:
        """Map interaction count to bounded relationship tiers."""
        if interactions <= 3: return "new"
        if interactions <= 10: return "familiar"
        if interactions <= 30: return "regular"
        if interactions <= 75: return "known"
        return "close"
