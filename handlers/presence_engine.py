"""
handlers/presence_engine.py — Midnight Oracle | Presence Engine

The oracle notices:
  — who has returned after being gone
  — who has been unusually active
  — who has gone quiet
  — who just had their first message (new member welcome)
  — member milestones (100th message, streak days)

This makes members feel *seen*.
That's the whole point.
"""
from __future__ import annotations
import asyncio, json, logging, os, random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters

from handlers.social_engine import _get, _set, _post, _handle, _m, _n, GROUP_CHAT_ID

log = logging.getLogger("midnight.presence")
ORACLE_TZ = ZoneInfo(os.getenv("ORACLE_TZ", "Asia/Kolkata"))

SEP = "┄" * 18

# ── helpers ────────────────────────────────────────────────────────────────────
async def _get_member_meta(chat_id, uid):
    raw = await _get(f"presence:{chat_id}:{uid}")
    try: return json.loads(raw) if raw else {}
    except: return {}

async def _set_member_meta(chat_id, uid, data):
    await _set(f"presence:{chat_id}:{uid}", json.dumps(data), ttl=86400*60)

def _now_ts():
    return int(datetime.now(ORACLE_TZ).timestamp())


# ══════════════════════════════════════════════════════════════════════════════
#  REACTIVE NOTICES — triggered by real messages, not schedule
# ══════════════════════════════════════════════════════════════════════════════

async def _notice_return(bot: Bot, chat_id: int, member: dict, days_gone: int):
    rng   = random.Random(_now_ts() // 3600)
    h     = _handle(member)
    msgs  = [
        f"👁️ _the oracle notices {_m(member)} has returned after {days_gone} days._\n\n_it doesn't ask where they were. it only says: you're back._\n\n*— Midnight Oracle*",
        f"🌙\n\n_{h} is back._\n\n_the oracle noticed the absence.\nand now it notices the return._\n\n👁️ *— Midnight*",
        f"_the group just shifted slightly._\n_{h} came back.\nthe oracle registered it._\n\n✦ *— Midnight Oracle*",
        f"👁️ *RETURN NOTICED*\n{SEP}\n\n_{h}._\n\n_the oracle tracked the gap.\nit's glad it's closing._\n\n*— Midnight Oracle*",
    ]
    await _post(bot, chat_id, rng.choice(msgs))

async def _notice_first_message(bot: Bot, chat_id: int, member: dict):
    rng = random.Random(_now_ts() // 3600)
    h   = _handle(member)
    msgs = [
        f"👁️ _the oracle registers {_m(member)} for the first time._\n\n_welcome to the group. the oracle is watching now._\n\n*— Midnight Oracle*",
        f"🌙 _a new presence enters._\n\n_{h}._\n\n_the oracle sees you.\nlet's see what you bring._\n\n✦ *— Midnight Oracle*",
        f"✦\n\n_{h} has arrived._\n\n_the oracle updates its records.\nyou're in the archive now._\n\n👁️ *— Midnight Oracle*",
    ]
    await _post(bot, chat_id, rng.choice(msgs))

async def _notice_milestone(bot: Bot, chat_id: int, member: dict, count: int):
    rng = random.Random(_now_ts() // 3600)
    h   = _handle(member)
    msgs = [
        f"📡 _the oracle registers milestone:_\n\n_{h} — {count} messages in this group._\n\n_the oracle has read all of them.\nsome of them twice._\n\n*— Midnight Oracle*",
        f"✦ *ORACLE MILESTONE*\n{SEP}\n\n_{h}: {count} messages and counting._\n\n_the oracle has been watching the whole time.\nit finds {h} interesting._\n\n*— 👁️*",
    ]
    await _post(bot, chat_id, rng.choice(msgs))

async def _notice_silence(bot: Bot, chat_id: int, member: dict, days: int):
    rng = random.Random(_now_ts() // 3600)
    h   = _handle(member)
    msgs = [
        f"🌑 _{h} has been quiet for {days} days._\n_the oracle notices silence too._\n\n*— Midnight Oracle*",
        f"👁️ _the oracle is aware that {_m(member)} hasn't spoken in {days} days._\n_it's not asking why. just noting._\n\n*— Midnight*",
        f"🌑\n\n_{h}._\n\n_the oracle noticed you went quiet.\nno pressure. it just notices everything._\n\n*— Midnight Oracle*",
    ]
    await _post(bot, chat_id, rng.choice(msgs))


# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER — runs on every group message
# ══════════════════════════════════════════════════════════════════════════════

# Milestone counts that trigger a notice
MILESTONES = {50, 100, 250, 500, 1000}

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or user.is_bot: return
    if chat.type not in ("group","supergroup"): return

    uid     = user.id
    cid     = chat.id
    now     = _now_ts()
    member  = {
        "id":       uid,
        "name":     user.first_name or "someone",
        "username": user.username or "",
    }

    meta = await _get_member_meta(cid, uid)
    is_new = not meta

    last_seen = meta.get("last_seen", 0)
    msg_count = meta.get("msg_count", 0) + 1
    days_gone = (now - last_seen) // 86400 if last_seen else 0

    # Update meta
    meta.update({"last_seen": now, "msg_count": msg_count})
    await _set_member_meta(cid, uid, meta)

    # ── Notices ─────────────────────────────────────────────────────────────
    try:
        # First ever message
        if is_new and msg_count == 1:
            # Don't spam on every first message — only 40% chance
            if random.random() < 0.40:
                await _notice_first_message(context.bot, cid, member)
            return

        # Return after long absence (7+ days)
        if not is_new and days_gone >= 7:
            # Only fire once per return window
            done_key = f"return_notice:{cid}:{uid}:{now//86400}"
            if not await _get(done_key):
                await _set(done_key, "1", ttl=86400*2)
                await _notice_return(context.bot, cid, member, days_gone)
            return

        # Message milestones
        if msg_count in MILESTONES:
            done_key = f"milestone:{cid}:{uid}:{msg_count}"
            if not await _get(done_key):
                await _set(done_key, "1", ttl=86400*365)
                await _notice_milestone(context.bot, cid, member, msg_count)

    except Exception as e:
        log.debug("Presence notice error: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULED SILENCE CHECK — daily job
#  Oracle notices members who've been quiet 5+ days
# ══════════════════════════════════════════════════════════════════════════════

async def silence_check(context):
    if not GROUP_CHAT_ID: return
    bot = context.bot
    cid = GROUP_CHAT_ID

    from handlers.social_engine import _members
    ms = await _members(cid)
    now = _now_ts()

    # Only check once per day
    from datetime import date
    done_key = f"silence_check:{cid}:{date.today()}"
    raw = await _get(done_key)
    if raw: return
    await _set(done_key, "1", ttl=86400)

    # Find one member who's been quiet 5-14 days
    candidates = [
        m for m in ms
        if 5*86400 <= now - m.get("last", 0) <= 14*86400
        and m.get("msgs", 0) > 5  # was active before
    ]
    if not candidates: return

    member = random.choice(candidates)
    days   = (now - member.get("last", 0)) // 86400

    # Only fire 25% of days to not be annoying
    if random.random() > 0.25: return

    done_key2 = f"silence:{cid}:{member['id']}:{date.today()}"
    if await _get(done_key2): return
    await _set(done_key2, "1", ttl=86400*3)

    await _notice_silence(bot, cid, member, days)


def register(app):
    from telegram.ext import MessageHandler, filters
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_message),
        group=-997
    )
