"""Canonical delivery bridge for Oracle-generated experiences."""
from __future__ import annotations

from typing import Any


async def deliver(application: Any, chat_id: int, text: str) -> bool:
    """Use the existing Social Engine posting path for generated Oracle content."""
    from handlers.social_engine import _post

    try:
        await _post(application.bot, chat_id, text)
        return True
    except Exception:
        return False
