"""
bot.py — Midnight Oracle | One canonical entrypoint.

Render runs: python bot.py
Existing token, groups, storage keys and internal compatibility names are preserved.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

logging.basicConfig(format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s", level=logging.INFO)
log = logging.getLogger("midnight.bot")

from dotenv import load_dotenv
load_dotenv()

BOT_NAME = "Midnight Oracle"
BOT_TAGLINE = "It watches. It names. It reveals."
TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    log.critical("BOT_TOKEN is not set. Add it to .env or Render environment.")
    sys.exit(1)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
ORACLE_TZ = ZoneInfo(os.getenv("ORACLE_TZ", os.getenv("ORACLE_TIMEZONE", "Asia/Kolkata")))

try:
    from storage import redis_client as _storage_client
except Exception as exc:
    log.warning("storage.py import failed: %s", exc)
    _storage_client = None

import startup
startup.init(_storage_client)

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import BotCommand
import legacy_bot

if hasattr(legacy_bot, "GEMINI_MODEL") and legacy_bot.GEMINI_MODEL in {"gemini-3.7-flash", "gemini-3.5-flash-lite"}:
    legacy_bot.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
if hasattr(legacy_bot, "GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID == 0:
    legacy_bot.GROUP_CHAT_ID = GROUP_CHAT_ID

async def _chat_registry_middleware(update, context):
    chat = getattr(update, "effective_chat", None)
    if chat and chat.type in ("group", "supergroup", "channel"):
        await startup.register_chat(chat.id, chat.type, chat.title or "")


def build_application() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, _chat_registry_middleware), group=-999)
    from handlers.social_engine import track_member
    app.add_handler(MessageHandler(filters.ALL, track_member), group=-998)
    from handlers.engagement_engine import init_storage as init_engagement_storage, register as register_engagement
    init_engagement_storage(_storage_client)
    register_engagement(app)

    if hasattr(legacy_bot, "register_handlers"):
        legacy_bot.register_handlers(app)
    elif hasattr(legacy_bot, "_register_handlers"):
        legacy_bot._register_handlers(app)
    else:
        _shim_register(app)

    if hasattr(legacy_bot, "broadcast_command"):
        app.add_handler(CommandHandler("broadcast", legacy_bot.broadcast_command))
    if hasattr(legacy_bot, "announce_command"):
        app.add_handler(CommandHandler("announce", legacy_bot.announce_command))

    from handlers.midnightmap import register as register_midnightmap
    register_midnightmap(app)
    return app


def _shim_register(app: Application):
    from handlers import (chat, games, moderation, utility, aesthetic, friendship,
                          fun, matchmaking, stats, events, economy, timecapsule, marriage)
    try:
        from handlers import deathgames_v2 as deathgames
    except ImportError:
        from handlers import deathgames

    command_map = {
        "oracle":"oracle_new_command", "aura":"aura_command", "identity":"identity_command",
        "vibecheck":"vibecheck_command", "shadow":"shadow_command", "element":"element_command",
        "corecode":"corecode_command", "universe":"universe_command", "ritual":"ritual_command",
        "duality":"duality_command", "glitch":"glitch_command", "nightreport":"nightreport_command",
        "sigil":"sigil_command", "checkin":"checkin_command", "streakcheck":"streakcheck_command",
        "vent":"vent_command", "cgift":"cgift_command", "rob":"eng_rob_command", "coinboard":"coinboard_command",
    }
    for cmd, fn in command_map.items():
        handler = getattr(legacy_bot, fn, None)
        if handler:
            app.add_handler(CommandHandler(cmd, handler))

    for module in (chat, games, moderation, utility, aesthetic, friendship, fun, matchmaking,
                   stats, events, economy, timecapsule, marriage, deathgames):
        if hasattr(module, "register"):
            module.register(app)
    if hasattr(legacy_bot, "handle_ai_message"):
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, legacy_bot.handle_ai_message), group=10)
    sticker_handler = getattr(legacy_bot, "handle_sticker", None) or getattr(legacy_bot, "smart_sticker_reply", None)
    if sticker_handler:
        app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))


async def _set_commands(app: Application):
    commands = [
        BotCommand("oracle", "🔮 Get a reading"), BotCommand("aura", "🟣 Scan your aura"),
        BotCommand("vibecheck", "✨ Check your vibe"), BotCommand("identity", "🃏 Your archetype"),
        BotCommand("shadow", "🌑 Meet your shadow"), BotCommand("element", "🌌 Your element"),
        BotCommand("corecode", "🔱 Your core words"), BotCommand("universe", "🌌 A message"),
        BotCommand("ritual", "🕯️ Today's ritual"), BotCommand("duality", "☯️ Your two sides"),
        BotCommand("nightreport", "🌙 Night report"), BotCommand("sigil", "🔱 Your sigil"),
        BotCommand("glitch", "⚡ Oracle glitch"), BotCommand("checkin", "🌙 Daily check-in"),
        BotCommand("streakcheck", "📊 Check streak"), BotCommand("vent", "🫀 Anonymous vent"),
        BotCommand("coinboard", "🏆 Coin leaderboard"), BotCommand("cgift", "💝 Gift coins"),
        BotCommand("rob", "🦹 Rob coins"),
    ]
    try:
        await app.bot.set_my_commands(commands)
        log.info("Telegram command menu set (%d public commands)", len(commands))
    except Exception as exc:
        log.warning("Could not set command menu: %s", exc)


async def _post_init(app: Application):
    await _set_commands(app)
    from handlers.social_engine import register_jobs, init_storage
    from handlers.presence_engine import register as register_presence, silence_check
    from handlers.help_command import register as help_register
    from handlers.homecoming import homecoming_job

    init_storage(_storage_client)
    from handlers import social_engine
    from handlers.oracle_governor import install as install_oracle_governor
    install_oracle_governor(social_engine)

    jq = app.job_queue
    if jq and not hasattr(jq, "run_weekly"):
        def _run_weekly(callback, time, weekday=None, days=(), name=None, data=None, job_kwargs=None):
            day = weekday if weekday is not None else (days[0] if days else 0)
            return jq.run_daily(callback, time=time, days=(day,), name=name, data=data, job_kwargs=job_kwargs)
        jq.run_weekly = _run_weekly
        log.info("Installed run_weekly compatibility adapter")

    register_jobs(app)
    register_presence(app)
    help_register(app)

    if jq:
        jq.run_repeating(homecoming_job, interval=21600, first=30, name="hidden_homecoming")
        log.info("HOMECOMING scheduler registered | every 6h | first run in 30s")
        jq.run_daily(silence_check, time=datetime.now(ORACLE_TZ).replace(hour=2, minute=0, second=0, microsecond=0).timetz(), name="silence_check")

    if hasattr(legacy_bot, "_post_init"):
        try:
            await legacy_bot._post_init(app)
        except Exception as exc:
            log.warning("legacy_bot._post_init failed: %s", exc)
    log.info("Post-init complete — Midnight Oracle is ready")


def main():
    app = build_application()
    original_initialize = app.initialize
    hooks_ran = False
    async def initialize_with_hooks():
        nonlocal hooks_ran
        await original_initialize()
        if not hooks_ran:
            hooks_ran = True
            await _post_init(app)
    app.initialize = initialize_with_hooks
    asyncio.run(startup.run(app, storage_client=_storage_client))


if __name__ == "__main__":
    main()