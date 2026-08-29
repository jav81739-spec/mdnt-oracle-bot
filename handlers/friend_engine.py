"""Low-noise friend layer for Midnight Oracle."""
from __future__ import annotations

import logging
import os
import random
from datetime import time
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

log = logging.getLogger("midnight.friend")
TZ = ZoneInfo(os.getenv("ORACLE_TIMEZONE", "Asia/Kolkata"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or "0")

MORNING = [
    "☀️ Good morning, {name}. Honestly — how are you?",
    "☕ Morning, {name}. Actually okay, or just functioning?",
    "🌤 New day, {name}. What's your real status today?",
]
EVENING = [
    "🌆 Day's almost done, {name}. What was the realest part of today?",
    "☾ Evening check, {name}. Did today treat you well?",
    "🕯 Before the day disappears: are you actually okay, {name}?",
]
NIGHT = [
    "☾ 03:00 question, {name}: what's something you'd only admit at this hour?",
    "🌙 Still awake, {name}? No advice tonight. Just talk.",
    "☾ Quiet room, {name}. What's been sitting in your head lately?",
]


def _keyboard():
    """Build the small mood keyboard used by scheduled friend check-ins."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🙂 I'm okay", callback_data="oracle:mood:okay"), InlineKeyboardButton("🥲 Not really", callback_data="oracle:mood:rough")],
        [InlineKeyboardButton("🔥 Great", callback_data="oracle:mood:great"), InlineKeyboardButton("🤐 Later", callback_data="oracle:mood:later")],
    ])


async def _recent_member() -> dict | None:
    """Return the most recently active known member for the configured group."""
    if not GROUP_CHAT_ID:
        log.info("AUTONOMOUS_MEMBER_SKIP | reason=group_not_configured")
        return None
    try:
        from handlers import social_engine
        members = await social_engine._members(GROUP_CHAT_ID)
        return max(members, key=lambda m: m.get("last", 0)) if members else None
    except Exception:
        log.exception("FRIEND_MEMBER_LOOKUP_FAILED")
        return None


async def _send(kind: str, templates: list[str], context: ContextTypes.DEFAULT_TYPE):
    """Send one scheduled friend check-in when the group is eligible."""
    log.info("AUTONOMOUS_JOB_ENTERED | feature=friend_%s", kind)
    if not GROUP_CHAT_ID:
        log.info("AUTONOMOUS_JOB_SKIPPED | feature=friend_%s | reason=group_not_configured", kind)
        return
    try:
        from handlers import social_engine
        key = f"friend:{GROUP_CHAT_ID}:{kind}"
        if await social_engine._done(key, 18 * 3600):
            log.info("AUTONOMOUS_JOB_SKIPPED | feature=friend_%s | reason=cooldown", kind)
            return
        member = await _recent_member()
        if not member:
            log.info("AUTONOMOUS_JOB_SKIPPED | feature=friend_%s | reason=no_recent_member", kind)
            return
        name = (member.get("name") or "friend")[:60]
        text = random.choice(templates).format(name=name)
        log.info("AUTONOMOUS_RUN | feature=friend_%s | member=%s", kind, name)
        await context.bot.send_message(GROUP_CHAT_ID, text, reply_markup=_keyboard())
        log.info("AUTONOMOUS_SENT | feature=friend_%s | member=%s", kind, name)
        log.info("FRIEND_CHECKIN_SENT | kind=%s | member=%s", kind, name)
    except Exception:
        log.exception("AUTONOMOUS_FAILED | feature=friend_%s", kind)


async def morning(context):
    """Run the morning friend check-in job."""
    await _send("morning", MORNING, context)


async def evening(context):
    """Run the evening friend check-in job."""
    await _send("evening", EVENING, context)


async def night(context):
    """Run the late-night friend check-in job."""
    await _send("3am", NIGHT, context)


async def mood_callback(update, context):
    """Handle a mood response without exposing internal state."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    replies = {
        "okay": "Good. Keep that okay protected. 🌙",
        "rough": "No pressure to explain. If you want to talk, I'm around.",
        "great": "Then keep that energy. 🔥",
        "later": "Fair. No interrogation. Come back when you feel like talking. 🖤",
    }
    mood = (query.data or "").split(":")[-1]
    try:
        await query.message.reply_text(replies.get(mood, "I'm listening. 🌙"))
    except Exception:
        log.exception("MOOD_CALLBACK_FAILED")


async def _ensure_canonical_db(app: Application) -> object | None:
    """Ensure canonical command handlers have one shared SQLite database object."""
    db = app.bot_data.get("oracle_db")
    if db is not None:
        return db
    try:
        from midnight_oracle.database import Database
        path = os.getenv("ORACLE_DATABASE_PATH", "midnight_oracle.sqlite3")
        db = Database(path)
        await db.connect()
        app.bot_data["oracle_db"] = db
        log.info("CANONICAL_DB_SURFACE_READY | path=%s", path)
        return db
    except Exception:
        log.exception("CANONICAL_DB_SURFACE_FAILED")
        return None


def _register_canonical_commands(app: Application) -> None:
    """Register the preserved Phase 1 command and Mini App surface exactly once."""
    from midnight_oracle.handlers.command_handler import (
        start, help_command, oracle, truth, memory, mymemory, forget, quiet, wake, house,
    )
    existing = set()
    for handlers in getattr(app, "handlers", {}).values():
        for handler in handlers:
            commands = getattr(handler, "commands", None)
            if commands:
                existing.update(str(c).lower().lstrip("/") for c in commands)
    callbacks = {
        "start": start, "help": help_command, "oracle": oracle, "truth": truth,
        "memory": memory, "mymemory": mymemory, "forget": forget, "quiet": quiet,
        "wake": wake, "house": house,
    }
    for command, callback in callbacks.items():
        if command not in existing:
            app.add_handler(CommandHandler(command, callback), group=1)
    try:
        from midnight_oracle.handlers.webapp_handler import handle_webapp_data
        app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data), group=2)
    except Exception:
        log.exception("MINI_APP_HANDLER_REGISTRATION_FAILED")


async def _canonical_startup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initialize the canonical command surface before any user invokes it."""
    await _ensure_canonical_db(context.application)


def register(app: Application):
    """Register friend automation, canonical commands, callbacks, and Mini App handlers."""
    app.add_handler(CallbackQueryHandler(mood_callback, pattern=r"^oracle:mood:"), group=5)
    _register_canonical_commands(app)
    if app.job_queue is None:
        log.warning("FRIEND_ENGINE_DISABLED | job_queue_unavailable=true")
        return
    app.job_queue.run_once(_canonical_startup, when=1, name="canonical_surface_startup")
    app.job_queue.run_daily(morning, time=time(9, 0, tzinfo=TZ), name="oracle_friend_morning")
    app.job_queue.run_daily(evening, time=time(19, 30, tzinfo=TZ), name="oracle_friend_evening")
    app.job_queue.run_daily(night, time=time(3, 0, tzinfo=TZ), name="oracle_friend_3am")
    log.info("FRIEND_ENGINE_READY | morning=09:00 | evening=19:30 | 3am=03:00 | spam_guard=on | canonical_commands=on | mini_app=on")
