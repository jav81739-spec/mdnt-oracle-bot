"""Midnight Oracle runtime compatibility bootstrap.

Keeps the existing Social Engine intact while making its autonomous jobs fan
out to every known group instead of only the single legacy GROUP_CHAT_ID.
This module is imported automatically by Python's site machinery when present.
It does not register Telegram commands or alter /help.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("midnight.autonomous")

try:
    from handlers import social_engine as _se

    _original_w = _se._w

    async def _known_targets() -> list[int]:
        targets: set[int] = set()
        if _se.GROUP_CHAT_ID:
            targets.add(int(_se.GROUP_CHAT_ID))
        try:
            import startup
            registry = await startup.get_chat_registry()
            for cid, info in registry.items():
                if info.get("type") in ("group", "supergroup"):
                    try:
                        targets.add(int(cid))
                    except (TypeError, ValueError):
                        continue
        except Exception as exc:
            log.debug("Could not read chat registry: %s", exc)
        return sorted(targets)

    def _fanout(fn):
        async def job(ctx):
            targets = await _known_targets()
            if not targets:
                log.info("AUTONOMOUS %s skipped: no known group targets", fn.__name__)
                return
            for chat_id in targets:
                await _se._run(ctx.bot, chat_id, fn)
        return job

    _se._w = _fanout
    log.info("Autonomous scheduler bootstrap installed: registry fan-out enabled")
except Exception:
    log.exception("Autonomous scheduler bootstrap could not be installed")
