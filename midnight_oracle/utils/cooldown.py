"""Persistent cooldown coordination."""
from __future__ import annotations

from .logger import get_logger
from ..database import Database, now_ts

log = get_logger("midnight.cooldown")


class CooldownManager:
    """Enforce member, group, serious-conversation, and scheduled-message limits."""

    def __init__(self, db: Database) -> None:
        """Create a cooldown manager backed by SQLite."""
        self.db = db

    async def active(self, scope: str, scope_id: str, kind: str) -> bool:
        """Return whether a named cooldown is active."""
        return await self.db.cooldown_active(scope, scope_id, kind)

    async def set(self, scope: str, scope_id: str, kind: str, seconds: int) -> None:
        """Set a cooldown for the requested number of seconds."""
        await self.db.set_cooldown(scope, scope_id, kind, now_ts() + max(0, seconds))

    async def can_ambient_reply(self, group_id: int, user_id: int) -> tuple[bool, str]:
        """Apply persistent member and group cooldown gates for an ambient reply."""
        gid, uid = str(group_id), str(user_id)
        if await self.active("group", gid, "ambient"):
            return False, "group_cooldown"
        if await self.active("member", f"{gid}:{uid}", "ambient"):
            return False, "member_cooldown"
        if await self.active("group", gid, "serious"):
            return False, "serious_conversation"
        return True, "allowed"
