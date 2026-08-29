"""
bot.py — Midnight Oracle | One canonical entrypoint.

This is the ONLY file Render should run: python bot.py

Architecture:
  bot.py
    └── startup.py      (lease, health, shutdown, chat registry)
    └── legacy_bot.py   (all handlers, Gemini, GIPHY, stickers)
    └── storage.py      (Redis compat facade → core/storage)

Public brand: Midnight Oracle
Internal compatibility identifiers intentionally remain unchanged so existing
stored data, environment variables, feature keys, and legacy handlers are not
broken by the rebrand.
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

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    level=logging.INFO,
)
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
if not GEMINI_API_KEY:
    log.warning("GEMINI_API_KEY not set — AI replies will use fallback responses.")

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
if GROUP_CHAT_ID == 0:
    log.warning(
        "GROUP_CHAT_ID not set — scheduled/broadcast group messages will be skipped. "
        "Use /id in your group to get the ID."
    )

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
if OWNER_ID == 0:
    log.warning("OWNER_ID not set — owner-only commands will be unavailable.")

ORACLE_TZ = ZoneInfo(os.getenv("ORACLE_TIMEZONE", "Asia/Kolkata"))

try:
    from storage import redis_client as _storage_client
    log.info("Storage: using storage.RedisCompat → core.storage")
except Exception as _e:
    log.warning("storage.py import failed (%s) — storage features disabled", _e)
    _storage_client = None

import startup
startup.init(_storage_client)

from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, filters
from telegram import BotCommand

import legacy_bot

if hasattr(legacy_bot, "GEMINI_MODEL"):
    current = legacy_bot.GEMINI_MODEL
    bad_models = {"gemini-3.7-flash", "gemini-3.5-flash-lite"}
    if current in bad_models:
        good = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        log.warning("Fixing wrong GEMINI_MODEL '%s' → '%s'", current, good)
        legacy_bot.GEMINI_MODEL = good

if hasattr(legacy_bot, "GROUP_CHAT_ID") and legacy_bot.GROUP_CHAT_ID == 0:
    legacy_bot.GROUP_CHAT_ID = GROUP_CHAT_ID

async def _chat_registry_middleware(update, context):
    """Called on every update — registers the chat so broadcast works."""
    chat = getattr(update, "effective_chat", None)
    if chat and chat.type in ("group", "supergroup", "channel"):
        await startup.register_chat(
            chat_id=chat.id,
            chat_type=chat.type,
            title=chat.title or "",
        )


def build_application() -> Application:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, _chat_registry_middleware), group=-999)

    from handlers.social_engine import track_member
    app.add_handler(MessageHandler(filters.ALL, track_member), group=-998)

    if hasattr(legacy_bot, "register_handlers"):
        legacy_bot.register_handlers(app)
        log.info("Handlers registered via legacy_bot.register_handlers()")
    elif hasattr(legacy_bot, "_register_handlers"):
        legacy_bot._register_handlers(app)
        log.info("Handlers registered via legacy_bot._register_handlers()")
    else:
        _shim_register(app)

    return app


def _shim_register(app: Application):
    from handlers import (
        chat, games, moderation, utility, aesthetic,
        friendship, fun, matchmaking, stats,
        events, economy, timecapsule, marriage,
    )
    try:
        from handlers import deathgames_v2 as deathgames
    except ImportError:
        from handlers import deathgames

    app.add_handler(CommandHandler("oracle", legacy_bot.oracle_new_command))
    app.add_handler(CommandHandler("aura", legacy_bot.aura_command))
    app.add_handler(CommandHandler("identity", legacy_bot.identity_command))
    app.add_handler(CommandHandler("vibecheck", legacy_bot.vibecheck_command))
    app.add_handler(CommandHandler("shadow", legacy_bot.shadow_command))
    app.add_handler(CommandHandler("element", legacy_bot.element_command))
    app.add_handler(CommandHandler("corecode", legacy_bot.corecode_command))
    app.add_handler(CommandHandler("universe", legacy_bot.universe_command))
    app.add_handler(CommandHandler("ritual", legacy_bot.ritual_command))
    app.add_handler(CommandHandler("duality", legacy_bot.duality_command))
    app.add_handler(CommandHandler("glitch", legacy_bot.glitch_command))
    app.add_handler(CommandHandler("nightreport", legacy_bot.nightreport_command))
    app.add_handler(CommandHandler("sigil", legacy_bot.sigil_command))
    app.add_handler(CommandHandler("checkin", legacy_bot.checkin_command))
    app.add_handler(CommandHandler("streakcheck", legacy_bot.streakcheck_command))
    app.add_handler(CommandHandler("vent", legacy_bot.vent_command))
    app.add_handler(CommandHandler("cgift", legacy_bot.cgift_command))
    app.add_handler(CommandHandler("rob", legacy_bot.eng_rob_command))
    app.add_handler(CommandHandler("coinboard", legacy_bot.coinboard_command))

    for module in (chat, games, moderation, utility, aesthetic, friendship, fun,
                   matchmaking, stats, events, economy, timecapsule, marriage, deathgames):
        if hasattr(module, "register"):
            module.register(app)

    if hasattr(legacy_bot, "handle_ai_message"):
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, legacy_bot.handle_ai_message), group=10)
    if hasattr(legacy_bot, "handle_sticker"):
        app.add_handler(MessageHandler(filters.Sticker.ALL, legacy_bot.handle_sticker))

    log.info("Handlers registered via shim (legacy_bot internals)")


async def _set_commands(app: Application):
    commands = [
        BotCommand("oracle", "🔮 Get a reading"),
        BotCommand("aura", "🟣 Scan your aura"),
        BotCommand("vibecheck", "✨ Check your vibe"),
        BotCommand("identity", "🃏 Your archetype"),
        BotCommand("shadow", "🌑 Meet your shadow"),
        BotCommand("element", "🌌 Your element"),
        BotCommand("corecode", "🔱 Your core words"),
        BotCommand("universe", "🌌 A message for you"),
        BotCommand("ritual", "🕯️ Today's ritual"),
        BotCommand("duality", "☯️ Your two sides"),
        BotCommand("nightreport", "🌙 Tonight's report"),
        BotCommand("sigil", "🔱 Your personal sigil"),
        BotCommand("glitch", "⚡ A system reading"),
        BotCommand("checkin", "🌙 Daily check-in & streak"),
        BotCommand("streakcheck", "📊 Check your streak"),
        BotCommand("coinboard", "🏆 Coin leaderboard"),
        BotCommand("cgift", "💝 Gift coins"),
        BotCommand("rob", "🦹 Rob someone's coins"),
        BotCommand("vent", "🫀 Anonymous vent"),
    ]
    try:
        await app.bot.set_my_commands(commands)
        log.info("Telegram command menu set (%d public commands)", len(commands))
    except Exception as exc:
        log.warning("Could not set command menu: %s", exc)


async def _post_init(app: Application):
    await _set_commands(app)

    from handlers.social_engine import register_jobs, init_storage
    from handlers.presence_engine import register, silence_check
    from handlers.help_command import register as help_register

    init_storage(_storage_client)
    register_jobs(app)
    register(app)
    help_register(app)

    app.job_queue.run_daily(
        silence_check,
        time=datetime.now(ORACLE_TZ).replace(hour=2, minute=0, second=0, microsecond=0).timetz(),
    )

    if hasattr(legacy_bot, "_post_init"):
        try:
            await legacy_bot._post_init(app)
        except Exception as exc:
            log.warning("legacy_bot._post_init failed: %s", exc)

    log.info("Post-init complete — Midnight Oracle is ready")


def main():
    app = build_application()
    app.post_init = _post_init
    log.info("Midnight Oracle starting — instance %s", startup._INSTANCE_ID)
    asyncio.run(startup.run(app, storage_client=_storage_client))


if __name__ == "__main__":
    main()
