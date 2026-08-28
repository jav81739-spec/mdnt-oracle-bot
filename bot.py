"""
bot.py — Midnight Oracle | One canonical entrypoint.

This is the ONLY file Render should run: python bot.py
Delete bot2.py, bot3.py, bot_1.py — they are dead duplicates.

Architecture:
  bot.py
    └── startup.py      (lease, health, shutdown, chat registry)
    └── legacy_bot.py   (all handlers, Gemini, GIPHY, stickers, Baka/Nova)
    └── storage.py      (Redis compat facade → core/storage)
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

TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    log.critical("BOT_TOKEN is not set. Add it to .env or Render environment.")
    sys.exit(1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if not GEMINI_API_KEY:
    log.warning("GEMINI_API_KEY not set — AI replies will use fallback responses.")

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or "0")
if GROUP_CHAT_ID == 0:
    log.warning("GROUP_CHAT_ID not set — scheduled/broadcast group messages will be skipped. Use /id in your group to get the ID.")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
if OWNER_ID == 0:
    log.warning("OWNER_ID not set — owner-only commands will be unavailable.")

ORACLE_TZ = ZoneInfo(os.getenv("ORACLE_TIMEZONE", "Asia/Kolkata"))

try:
    from storage import redis_client as _storage_client
    log.info("Storage: using storage.RedisCompat → core/storage")
except Exception as _e:
    log.warning("storage.py import failed (%s) — storage features disabled", _e)
    _storage_client = None

import startup
startup.init(_storage_client)

from telegram.ext import Application, MessageHandler, filters
from telegram import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllChatAdministrators,
)

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
    chat = getattr(update, "effective_chat", None)
    if chat and chat.type in ("group", "supergroup", "channel"):
        await startup.register_chat(chat_id=chat.id, chat_type=chat.type, title=chat.title or "")


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
    """Import the complete handler set from legacy_bot without a second poller."""
    class _CaptureApplication:
        last_instance = None

        def __init__(self):
            self.handlers = []
            type(self).last_instance = self

        def add_handler(self, handler, group=0):
            self.handlers.append((handler, group))

        def run_polling(self, *_args, **_kwargs):
            # legacy_bot.main() reaches this point after registration. Never
            # start its polling loop; startup.py owns the only real poller.
            return None

    class _CaptureBuilder:
        def __init__(self):
            self._capture = _CaptureApplication()

        def token(self, *_args, **_kwargs):
            return self

        def post_init(self, *_args, **_kwargs):
            return self

        def build(self):
            return self._capture

    original_application = legacy_bot.Application
    original_dummy_server = getattr(legacy_bot, "_start_dummy_server", None)

    try:
        legacy_bot.Application = type(
            "_CapturedApplication",
            (),
            {"builder": staticmethod(lambda: _CaptureBuilder())},
        )
        if original_dummy_server is not None:
            legacy_bot._start_dummy_server = lambda: None

        legacy_bot.main()
        captured = _CaptureApplication.last_instance
        if captured is None:
            raise RuntimeError("legacy_bot.main() did not create its application")

        for handler, group in captured.handlers:
            app.add_handler(handler, group=group)

        log.info("Handlers registered from legacy_bot.main(): %d handlers", len(captured.handlers))
    finally:
        legacy_bot.Application = original_application
        if original_dummy_server is not None:
            legacy_bot._start_dummy_server = original_dummy_server


async def _set_commands(app: Application):
    commands = [
        BotCommand("start", "🌙 Enter the Midnight Realm"),
        BotCommand("help", "📖 See what Midnight Oracle can do"),
        BotCommand("oracle", "🔮 Your daily Oracle prophecy"),
        BotCommand("aura", "🟣 Scan your aura"),
        BotCommand("vibecheck", "✨ Vibe check"),
        BotCommand("identity", "🃏 Your Oracle archetype"),
        BotCommand("shadow", "🌑 Meet your shadow self"),
        BotCommand("element", "🌌 Your cosmic element"),
        BotCommand("corecode", "🔱 Your core words"),
        BotCommand("universe", "🌌 Message from the universe"),
        BotCommand("ritual", "🕯️ Today's ritual"),
        BotCommand("duality", "☯️ Your duality"),
        BotCommand("nightreport", "🌙 Tonight's night report"),
        BotCommand("sigil", "🔱 Your personal sigil"),
        BotCommand("glitch", "⚡ Oracle glitch"),
        BotCommand("checkin", "🌙 Daily check-in & streak"),
        BotCommand("streakcheck", "📊 Check your streak"),
        BotCommand("coinboard", "🏆 Coin leaderboard"),
        BotCommand("cgift", "💝 Gift coins to someone"),
        BotCommand("rob", "🦹 Rob someone's coins"),
        BotCommand("vent", "🫀 Anonymous vent"),
    ]
    try:
        await app.bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
        await app.bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
        await app.bot.delete_my_commands(scope=BotCommandScopeAllChatAdministrators())
        await app.bot.delete_my_commands(scope=BotCommandScopeDefault())
        await app.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
        await app.bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
        await app.bot.set_my_commands(commands, scope=BotCommandScopeAllChatAdministrators())
        await app.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        log.info("Telegram command menus set (%d commands) for private, group, admin and default scopes", len(commands))
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
        time=datetime.now(ORACLE_TZ).replace(hour=2, minute=0, second=0).timetz(),
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
