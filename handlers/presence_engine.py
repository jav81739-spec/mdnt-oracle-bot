"""
handlers/presence_engine.py — Midnight Oracle | Presence Engine

Presence is social context, not surveillance. Oracle may celebrate a return,
a first hello, or a genuine milestone, but it never claims to watch, scan,
record, archive, or read someone's private history.
"""
from __future__ import annotations
import json
import logging
import os
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, Bot
from telegram.ext import ContextTypes, MessageHandler, filters

from handlers.social_engine import _get, _set, _post, _handle, _m, GROUP_CHAT_ID

log = logging.getLogger("midnight.presence")
ORACLE_TZ = ZoneInfo(os.getenv("ORACLE_TZ", "Asia/Kolkata"))


async def _get_member_meta(chat_id, uid):
    raw = await _get(f"presence:{chat_id}:{uid}")
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


async def _set_member_meta(chat_id, uid, data):
    await _set(f"presence:{chat_id}:{uid}", json.dumps(data), ttl=86400 * 60)


def _now_ts():
    return int(datetime.now(ORACLE_TZ).timestamp())


async def _notice_return(bot: Bot, chat_id: int, member: dict, days_gone: int):
    h = _handle(member)
    choices = [
        f"🌙 {h} is back.\n\nNo questions. Just good to see you again.",
        f"oh — {h} is here again.\n\nwelcome back. ✦",
        f"{h} returned after a little while.\n\nSome absences make a hello feel warmer. 🌙",
        f"there you are, {h}.\n\nThe room feels a little more complete.",
    ]
    await _post(bot, chat_id, random.choice(choices))


async def _notice_first_message(bot: Bot, chat_id: int, member: dict):
    h = _handle(member)
    choices = [
        f"🌙 welcome, {h}.\n\nYou've officially said hello. That's enough for an entrance.",
        f"{h} has entered the conversation. ✦\n\nTake your time. You'll find your rhythm.",
        f"oh, hello {h}.\n\nNow let's see what kind of chaos you bring. 😌",
        f"🌙 {h} — welcome in.\n\nNo ceremony. Just make yourself at home.",
    ]
    await _post(bot, chat_id, random.choice(choices))


async def _notice_milestone(bot: Bot, chat_id: int, member: dict, count: int):
    h = _handle(member)
    choices = [
        f"✦ {h} just crossed {count} messages here.\n\nThat's a proper little chapter.",
        f"{count} messages, {h}. 🌙\n\nAt this point, you're part of the furniture.",
        f"hey {h} — {count} already?\n\nYou've definitely left a little personality in this place.",
        f"🌙 {h} hit {count}.\n\nSomewhere along the way, this stopped being just another group.",
    ]
    await _post(bot, chat_id, random.choice(choices))


async def _notice_silence(bot: Bot, chat_id: int, member: dict, days: int):
    h = _handle(member)
    choices = [
        f"🌑 {h} has been quiet for a while.\n\nHope life is treating you kindly.",
        f"{h}, whenever you wander back in — the door's open. 🌙",
        f"quiet corner reserved for {h}.\n\nNo pressure. Just a little hello from Midnight.",
    ]
    await _post(bot, chat_id, random.choice(choices))


MILESTONES = {50, 100, 250, 500, 1000}


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or user.is_bot:
        return
    if chat.type not in ("group", "supergroup"):
        return

    uid = user.id
    cid = chat.id
    now = _now_ts()
    member = {
        "id": uid,
        "name": user.first_name or "someone",
        "username": user.username or "",
    }

    meta = await _get_member_meta(cid, uid)
    is_new = not meta
    last_seen = meta.get("last_seen", 0)
    msg_count = meta.get("msg_count", 0) + 1
    days_gone = (now - last_seen) // 86400 if last_seen else 0
    meta.update({"last_seen": now, "msg_count": msg_count})
    await _set_member_meta(cid, uid, meta)

    try:
        if is_new and msg_count == 1:
            if random.random() < 0.25:
                await _notice_first_message(context.bot, cid, member)
            return

        if not is_new and days_gone >= 7:
            done_key = f"return_notice:{cid}:{uid}:{now // 86400}"
            if not await _get(done_key):
                await _set(done_key, "1", ttl=86400 * 2)
                await _notice_return(context.bot, cid, member, days_gone)
            return

        if msg_count in MILESTONES:
            done_key = f"milestone:{cid}:{uid}:{msg_count}"
            if not await _get(done_key):
                await _set(done_key, "1", ttl=86400 * 365)
                await _notice_milestone(context.bot, cid, member, msg_count)
    except Exception as e:
        log.debug("Presence notice error: %s", e)


async def silence_check(context):
    if not GROUP_CHAT_ID:
        return
    bot = context.bot
    cid = GROUP_CHAT_ID

    from handlers.social_engine import _members
    ms = await _members(cid)
    now = _now_ts()

    from datetime import date
    done_key = f"silence_check:{cid}:{date.today()}"
    if await _get(done_key):
        return
    await _set(done_key, "1", ttl=86400)

    candidates = [
        m for m in ms
        if 5 * 86400 <= now - m.get("last", 0) <= 14 * 86400
        and m.get("msgs", 0) > 5
    ]
    if not candidates or random.random() > 0.15:
        return

    member = random.choice(candidates)
    days = (now - member.get("last", 0)) // 86400
    done_key2 = f"silence:{cid}:{member['id']}:{date.today()}"
    if await _get(done_key2):
        return
    await _set(done_key2, "1", ttl=86400 * 3)
    await _notice_silence(bot, cid, member, days)


def register(app):
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_message),
        group=-997,
    )
