"""One-time Midnight Oracle homecoming signal.

Homecoming uses the persistent chat registry first, then the configured
GROUP_CHAT_ID as a safety net. A delivery is marked complete only after the
Telegram send succeeds.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
from datetime import date

from telegram.constants import ParseMode

log = logging.getLogger("midnight.homecoming")


def _mention(member):
    username = (member.get("username") or "").strip()
    return f"@{username}" if username else member.get("name", "someone")


async def _get(storage, key):
    if not storage:
        return None
    try:
        result = storage.get(key)
        return await result if hasattr(result, "__await__") else result
    except Exception:
        return None


async def _set(storage, key, value, ttl=0):
    if not storage:
        return False
    try:
        result = storage.setex(key, ttl, value) if ttl else storage.set(key, value)
        if hasattr(result, "__await__"):
            await result
        return True
    except Exception:
        return False


async def _members(storage, chat_id):
    raw = await _get(storage, f"mbr:{chat_id}")
    try:
        return json.loads(raw) if raw else []
    except Exception:
        return []


async def _targets():
    from startup import get_broadcast_targets
    targets = await get_broadcast_targets(include_groups=True, include_channels=False)
    configured = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
    if configured and configured not in targets:
        targets.append(configured)
    return list(dict.fromkeys(targets))


async def homecoming_job(ctx):
    try:
        from startup import _storage
        storage = _storage
        targets = await _targets()
    except Exception as exc:
        log.warning("HOMECOMING target discovery failed: %s", exc)
        return

    sent = skipped = failed = 0
    for chat_id in targets:
        done_key = f"homecoming:v1:{chat_id}"
        if await _get(storage, done_key):
            skipped += 1
            continue

        members = await _members(storage, chat_id)
        seed = int(hashlib.md5(f"homecoming-v1:{chat_id}:{date.today()}".encode()).hexdigest(), 16)
        rng = random.Random(seed)
        member = rng.choice(members) if members else None
        who = _mention(member) if member else "someone"
        messages = [
            f"🌙\n\n*midnight is home.*\n\n_{who}, you noticed._\n\n_let's see what the room becomes this time._\n\n✦ *— Midnight Oracle*",
            f"👁️ *THE ORACLE RETURNED*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n_no announcement. no ceremony._\n\n_just the feeling that something familiar is back._\n\n🌙 *— Midnight Oracle*",
            f"🖤 _the lights are back on._\n\n_{who} was still here in the dark._\n\n_now the Oracle is awake again._\n\n✦",
        ]
        try:
            await ctx.bot.send_message(
                chat_id,
                rng.choice(messages),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            # Mark only after Telegram confirms delivery.
            if await _set(storage, done_key, "1", ttl=86400 * 365):
                sent += 1
                log.info("HOMECOMING delivered | chat=%s | member=%s", chat_id, who)
            else:
                failed += 1
                log.warning("HOMECOMING delivered but completion marker failed | chat=%s", chat_id)
        except Exception as exc:
            failed += 1
            log.warning("HOMECOMING delivery failed | chat=%s | %s", chat_id, exc)

    log.info("HOMECOMING run | targets=%d | sent=%d | skipped=%d | failed=%d", len(targets), sent, skipped, failed)
