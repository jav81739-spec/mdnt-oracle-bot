"""Quiet member memory + low-frequency engagement for Midnight Oracle.

The Oracle remembers lightweight identity context (name, username, message count,
last seen) without storing message bodies. Engagement is deliberately rate-limited.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

log = logging.getLogger("midnight.engagement")
TZ = ZoneInfo(os.getenv("ORACLE_TZ", os.getenv("ORACLE_TIMEZONE", "Asia/Kolkata")))
MEMORY_TTL = 86400 * 180

_storage = None

def init_storage(storage):
    global _storage
    _storage = storage

async def _get(key):
    if not _storage:
        return None
    try:
        value = _storage.get(key)
        return await value if asyncio.iscoroutine(value) else value
    except Exception:
        return None

async def _set(key, value, ttl=MEMORY_TTL):
    if not _storage:
        return False
    try:
        result = _storage.setex(key, ttl, value) if ttl else _storage.set(key, value)
        if asyncio.iscoroutine(result):
            await result
        return True
    except Exception:
        return False

async def _members(chat_id):
    raw = await _get(f"mbr:{chat_id}")
    try:
        return json.loads(raw) if raw else []
    except Exception:
        return []

async def remember_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in ("group", "supergroup") or not user or user.is_bot:
        return

    members = await _members(chat.id)
    now = int(time.time())
    username = (user.username or "").strip()
    name = (user.full_name or user.first_name or "someone").strip()[:80]
    found = False
    for member in members:
        if int(member.get("id", 0)) == user.id:
            member["name"] = name
            member["username"] = username
            member["last"] = now
            member["msgs"] = int(member.get("msgs", 0)) + 1
            member.setdefault("first_seen", now)
            found = True
            break
    if not found:
        members.append({
            "id": user.id,
            "name": name,
            "username": username,
            "first_seen": now,
            "last": now,
            "msgs": 1,
        })
    # Keep the most recently active 500 members; names survive for 180 days.
    members = sorted(members, key=lambda x: int(x.get("last", 0)), reverse=True)[:500]
    await _set(f"mbr:{chat.id}", json.dumps(members, ensure_ascii=False), MEMORY_TTL)
    await _set(f"room:last_activity:{chat.id}", str(now), 0)


def _mention(member):
    username = (member.get("username") or "").strip()
    if username:
        return f"@{username}"
    name = member.get("name", "someone").replace("[", "").replace("]", "")
    return f"[{name}](tg://user?id={member.get('id', 0)})"

async def quiet_pulse(ctx: ContextTypes.DEFAULT_TYPE):
    """At most one lightweight social touch per room per day, probabilistically."""
    try:
        from startup import get_broadcast_targets, _storage
        storage = _storage
        targets = await get_broadcast_targets(include_groups=True, include_channels=False)
        configured = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
        if configured and configured not in targets:
            targets.append(configured)
    except Exception as exc:
        log.debug("quiet pulse target discovery failed: %s", exc)
        return

    now = int(time.time())
    for chat_id in targets:
        try:
            last_activity = int(await _get(f"room:last_activity:{chat_id}") or 0)
            if not last_activity or now - last_activity > 86400:
                continue
            day = datetime.now(TZ).date().isoformat()
            key = f"quietpulse:{chat_id}:{day}"
            if await _get(key):
                continue
            # 30% daily chance keeps it feeling organic, not scheduled spam.
            seed = int(hashlib.md5(f"pulse:{chat_id}:{day}".encode()).hexdigest(), 16)
            if seed % 10 >= 3:
                continue
            members = await _members(chat_id)
            active = [m for m in members if now - int(m.get("last", 0)) <= 86400]
            if not active:
                continue
            member = active[seed % len(active)]
            lines = [
                f"🌙 _the room has a memory._\n\n{_mention(member)} — _the Oracle remembers your presence._\n\n✦",
                f"👁️ _some names become familiar without anyone announcing them._\n\n{_mention(member)}. _noted._",
                f"🖤 _quiet observation:_ { _mention(member) } _has been part of today's rhythm._\n\n_that's all. for now._",
            ]
            await ctx.bot.send_message(chat_id, lines[seed % len(lines)], parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            await _set(key, "1", 86400 * 2)
            log.info("QUIET_PULSE sent | chat=%s | member=%s", chat_id, member.get("username") or member.get("name"))
        except Exception as exc:
            log.debug("quiet pulse failed for %s: %s", chat_id, exc)


def register(app: Application):
    app.add_handler(MessageHandler(filters.ALL, remember_member), group=-997)
    if app.job_queue:
        app.job_queue.run_daily(
            quiet_pulse,
            time=datetime.now(TZ).replace(hour=19, minute=30, second=0, microsecond=0).timetz(),
            name="quiet_member_pulse",
        )
        log.info("Quiet member engagement registered (19:30 local, probabilistic daily cap)")
