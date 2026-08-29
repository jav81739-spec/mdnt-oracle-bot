"""Central delivery governor for Midnight Oracle autonomous features.

Keeps many autonomous features feeling like one quiet presence:
- targets every registered group plus GROUP_CHAT_ID fallback
- enforces per-room speaking cooldown
- prevents a single feature from spamming a room
- makes _done transactional: completion is recorded only after a successful send
- leaves public commands/help untouched
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import os
import time

log = logging.getLogger("midnight.governor")

_ROOM_COOLDOWN = int(os.getenv("ORACLE_ROOM_COOLDOWN", "1800") or "1800")
_FEATURE_COOLDOWN = int(os.getenv("ORACLE_FEATURE_COOLDOWN", "300") or "300")

_pending_done: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar("oracle_pending_done", default=None)


def install(engine):
    """Patch the already-imported social engine without replacing its feature code."""
    if getattr(engine, "_governor_installed", False):
        return

    original_post = engine._post
    original_done = engine._done
    original_w = engine._w

    async def guarded_done(key, ttl):
        if await original_done.__wrapped__(key, ttl) if hasattr(original_done, "__wrapped__") else False:
            return True
        # We don't use the original implementation because it marks before send.
        if await engine._get(key):
            return True
        pending = _pending_done.get()
        if pending is None:
            pending = set()
            _pending_done.set(pending)
        pending.add((key, ttl))
        return False

    # Replace _done with a check-only reservation. Successful _post commits it.
    async def check_done(key, ttl):
        if await engine._get(key):
            return True
        pending = _pending_done.get()
        if pending is None:
            pending = set()
            _pending_done.set(pending)
        pending.add((key, ttl))
        return False

    async def governed_post(bot, chat_id, text):
        """Send first; only then persist pending completion keys."""
        try:
            await bot.send_message(
                chat_id, text,
                parse_mode=engine.ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            sent = True
        except Exception:
            try:
                clean = engine.re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
                for c in ["*", "_", "`"]:
                    clean = clean.replace(c, "")
                await bot.send_message(chat_id, clean, disable_web_page_preview=True)
                sent = True
            except Exception as exc:
                log.warning("AUTONOMOUS_SEND_FAILED | chat=%s | %s", chat_id, exc)
                sent = False

        if sent:
            pending = _pending_done.get()
            if pending:
                for key, ttl in list(pending):
                    await engine._set(key, "1", ttl=ttl)
                pending.clear()
            now = int(time.time())
            await engine._set(f"oracle:last_speak:{chat_id}", str(now), ttl=86400 * 7)
            log.info("AUTONOMOUS_SENT | chat=%s", chat_id)
        return sent

    async def room_allowed(chat_id):
        raw = await engine._get(f"oracle:last_speak:{chat_id}")
        try:
            return int(time.time()) - int(raw or 0) >= _ROOM_COOLDOWN
        except Exception:
            return True

    async def governed_w(bot, fn):
        """Run one autonomous feature across all known rooms, not one room only."""
        try:
            from startup import get_broadcast_targets
            targets = await get_broadcast_targets(include_groups=True, include_channels=False)
        except Exception as exc:
            log.warning("AUTONOMOUS_TARGET_DISCOVERY_FAILED | %s", exc)
            targets = []
        configured = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
        if configured and configured not in targets:
            targets.append(configured)

        sent = 0
        skipped = 0
        for chat_id in dict.fromkeys(targets):
            if not await room_allowed(chat_id):
                skipped += 1
                continue
            try:
                await fn(bot, chat_id)
                sent += 1
            except Exception as exc:
                log.warning("AUTONOMOUS_FEATURE_FAILED | feature=%s | chat=%s | %s", fn.__name__, chat_id, exc)
        log.info("AUTONOMOUS_RUN | feature=%s | targets=%d | attempted=%d | skipped=%d", fn.__name__, len(targets), sent + skipped, skipped)

    engine._done = check_done
    engine._post = governed_post
    engine._w = governed_w
    engine._governor_installed = True
    log.info("Oracle delivery governor installed | room_cooldown=%ss", _ROOM_COOLDOWN)
